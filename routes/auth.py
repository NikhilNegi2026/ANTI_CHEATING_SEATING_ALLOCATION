from flask import Blueprint, render_template, request, redirect, session
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        role = request.form.get("role")
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password or not role:
            error = "Please select a role and enter both username and password."
            return render_template("login.html", error=error)

        db = get_db()
        cursor = db.cursor(dictionary=True, buffered=True)

        if role == "admin":
            # Fetch admin from database instead of hardcoded hash
            cursor.execute("SELECT * FROM admins WHERE username = %s", (username,))
            admin = cursor.fetchone()

            if admin and check_password_hash(admin["password_hash"], password):
                session.clear()
                session["user"] = username
                session["role"] = "admin"
                cursor.close()
                db.close()
                return redirect("/dashboard")
            else:
                error = "Invalid Admin Credentials"

        elif role == "student":
            cursor.execute("SELECT * FROM students WHERE TRIM(UPPER(roll)) = %s", (username.upper(),))
            student = cursor.fetchone()

            if student:
                db_password = student.get("password")

                if password.upper() == str(student["roll"]).strip().upper() or (db_password and str(db_password).strip().upper() == password.upper()):
                    session.clear()
                    session["user"] = student["roll"]  
                    session["student_roll"] = student["roll"]
                    session["role"] = "student"
                    cursor.close()
                    db.close()
                    return redirect("/student_panel")
                else:
                    error = "Invalid Password. Please use your Roll Number as the password."
            else:
                error = f"Roll Number '{username}' not found in database."

        cursor.close()
        db.close()

    return render_template("login.html", error=error)

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@auth_bp.route("/setup_admin")
def setup_admin():
    db = get_db()
    cursor = db.cursor()
    
    hashed_pw = generate_password_hash("admin123", method='pbkdf2:sha256')
    
    try:
        cursor.execute("DELETE FROM admins WHERE username = 'admin'")
        cursor.execute("INSERT INTO admins (username, password_hash) VALUES (%s, %s)", ('admin', hashed_pw))
        db.commit()
        cursor.close()
        db.close()
        return "SUCCESS! Admin created. Go to /login and type: admin / admin123"
    except Exception as e:
        cursor.close()
        db.close()
        return f"Error: {e}"
