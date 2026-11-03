import os, csv, io
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, Response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-this-secret-key")
database_url = os.getenv("DATABASE_URL", "sqlite:///feedback.db")
# Render and some providers supply postgres://; SQLAlchemy expects postgresql://.
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False, unique=True)
    code = db.Column(db.String(30), nullable=False, unique=True)
    semester = db.Column(db.String(40), default="Current semester")
    active = db.Column(db.Boolean, default=True)
    questions = db.relationship("FeedbackQuestion", backref="course", cascade="all, delete-orphan")
    feedback = db.relationship("Feedback", backref="course", cascade="all, delete-orphan")

class FeedbackQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    text = db.Column(db.String(300), nullable=False)
    active = db.Column(db.Boolean, default=True)

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("feedback_question.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.String(1000))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

@app.context_processor
def inject_globals():
    return {"current_year": datetime.now().year}

@app.route("/")
def index():
    courses = Course.query.filter_by(active=True).order_by(Course.name).all()
    return render_template("index.html", courses=courses)

@app.route("/feedback/<int:course_id>", methods=["GET", "POST"])
def submit_feedback(course_id):
    course = Course.query.filter_by(id=course_id, active=True).first_or_404()
    questions = FeedbackQuestion.query.filter_by(course_id=course.id, active=True).all()
    if request.method == "POST":
        if not questions:
            flash("This course has no active feedback questions yet.", "warning")
            return redirect(url_for("index"))
        comment = request.form.get("comment", "").strip()
        if len(comment) > 1000:
            flash("Comment must be 1000 characters or fewer.", "danger")
            return redirect(url_for("submit_feedback", course_id=course.id))
        ratings = {}
        for q in questions:
            raw = request.form.get(f"rating_{q.id}", "")
            if raw not in {"1", "2", "3", "4", "5"}:
                flash("Please select a rating from 1 to 5 for every question.", "danger")
                return redirect(url_for("submit_feedback", course_id=course.id))
            ratings[q.id] = int(raw)
        for q in questions:
            db.session.add(Feedback(course_id=course.id, question_id=q.id,
                                    rating=ratings[q.id], comment=comment or None))
        db.session.commit()
        return render_template("thank_you.html", course=course)
    return render_template("feedback.html", course=course, questions=questions)

@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = Admin.query.filter_by(username=request.form.get("username", "").strip()).first()
        if user and check_password_hash(user.password_hash, request.form.get("password", "")):
            session["admin_id"] = user.id
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")

@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/admin")
@admin_required
def dashboard():
    courses = Course.query.order_by(Course.name).all()
    total = Feedback.query.count()
    course_stats = []
    for c in courses:
        rows = Feedback.query.filter_by(course_id=c.id).all()
        avg = round(sum(x.rating for x in rows)/len(rows), 2) if rows else 0
        course_stats.append({"course": c, "responses": len(rows), "average": avg})
    recent = Feedback.query.order_by(Feedback.created_at.desc()).limit(8).all()
    return render_template("dashboard.html", courses=courses, total=total,
                           course_stats=course_stats, recent=recent)

@app.route("/admin/courses", methods=["GET", "POST"])
@admin_required
def manage_courses():
    if request.method == "POST":
        name, code = request.form.get("name", "").strip(), request.form.get("code", "").strip().upper()
        semester = request.form.get("semester", "").strip() or "Current semester"
        if not name or not code:
            flash("Course name and code are required.", "danger")
        elif Course.query.filter((Course.name == name) | (Course.code == code)).first():
            flash("A course with that name or code already exists.", "warning")
        else:
            c = Course(name=name, code=code, semester=semester)
            db.session.add(c); db.session.commit()
            flash("Course added. Add questions below.", "success")
            return redirect(url_for("manage_questions", course_id=c.id))
    return render_template("courses.html", courses=Course.query.order_by(Course.name).all())

@app.route("/admin/courses/<int:course_id>/toggle", methods=["POST"])
@admin_required
def toggle_course(course_id):
    c = Course.query.get_or_404(course_id); c.active = not c.active
    db.session.commit()
    flash("Course status updated.", "success")
    return redirect(url_for("manage_courses"))

@app.route("/admin/courses/<int:course_id>/questions", methods=["GET", "POST"])
@admin_required
def manage_questions(course_id):
    course = Course.query.get_or_404(course_id)
    if request.method == "POST":
        text = request.form.get("text", "").strip()
        if text:
            db.session.add(FeedbackQuestion(course_id=course.id, text=text))
            db.session.commit(); flash("Question added.", "success")
        else: flash("Enter a question.", "danger")
        return redirect(url_for("manage_questions", course_id=course.id))
    return render_template("questions.html", course=course)

@app.route("/admin/questions/<int:question_id>/toggle", methods=["POST"])
@admin_required
def toggle_question(question_id):
    q = FeedbackQuestion.query.get_or_404(question_id); q.active = not q.active
    db.session.commit()
    return redirect(url_for("manage_questions", course_id=q.course_id))

@app.route("/admin/reports")
@admin_required
def reports():
    courses = Course.query.order_by(Course.name).all()
    selected_id = request.args.get("course", type=int)
    selected = Course.query.get(selected_id) if selected_id else (courses[0] if courses else None)
    labels, averages, counts, comments = [], [], [], []
    total_responses = 0
    if selected:
        qs = FeedbackQuestion.query.filter_by(course_id=selected.id).all()
        for q in qs:
            rows = Feedback.query.filter_by(course_id=selected.id, question_id=q.id).all()
            labels.append(q.text); counts.append(len(rows))
            averages.append(round(sum(x.rating for x in rows)/len(rows), 2) if rows else 0)
            total_responses = max(total_responses, len(rows))
        # Suppress comments unless at least five feedback submissions exist for the course.
        all_rows = Feedback.query.filter_by(course_id=selected.id).all()
        if len(all_rows) >= 5:
            comments = [x.comment for x in all_rows if x.comment]
    return render_template("reports.html", courses=courses, selected=selected,
                           labels=labels, averages=averages, counts=counts,
                           comments=comments, total_responses=total_responses)

@app.route("/admin/export")
@admin_required
def export_csv():
    course_id = request.args.get("course", type=int)
    query = Feedback.query
    if course_id: query = query.filter_by(course_id=course_id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Course", "Course code", "Question", "Rating (1-5)", "Comment", "Submitted at"])
    for row in query.order_by(Feedback.created_at.desc()).all():
        q = FeedbackQuestion.query.get(row.question_id)
        writer.writerow([row.course.name, row.course.code, q.text if q else "",
                         row.rating, row.comment or "", row.created_at.isoformat()])
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=feedback_report.csv"})

def seed():
    db.create_all()
    if not Admin.query.first():
        username = os.getenv("ADMIN_USERNAME", "admin")
        password = os.getenv("ADMIN_PASSWORD", "admin123")
        db.session.add(Admin(username=username, password_hash=generate_password_hash(password)))
    if not Course.query.first():
        c = Course(name="Python Programming", code="CSE101", semester="Semester 1")
        db.session.add(c); db.session.flush()
        for question in ["The topics were explained clearly.", "The course materials were useful.",
                         "The pace of the course was appropriate.", "Practical sessions supported learning.",
                         "Overall, I am satisfied with this course."]:
            db.session.add(FeedbackQuestion(course_id=c.id, text=question))
    db.session.commit()

with app.app_context():
    seed()

if __name__ == "__main__":
    app.run(debug=True)
