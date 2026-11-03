# Student Feedback Analysis System

A complete Flask + SQLAlchemy web application based on the submitted project abstract:
- Anonymous student feedback (no name/roll number fields)
- Course ratings from 1 to 5 and optional comments
- Admin login, course and question management
- Dashboard with response counts and average ratings
- Course-wise charts and CSV export
- Comments hidden until a course has at least five feedback records

## Run locally (Windows)

1. Install Python 3.10+ and MySQL if you want to use MySQL.
2. Extract this folder and open a terminal inside it.
3. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .venv\Scripts\activate
   ```
4. Install packages:

   ```powershell
   pip install -r requirements.txt
   ```
5. Optional: copy `.env.example` to `.env`, then set a strong `SECRET_KEY` and admin password.
6. Run:

   ```powershell
   python app.py
   ```
7. Open http://127.0.0.1:5000

## Default demo login

- Username: `admin`
- Password: `admin123`

Change these before using the app beyond a local demo. The first run creates the database and a sample course with questions.

## Use MySQL

Create a database in MySQL:

```sql
CREATE DATABASE student_feedback CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Set `DATABASE_URL` in `.env`:

```text
DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@localhost/student_feedback
```

Then run `python app.py`. Tables are created automatically.

## Main pages

- `/` — student course selection
- `/feedback/<course_id>` — anonymous feedback form
- `/admin/login` — administrator sign-in
- `/admin` — dashboard
- `/admin/courses` — create and activate/deactivate courses
- `/admin/courses/<course_id>/questions` — manage questions
- `/admin/reports` — course analytics and comments
- `/admin/export?course=<id>` — CSV export

## Notes

This is a student-project starter implementation, not a production-hardened deployment. Before public deployment add CSRF protection, HTTPS, rate limiting, secure secret management, database backups, and stronger admin account management. The app stores one feedback row per question; a future anonymous-token mechanism is needed if you want to enforce one submission per student without collecting identity.


## Deploy on Render

This repository includes `render.yaml` for a Render Blueprint deployment.
1. Push the project to GitHub.
2. In Render, choose **New → Blueprint**, connect the repository, and apply the Blueprint.
3. Set the prompted `ADMIN_PASSWORD` to a strong password.
4. Wait for the web service and PostgreSQL database to be created. Open the service's `onrender.com` URL.

The Blueprint configures Gunicorn and a PostgreSQL database. Check Render's current free-plan limits and database retention before relying on it for long-term records.
