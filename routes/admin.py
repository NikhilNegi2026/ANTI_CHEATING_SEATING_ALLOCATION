from flask import Blueprint, render_template, request, redirect, session, flash
import csv
from datetime import date
from db import get_db

admin_bp = Blueprint('admin', __name__)

@admin_bp.before_request
def require_admin():
    pass

@admin_bp.route("/dashboard")
def dashboard():
    if session.get("role") != "admin":
        return redirect("/")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS c FROM students")
    student_count = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) AS c FROM teachers")
    teacher_count = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) AS c FROM halls")
    hall_count = cursor.fetchone()["c"]

    cursor.execute("SELECT * FROM seating LIMIT 5")
    seating = cursor.fetchall()

    today = date.today()

    cursor.execute("""
        SELECT * FROM exams
        WHERE exam_date >= %s
        ORDER BY exam_date, exam_time
    """, (today,))
    schedule = cursor.fetchall()

    cursor.execute("SELECT * FROM courses")
    available_courses = cursor.fetchall()

    cursor.execute("""
        SELECT MIN(exam_date) AS next_date
        FROM exams
        WHERE exam_date >= %s
    """, (today,))
    result = cursor.fetchone()
    next_date = result["next_date"] if result else None

    if next_date:
        cursor.execute("""
            SELECT subject_name AS subject, exam_time AS time, course
            FROM exams
            WHERE exam_date = %s
        """, (next_date,))
        exams = cursor.fetchall()
    else:
        exams = []

    cursor.close()
    db.close()

    return render_template(
        "dashboard.html",
        student_count=student_count,
        teacher_count=teacher_count,
        hall_count=hall_count,
        seating=seating,
        exams=exams,          
        schedule=schedule,    
        next_date=next_date,  
        available_courses=available_courses 
    )

@admin_bp.route("/schedule_exam", methods=["POST"])
def schedule_exam():
    if session.get("role") != "admin":
        return redirect("/")

    exam_date = request.form.get("exam_date")
    exam_time = request.form.get("exam_time")
    course_code = request.form.get("course_code")
    subject_name = request.form.get("subject_name")

    if not exam_date or not exam_time or not course_code or not subject_name:
        flash("All fields are required to schedule an exam.", "error")
        return redirect("/dashboard")

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            "INSERT INTO exams (exam_date, exam_time, course, subject_name) VALUES (%s, %s, %s, %s)",
            (exam_date, exam_time, course_code, subject_name)
        )
        db.commit()
        flash("Exam scheduled successfully.", "success")
    except Exception as e:
        flash(f"Database Error: {e}", "error")
    finally:
        cursor.close()
        db.close()

    return redirect("/schedule")

@admin_bp.route("/schedule")
def schedule():
    role = session.get("role")
    if not role:
        return redirect("/")

    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    schedule_data = []
    is_admin = (role == "admin") 

    if is_admin:
        cursor.execute("""
            SELECT id, exam_date, exam_time AS time, subject_name AS subject 
            FROM exams ORDER BY exam_date ASC
        """)
        schedule_data = cursor.fetchall()
    elif role == "student":
        roll = session.get("student_roll")
        cursor.execute("SELECT branch FROM students WHERE roll = %s", (roll,))
        student = cursor.fetchone()
        
        if student and student.get("branch"):
            cursor.execute("""
                SELECT id, exam_date, exam_time AS time, subject_name AS subject 
                FROM exams WHERE UPPER(course) = UPPER(%s) ORDER BY exam_date ASC
            """, (student['branch'].strip(),))
            schedule_data = cursor.fetchall()

    cursor.close()
    db.close()
    return render_template("schedule.html", schedule=schedule_data, is_admin=is_admin)

@admin_bp.route("/delete_exam/<int:exam_id>")
def delete_exam(exam_id):
    if session.get("role") != "admin":
        return redirect("/")

    db = get_db()
    cursor = db.cursor()
    try:
        # Before deleting, check if seating has been generated for this exam date/subject.
        # But for simplicity, we just delete.
        cursor.execute("DELETE FROM exams WHERE id = %s", (exam_id,))
        db.commit()
        flash("Exam deleted successfully.", "success")
    except Exception as e:
        flash(f"Delete Error: {e}", "error")
    finally:
        cursor.close()
        db.close()
    
    return redirect("/schedule")

@admin_bp.route("/students", methods=["GET", "POST"])
def students_page():
    if "user" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form.get("name")
        roll = request.form.get("roll")
        branch = request.form.get("branch")
        subject = request.form.get("subject")
        section = request.form.get("section")
        password = request.form.get("password")

        if not name or not roll or not branch or not password:
            flash("Name, Roll, Branch, and Password are required.", "error")
        else:
            try:
                cursor.execute(
                    "INSERT INTO students(name,roll,branch,subject,section,password) VALUES(%s,%s,%s,%s,%s,%s)",
                    (name, roll, branch, subject, section, password)
                )
                db.commit()
                flash("Student added successfully.", "success")
            except Exception as e:
                flash(f"Error adding student: {e}", "error")

    cursor.execute("SELECT * FROM students")
    students = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("students.html", students=students)

@admin_bp.route("/upload_students", methods=["POST"])
def upload_students():
    if session.get("role") != "admin":
        return redirect("/")

    file = request.files.get("file")
    if not file:
        flash("No file provided.", "error")
        return redirect("/students")

    db = get_db()
    cursor = db.cursor()
    try:
        content = file.read().decode("utf-8-sig").splitlines()
        reader = csv.reader(content)
        next(reader, None)

        for row in reader:
            if len(row) < 6:
                continue
            cursor.execute(
                "INSERT INTO students(name,roll,branch,subject,section,password) VALUES(%s,%s,%s,%s,%s,%s)",
                (row[0], row[1], row[2], row[3], row[4], row[5])
            )
        db.commit()
        flash("Students uploaded successfully.", "success")
    except Exception as e:
        flash(f"CSV Upload Error: {e}", "error")
    finally:
        cursor.close()
        db.close()

    return redirect("/students")

@admin_bp.route("/delete_all_students", methods=["POST"])
def delete_all_students():
    if session.get("role") != "admin":
        return redirect("/")

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM seating")
        cursor.execute("DELETE FROM students")
        db.commit()
        flash("All students deleted.", "success")
    except Exception as e:
        flash(f"Delete All Error: {e}", "error")
    finally:
        cursor.close()
        db.close()
        
    return redirect("/students")

@admin_bp.route("/delete_student/<roll>", methods=["POST"])
def delete_student(roll):
    if session.get("role") != "admin":
        return redirect("/")

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM seating WHERE roll = %s", (roll,))
        cursor.execute("DELETE FROM students WHERE roll = %s", (roll,))
        db.commit()
        flash("Student deleted.", "success")
    except Exception as e:
        flash(f"Delete Student Error: {e}", "error")
    finally:
        cursor.close()
        db.close()
        
    return redirect("/students")

@admin_bp.route("/manage_courses", methods=["GET", "POST"])
def manage_courses():
    if "user" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        code = request.form.get("course_code")
        name = request.form.get("course_name")
        if not code or not name:
            flash("Course code and name are required.", "error")
        else:
            try:
                cursor.execute("INSERT INTO courses (course_code, course_name) VALUES (%s, %s)", (code.upper().strip(), name.strip()))
                db.commit()
                flash("Course added successfully.", "success")
            except Exception as e:
                flash(f"Error adding course: {e}", "error")

    cursor.execute("""
        SELECT c.course_code, c.course_name, COUNT(s.roll) as student_count
        FROM courses c
        LEFT JOIN students s ON c.course_code = s.branch
        GROUP BY c.course_code, c.course_name
    """)
    courses_data = cursor.fetchall()
    
    cursor.close()
    db.close()
    return render_template("courses.html", courses=courses_data)

@admin_bp.route("/delete_course/<code>")
def delete_course(code):
    if session.get("role") != "admin":
        return redirect("/")
        
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        # Check foreign key constraint manually to avoid generic DB errors
        cursor.execute("SELECT COUNT(*) as c FROM students WHERE branch = %s", (code,))
        if cursor.fetchone()['c'] > 0:
            flash("Cannot delete course: There are students enrolled in this course.", "error")
            return redirect("/manage_courses")
            
        cursor.execute("SELECT COUNT(*) as c FROM exams WHERE course = %s", (code,))
        if cursor.fetchone()['c'] > 0:
            flash("Cannot delete course: There are exams scheduled for this course.", "error")
            return redirect("/manage_courses")

        cursor.execute("DELETE FROM courses WHERE course_code = %s", (code,))
        db.commit()
        flash("Course deleted successfully.", "success")
    except Exception as e:
        flash(f"Delete Course Error: {e}", "error")
    finally:
        cursor.close()
        db.close()
        
    return redirect("/manage_courses")

@admin_bp.route("/teachers", methods=["GET", "POST"])
def teachers_page():
    if "user" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form.get("name")
        subject = request.form.get("subject")
        if not name or not subject:
            flash("Name and subject are required.", "error")
        else:
            try:
                cursor.execute(
                    "INSERT INTO teachers(name,subject) VALUES(%s,%s)",
                    (name, subject)
                )
                db.commit()
                flash("Teacher added successfully.", "success")
            except Exception as e:
                flash(f"Error adding teacher: {e}", "error")

    cursor.execute("SELECT * FROM teachers")
    teachers = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("teachers.html", teachers=teachers)

@admin_bp.route("/delete_teacher/<int:id>")
def delete_teacher(id):
    if session.get("role") != "admin":
        return redirect("/")

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT name FROM teachers WHERE id=%s", (id,))
        teacher = cursor.fetchone()
        if teacher:
            t_name = teacher['name']
            cursor.execute("SELECT COUNT(*) as c FROM invigilation_assignments WHERE teacher1=%s OR teacher2=%s", (t_name, t_name))
            if cursor.fetchone()['c'] > 0:
                flash("Cannot delete teacher: They are currently assigned to invigilation duties.", "error")
                return redirect("/teachers")
                
            cursor.execute("DELETE FROM teachers WHERE id=%s", (id,))
            db.commit()
            flash("Teacher deleted successfully.", "success")
    except Exception as e:
        flash(f"Delete Teacher Error: {e}", "error")
    finally:
        cursor.close()
        db.close()

    return redirect("/teachers")

@admin_bp.route("/edit_teacher/<int:id>", methods=["GET", "POST"])
def edit_teacher(id):
    if session.get("role") != "admin":
        return redirect("/")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form.get("name")
        subject = request.form.get("subject")
        if not name or not subject:
            flash("Name and subject are required.", "error")
        else:
            try:
                cursor.execute(
                    "UPDATE teachers SET name=%s, subject=%s WHERE id=%s",
                    (name, subject, id)
                )
                db.commit()
                flash("Teacher updated successfully.", "success")
                cursor.close()
                db.close()
                return redirect("/teachers")
            except Exception as e:
                flash(f"Update Teacher Error: {e}", "error")

    cursor.execute("SELECT * FROM teachers WHERE id=%s", (id,))
    teacher = cursor.fetchone()

    cursor.close()
    db.close()

    return render_template("edit_teacher.html", teacher=teacher)

@admin_bp.route("/halls", methods=["GET", "POST"])
def halls_page():
    if "user" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        hall = request.form.get("hall")
        capacity = request.form.get("capacity")
        if not hall or not capacity:
            flash("Hall name and capacity are required.", "error")
        else:
            try:
                cursor.execute(
                    "INSERT INTO halls(hall,capacity) VALUES(%s,%s)",
                    (hall, capacity)
                )
                db.commit()
                flash("Hall added successfully.", "success")
            except Exception as e:
                flash(f"Error adding hall: {e}", "error")

    cursor.execute("SELECT * FROM halls")
    halls = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("halls.html", halls=halls)

@admin_bp.route("/delete_hall/<int:id>")
def delete_hall(id):
    if session.get("role") != "admin":
        return redirect("/")

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT hall FROM halls WHERE id=%s", (id,))
        hall_record = cursor.fetchone()
        if hall_record:
            h_name = hall_record['hall']
            
            cursor.execute("SELECT COUNT(*) as c FROM seating WHERE hall=%s", (h_name,))
            if cursor.fetchone()['c'] > 0:
                flash("Cannot delete hall: There are students currently seated in this hall.", "error")
                return redirect("/halls")
                
            cursor.execute("SELECT COUNT(*) as c FROM invigilation_assignments WHERE hall_id=%s", (h_name,))
            if cursor.fetchone()['c'] > 0:
                flash("Cannot delete hall: There are invigilators assigned to this hall.", "error")
                return redirect("/halls")

            cursor.execute("DELETE FROM halls WHERE id=%s", (id,))
            db.commit()
            flash("Hall deleted successfully.", "success")
    except Exception as e:
        flash(f"Delete Hall Error: {e}", "error")
    finally:
        cursor.close()
        db.close()

    return redirect("/halls")

@admin_bp.route("/edit_hall/<int:id>", methods=["GET", "POST"])
def edit_hall(id):
    if session.get("role") != "admin":
        return redirect("/")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        hall = request.form.get("hall")
        capacity = request.form.get("capacity")
        if not hall or not capacity:
            flash("Hall name and capacity are required.", "error")
        else:
            try:
                cursor.execute(
                    "UPDATE halls SET hall=%s, capacity=%s WHERE id=%s",
                    (hall, capacity, id)
                )
                db.commit()
                flash("Hall updated successfully.", "success")
                cursor.close()
                db.close()
                return redirect("/halls")
            except Exception as e:
                flash(f"Update Hall Error: {e}", "error")

    cursor.execute("SELECT * FROM halls WHERE id=%s", (id,))
    hall = cursor.fetchone()

    cursor.close()
    db.close()

    return render_template("edit_hall.html", hall=hall)
