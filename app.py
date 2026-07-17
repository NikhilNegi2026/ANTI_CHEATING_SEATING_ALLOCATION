from flask import Flask, render_template, request, redirect, session
import mysql.connector
import random
import csv
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback_secret_key")


# ---------------- DATABASE CONNECTION ----------------

def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "root"),
        database=os.getenv("DB_NAME", "exam_system")
    )


# ---------------- LOGIN ----------------

from werkzeug.security import check_password_hash

@app.route("/", methods=["GET", "POST"])
def login():
    error = None

    # ---------------- SECURE ADMIN HASH ----------------
    # This is the encrypted hash for the password "admin"
    ADMIN_HASH = "scrypt:32768:8:1$vW6BCRjqErLspKkf$c67969e52c38b89c3833408ae3c2ca4f0a6ca86ab383d677f445b7c99642dfe920def4fbbd2b53927577a360002bdc2f0deb36817eee9be8dd5a44570f232a73"

    if request.method == "POST":
        role = request.form.get("role")
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        # ---------------- BASIC VALIDATION ----------------
        if not username or not password or not role:
            error = "Please select a role and enter both username and password."
            return render_template("login.html", error=error)

        # ---------------- ADMIN LOGIN ----------------
        if role == "admin":
            # 👇 THIS IS THE FIX: Hashing validation instead of plain text 👇
            if username == "admin" and check_password_hash(ADMIN_HASH, password):
                session.clear()
                session["user"] = "admin"
                session["role"] = "admin"
                return redirect("/dashboard")
            else:
                error = "Invalid Admin Credentials"

        # ---------------- STUDENT LOGIN ----------------
        elif role == "student":
            db = get_db()
            
            cursor = db.cursor(dictionary=True, buffered=True)
            
            cursor.execute("SELECT * FROM students WHERE TRIM(UPPER(roll)) = %s", (username.upper(),))
            student = cursor.fetchone()
            
            cursor.close()
            db.close()

            if student:
                db_password = student.get("password")

                # The Master Key logic remains exactly the same!
                if password.upper() == str(student["roll"]).strip().upper() or (db_password and str(db_password).strip().upper() == password.upper()):
                    session.clear()
                    session["user"] = student["roll"]  
                    session["student_roll"] = student["roll"]
                    session["role"] = "student"
                    return redirect("/student_panel")
                else:
                    error = "Invalid Password. Please use your Roll Number as the password."
            else:
                error = f"Roll Number '{username}' not found in database."

    return render_template("login.html", error=error)

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        return redirect("/")

    from datetime import date

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # ---------------- COUNTS ----------------
    cursor.execute("SELECT COUNT(*) AS c FROM students")
    student_count = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) AS c FROM teachers")
    teacher_count = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) AS c FROM halls")
    hall_count = cursor.fetchone()["c"]

    # ---------------- RECENT SEATING ----------------
    cursor.execute("SELECT * FROM seating LIMIT 5")
    seating = cursor.fetchall()

    # 🔥 THE FIX: Get today's date first so we can use it everywhere
    today = date.today()

    # ---------------- ADMIN FULL SCHEDULE (FIXED) ----------------
    # Impact: The master schedule will no longer show old, passed exams.
    cursor.execute("""
        SELECT * FROM exams
        WHERE exam_date >= %s
        ORDER BY exam_date, exam_time
    """, (today,))
    schedule = cursor.fetchall()

    # ---------------- FETCH DYNAMIC COURSES ----------------
    cursor.execute("SELECT * FROM courses")
    available_courses = cursor.fetchall()

    # ---------------- UPCOMING EXAMS (SMART) ----------------
    # Impact: Ensures the "Next Exam" widget strictly looks forward.
    cursor.execute("""
        SELECT MIN(exam_date) AS next_date
        FROM exams
        WHERE exam_date >= %s
    """, (today,))
    result = cursor.fetchone()

    next_date = result["next_date"]

    # Get exams of that date
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

    # ---------------- RENDER ----------------
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



# ---------------- CREATE EXAM SESSION ----------------
@app.route("/schedule_exam", methods=["POST"])
def schedule_exam():
    if session.get("role") != "admin":
        return redirect("/")

    exam_date = request.form.get("exam_date")
    exam_time = request.form.get("exam_time")
    course_code = request.form.get("course_code") # e.g., MCA
    subject_name = request.form.get("subject_name")

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            "INSERT INTO exams (exam_date, exam_time, course, subject_name) VALUES (%s, %s, %s, %s)",
            (exam_date, exam_time, course_code, subject_name)
        )
        db.commit()
    except Exception as e:
        print(f"Database Error: {e}")
    finally:
        cursor.close()
        db.close()

    return redirect("/schedule")

@app.route("/schedule")
def schedule():
    role = session.get("role")
    if not role:
        return redirect("/")

    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    schedule_data = []
    is_admin = (role == "admin") 

    if is_admin:
        # 🔥 Added 'id' here so we can delete specific rows
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
            # 🔥 Added 'id' here as well
            cursor.execute("""
                SELECT id, exam_date, exam_time AS time, subject_name AS subject 
                FROM exams WHERE UPPER(course) = UPPER(%s) ORDER BY exam_date ASC
            """, (student['branch'].strip(),))
            schedule_data = cursor.fetchall()

    cursor.close()
    db.close()
    return render_template("schedule.html", schedule=schedule_data, is_admin=is_admin)

@app.route("/delete_exam/<int:exam_id>")
def delete_exam(exam_id):
    if session.get("role") != "admin":
        return redirect("/")

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM exams WHERE id = %s", (exam_id,))
        db.commit()
    except Exception as e:
        print(f"Delete Error: {e}")
    finally:
        cursor.close()
        db.close()
    
    return redirect("/schedule")



# ---------------- STUDENTS ----------------

@app.route("/students", methods=["GET", "POST"])
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

        cursor.execute(
            "INSERT INTO students(name,roll,branch,subject,section,password) VALUES(%s,%s,%s,%s,%s,%s)",
            (name, roll, branch, subject, section, password)
        )

        db.commit()

    cursor.execute("SELECT * FROM students")
    students = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("students.html", students=students)


# ---------------- CSV BULK STUDENT UPLOAD ----------------

@app.route("/upload_students", methods=["POST"])
def upload_students():

    if "user" not in session:
        return redirect("/")

    file = request.files.get("file")

    if not file:
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

    except Exception as e:
        print("CSV Upload Error:", e)

    finally:
        cursor.close()
        db.close()

    return redirect("/students")

# ---------------- MANAGE COURSES (With Student Count) ----------------
@app.route("/manage_courses", methods=["GET", "POST"])
def manage_courses():
    if "user" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        code = request.form.get("course_code").upper().strip()
        name = request.form.get("course_name").strip()
        if code and name:
            cursor.execute("INSERT INTO courses (course_code, course_name) VALUES (%s, %s)", (code, name))
            db.commit()

    # Optimized Query: Counts students based on the 'branch' column
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

# ---------------- DELETE COURSE ROUTE ----------------
@app.route("/delete_course/<code>")
def delete_course(code):
    if "user" not in session:
        return redirect("/")
        
    db = get_db()
    cursor = db.cursor()
    # Delete the course using its code
    cursor.execute("DELETE FROM courses WHERE course_code = %s", (code,))
    db.commit()
    cursor.close()
    db.close()
    return redirect("/manage_courses")

# ---------------- TEACHERS ----------------

@app.route("/teachers", methods=["GET", "POST"])
def teachers_page():

    if "user" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":

        cursor.execute(
            "INSERT INTO teachers(name,subject) VALUES(%s,%s)",
            (request.form.get("name"), request.form.get("subject"))
        )

        db.commit()

    cursor.execute("SELECT * FROM teachers")
    teachers = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("teachers.html", teachers=teachers)


# ---------------- HALLS ----------------

@app.route("/halls", methods=["GET", "POST"])
def halls_page():

    if "user" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":

        cursor.execute(
            "INSERT INTO halls(hall,capacity) VALUES(%s,%s)",
            (request.form.get("hall"), request.form.get("capacity"))
        )

        db.commit()

    cursor.execute("SELECT * FROM halls")
    halls = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("halls.html", halls=halls)


# ---------------- ULTIMATE SEAT ALLOCATION (FINAL GOD TIER V2) ----------------


@app.route("/allocate", methods=["POST"])
def allocate_seats():
    if "user" not in session:
        return redirect("/")

    target_date = request.form.get("exam_date")
    if not target_date:
        return redirect("/seating")

    db = get_db()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("""
        SELECT s.*, e.subject_name AS exam_subject
        FROM students s
        JOIN exams e ON UPPER(s.branch) = UPPER(e.course)
        WHERE e.exam_date = %s
    """, (target_date,))
    students = cursor.fetchall()

    cursor.execute("SELECT * FROM halls")
    halls = cursor.fetchall()

    if not students or not halls:
        cursor.close()
        db.close()
        return redirect("/seating")

    from collections import defaultdict
    import random

    # --- RULE 1: GROUP STRICTLY BY COURSE (BRANCH), NOT SUBJECT ---
    # This ensures friends from the same course never sit together.
    branch_groups = defaultdict(list)
    for s in students:
        branch_groups[s["branch"]].append(s)

    for b in branch_groups:
        random.shuffle(branch_groups[b])

    # --- RULE 2: THE HARD MODE SWITCH ---
    # If there are only 1 or 2 courses scheduled, we MUST force physical gaps.
    num_courses = len(branch_groups.keys())
    is_strict_gap_mode = (num_courses <= 2)

    # --- PRE-FLIGHT CAPACITY CHECK ---
    total_capacity = sum(int(hall["capacity"]) for hall in halls)
    effective_capacity = total_capacity // 2 if is_strict_gap_mode else total_capacity

    if effective_capacity < len(students):
        cursor.close()
        db.close()
        mode_text = "STRICT GAP MODE (1-2 Courses)" if is_strict_gap_mode else "TIGHT PACK MODE (3+ Courses)"
        return f"""
            <div style="font-family: Arial; padding: 20px; color: #721c24; background-color: #f8d7da; border: 1px solid #f5c6cb; border-radius: 5px; margin: 20px; max-width: 600px;">
                <h3>🚨 CAPACITY ERROR</h3>
                <p>You have <b>{len(students)}</b> students, but only <b>{effective_capacity}</b> effective seats available under <b>{mode_text}</b>.</p>
                <a href="/seating" style="padding: 10px 15px; background: #dc3545; color: white; text-decoration: none; border-radius: 4px; display: inline-block; margin-top: 10px;">Go Back</a>
            </div>
        """

    arranged_seating = []
    row_size = 6  

    # --- HALL-BY-HALL ALLOCATION ---
    for hall in halls:
        capacity = int(hall["capacity"])
        hall_name = hall["hall"]
        
        hall_grid = {} 
        hall_priority = {b: random.random() for b in branch_groups.keys()}
        
        for seat_idx in range(capacity):
            if sum(len(g) for g in branch_groups.values()) == 0:
                break
                
            # 🔥 STRICT GAP ENFORCER FOR 1 OR 2 COURSES 🔥
            if is_strict_gap_mode and seat_idx % 2 != 0:
                hall_grid[seat_idx] = {"branch": "BLANK", "exam_subject": "BLANK"}
                continue
                
            row = seat_idx // row_size
            col = seat_idx % row_size
            
            # RADAR CHECKS FOR SAME BRANCH
            left_branch = hall_grid.get(seat_idx - 1, {}).get("branch") if col > 0 else None
            top_branch = hall_grid.get(seat_idx - row_size, {}).get("branch") if row > 0 else None
            top_left_branch = hall_grid.get(seat_idx - row_size - 1, {}).get("branch") if row > 0 and col > 0 else None
            top_right_branch = hall_grid.get(seat_idx - row_size + 1, {}).get("branch") if row > 0 and col < row_size - 1 else None
            
            available = [b for b in branch_groups if len(branch_groups[b]) > 0]
            available.sort(key=lambda x: (len(branch_groups[x]), hall_priority[x]), reverse=True)
            
            best_branch = None
            
            # Phase 1: Perfect placement
            for b in available:
                if b != left_branch and b != top_branch and b != top_left_branch and b != top_right_branch:
                    best_branch = b
                    break
                    
            # Phase 2: Acceptable placement
            if not best_branch:
                for b in available:
                    if b != left_branch and b != top_branch:
                        best_branch = b
                        break

            # 🔥 DYNAMIC OVERFLOW GAP (If 3+ courses somehow fail to shield) 🔥
            if not best_branch:
                hall_grid[seat_idx] = {"branch": "BLANK", "exam_subject": "BLANK"}
                continue 
                
            student = branch_groups[best_branch].pop(0)
            hall_grid[seat_idx] = student
            
            arranged_seating.append((hall_name, seat_idx + 1, student["name"], student["roll"], student["exam_subject"]))

    # --- POST-FLIGHT CHECK ---
    leftover_students = sum(len(g) for g in branch_groups.values())
    if leftover_students > 0:
        cursor.close()
        db.close()
        return f"<h3>🚨 ALLOCATION FAILED</h3><p>Could not seat <b>{leftover_students}</b> students. Physical gaps were injected to keep students from the same course separated, causing you to run out of seats.</p>"

    # --- DATABASE SAVE ---
    try:
        cursor.execute("""
            DELETE FROM seating 
            WHERE subject_name IN (SELECT subject_name FROM exams WHERE exam_date = %s)
        """, (target_date,))
        
        insert_query = "INSERT INTO seating (hall, seat, student, roll, subject_name) VALUES (%s, %s, %s, %s, %s)"
        cursor.executemany(insert_query, arranged_seating)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"CRITICAL DB ERROR: {e}")
    finally:
        cursor.close()
        db.close()

    return redirect("/seating")
        # -------CSV FILE GENERATED FOR NAMES FOR STUDENTS-----------

import csv
import random

first_names = [
    "Aarav","Vivaan","Aditya","Vihaan","Arjun","Sai","Reyansh","Krishna","Ishaan","Shaurya",
    "Ananya","Aadhya","Diya","Myra","Sara","Riya","Ira","Anika","Meera","Kavya",
    "Rohan","Kunal","Rahul","Amit","Siddharth","Varun","Nikhil","Dev","Yash","Aryan",
    "Pooja","Neha","Simran","Sneha","Priya","Kriti","Naina","Rashmi","Ishita","Tanvi"
]

last_names = [
    "Sharma","Verma","Gupta","Singh","Kumar","Joshi","Mehta","Agarwal","Jain","Chopra",
    "Malhotra","Kapoor","Bansal","Mittal","Saxena","Tiwari","Pandey","Rathore","Chauhan","Yadav"
]

def unique_name(used):
    while True:
        name = random.choice(first_names) + " " + random.choice(last_names)
        if name not in used:
            used.add(name)
            return name

used_names = set()

with open("students.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["name","roll","branch","subject","section","password"])

    courses = [
        ("MCA","MCA_SEM1","MCA"),
        ("BAJ","BAJMC_SEM1","BAJMC"),
        ("CSE","CSE_SEM1","BTECH-CSE"),
        ("IT","IT_SEM1","BTECH-IT")
    ]

    for code, subject, branch in courses:
        for i in range(1,121):

            name = unique_name(used_names)
            roll = f"{code}{i:03}"
            section = "A" if i <= 60 else "B"

            writer.writerow([name, roll, branch, subject, section, "123"])

print("CSV with unique names created!")
# ---------------- SEATING PAGE (FIX ADDED) ----------------

@app.route("/seating")
def seating_page():
    if "user" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
    SELECT seating.hall,
           seating.seat,
           seating.student,
           seating.roll,
           seating.subject_name AS display_subject,
           students.branch
    FROM seating
    JOIN students ON seating.roll = students.roll
    ORDER BY seating.hall, seating.seat
    """)

    seating = cursor.fetchall()
    cursor.close()
    db.close()

    return render_template("seating.html", seating=seating)



from datetime import datetime

# --- SMART INVIGILATOR ASSIGNMENT (Fair Workload) ---
@app.route("/assign_invigilators")
def assign_invigilators():
    if "user" not in session:
        return redirect("/")

    target_date = request.args.get("exam_date")
    if not target_date:
        return "<h3>Error:</h3><p>Please select an exam date first.</p>"

    db = get_db()
    cursor = db.cursor(dictionary=True, buffered=True)

    try:
        # 1. Find halls used on this specific date
        cursor.execute("""
            SELECT DISTINCT s.hall 
            FROM seating s
            JOIN exams e ON s.subject_name = e.subject_name
            WHERE e.exam_date = %s
        """, (target_date,))
        active_halls = [row['hall'] for row in cursor.fetchall()]

        if not active_halls:
            cursor.close(); db.close()
            return f"<h3>Allocation Error</h3><p>No students seated for {target_date}. Allocate seats first!</p>"

        # ---------------------------------------------------------
        # 🔥 IMPROVEMENT 1: BATCH UPDATE FOR THE RESET
        # ---------------------------------------------------------
        cursor.execute("SELECT teacher1, teacher2 FROM invigilation_assignments WHERE exam_date = %s", (target_date,))
        prev_rows = cursor.fetchall()
        
        prev_teachers = []
        for row in prev_rows:
            prev_teachers.extend([row['teacher1'], row['teacher2']])

        if prev_teachers:
            # Create a string of %s exactly as long as our teacher list (e.g., "%s, %s, %s")
            format_strings = ','.join(['%s'] * len(prev_teachers))
            # Execute ONE query instead of looping! (GREATEST(0) prevents negative workloads)
            cursor.execute(f"""
                UPDATE teachers 
                SET duties_assigned = GREATEST(0, duties_assigned - 1) 
                WHERE name IN ({format_strings})
            """, tuple(prev_teachers))

        # 3. Clear the table for this date only
        cursor.execute("DELETE FROM invigilation_assignments WHERE exam_date = %s", (target_date,))

        # 4. Fetch teachers sorted by LEAST workload (Fairness Algorithm)
        cursor.execute("SELECT * FROM teachers ORDER BY duties_assigned ASC")
        teachers = cursor.fetchall()

        if len(teachers) < len(active_halls) * 2:
            return f"<h3>Shortage Error:</h3><p>You need {len(active_halls) * 2} teachers for {len(active_halls)} halls, but only have {len(teachers)} available.</p>"

        assignments = []
        newly_assigned_names = []

        # 5. Assign 2 per hall
        for hall in active_halls:
            t1 = teachers.pop(0)
            t2 = teachers.pop(0)
            assignments.append((hall, t1['name'], t2['name'], target_date))
            newly_assigned_names.extend([t1['name'], t2['name']])

        # 6. Save Assignments
        insert_query = "INSERT INTO invigilation_assignments (hall_id, teacher1, teacher2, exam_date) VALUES (%s, %s, %s, %s)"
        cursor.executemany(insert_query, assignments)
        
        # ---------------------------------------------------------
        # 🔥 IMPROVEMENT 2: BATCH UPDATE FOR INCREMENTING
        # ---------------------------------------------------------
        if newly_assigned_names:
            format_strings = ','.join(['%s'] * len(newly_assigned_names))
            cursor.execute(f"""
                UPDATE teachers 
                SET duties_assigned = duties_assigned + 1 
                WHERE name IN ({format_strings})
            """, tuple(newly_assigned_names))
            
        db.commit()

    except Exception as e:
        db.rollback()
        # 🔥 IMPROVEMENT 3: Return the exact error to the UI instead of a silent print
        return f"<h3>Database Error:</h3><p>{e}</p>"
    finally:
        cursor.close()
        db.close()

    return redirect(f"/invigilation?exam_date={target_date}")

@app.route("/invigilation")
def invigilators_dashboard():
    if "user" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("SELECT DISTINCT exam_date FROM exams WHERE exam_date IS NOT NULL ORDER BY exam_date ASC")
    available_dates = [str(row['exam_date']) for row in cursor.fetchall()]

    selected_date = request.args.get("exam_date")
    if not selected_date and available_dates:
        selected_date = available_dates[0]

    assignments = []
    backups = []
    
    if selected_date:
        # Get assignments for the chosen date
        cursor.execute("SELECT * FROM invigilation_assignments WHERE exam_date = %s", (selected_date,))
        assignments = cursor.fetchall()

        # BACKUP LOGIC: Find teachers NOT in the assigned list for today
        assigned_today = []
        for a in assignments:
            assigned_today.extend([a['teacher1'], a['teacher2']])
            
        if assigned_today:
            placeholders = ','.join(['%s'] * len(assigned_today))
            # Increased limit to 10 so you can actually see them!
            cursor.execute(f"SELECT * FROM teachers WHERE name NOT IN ({placeholders}) ORDER BY duties_assigned ASC LIMIT 10", tuple(assigned_today))
        else:
            cursor.execute("SELECT * FROM teachers ORDER BY duties_assigned ASC LIMIT 10")
            
        backups = cursor.fetchall()

    # Get total stats for the workload table
    cursor.execute("SELECT name, duties_assigned FROM teachers ORDER BY duties_assigned DESC")
    workloads = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("invigilators.html", 
                           assignments=assignments, 
                           backups=backups, 
                           workloads=workloads, 
                           available_dates=available_dates, 
                           selected_date=selected_date)
#----------------VIRTUAL VIEW--------------

@app.route("/virtual_view")
def virtual_view():

    # ---------------- AUTH CHECK ----------------
    if "user" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor(dictionary=True, buffered=True)

    # ---------------- AVAILABLE EXAM DATES ----------------
    cursor.execute("SELECT DISTINCT exam_date FROM exams ORDER BY exam_date ASC")
    available_dates = [str(row['exam_date']) for row in cursor.fetchall() if row['exam_date']]

    # ---------------- SELECTED FILTERS ----------------
    selected_course = request.args.get("course", "").strip()
    selected_date = request.args.get("exam_date", "").strip()

    if not selected_date and available_dates:
        selected_date = available_dates[0]

    # ---------------- COURSES ----------------
    cursor.execute("SELECT * FROM courses")
    courses = cursor.fetchall()

    # ---------------- INVIGILATORS ----------------
    try:
        cursor.execute("SELECT * FROM invigilation_assignments")
        invig_map = {
            row['hall_id']: [row['teacher1'], row['teacher2']]
            for row in cursor.fetchall()
        }
    except:
        invig_map = {}

    # ---------------- FETCH SEATING ----------------
    query = """
        SELECT DISTINCT
            s.name, 
            s.roll, 
            s.branch, 
            st.subject_name, 
            st.hall, 
            st.seat
        FROM seating st
        JOIN students s ON st.roll = s.roll
        JOIN exams e ON UPPER(e.subject_name) = UPPER(st.subject_name)
        WHERE DATE(e.exam_date) = %s
        ORDER BY st.hall, st.seat
    """
    cursor.execute(query, (selected_date,))
    seating_results = cursor.fetchall()

    # ---------------- BACKUP TEACHERS ----------------
    cursor.execute("""
        SELECT name 
        FROM teachers 
        ORDER BY duties_assigned ASC 
        LIMIT 5
    """)
    backups = [t['name'] for t in cursor.fetchall()]

    # ---------------- CURRENT TIME ----------------
    from datetime import datetime
    current_time = datetime.now().strftime("%d %B, %Y | %I:%M %p")

    # 🔥 THE CRITICAL UPGRADE: Rebuilding the exact grid and injecting blanks 🔥
    temp_halls = {}
    for row in seating_results:
        hall_name = row['hall']
        if hall_name not in temp_halls:
            temp_halls[hall_name] = {'invigilators': invig_map.get(hall_name, ["TBD", "TBD"]), 'seats_map': {}}
        # Map each student to their exact physical seat number
        temp_halls[hall_name]['seats_map'][row['seat']] = row

    halls_dict = {}
    for h_name, data in temp_halls.items():
        # Find the highest seat number used in this hall
        max_seat = max(data['seats_map'].keys()) if data['seats_map'] else 0
        
        seat_list = []
        # Loop from Seat 1 up to the max seat
        for i in range(1, max_seat + 1):
            if i in data['seats_map']:
                seat_list.append(data['seats_map'][i])
            else:
                # If a seat number is missing from the DB, inject our BLANK placeholder!
                seat_list.append({"name": "Empty Desk", "roll": "---", "branch": "BLANK", "seat": i})
        
        halls_dict[h_name] = {'seats': seat_list, 'invigilators': data['invigilators']}

    # ---------------- CLEANUP ----------------
    cursor.close()
    db.close()

    # ---------------- RENDER ----------------
    return render_template(
        "virtual_view.html",
        halls=halls_dict,
        courses=courses,
        backups=backups,
        selected_course=selected_course,
        selected_date=selected_date,
        available_dates=available_dates,
        current_time=current_time
    )
# ---------------- PRINT ADMIT CARDS (NOW DYNAMIC) ----------------
@app.route("/print_admit_cards")
def print_admit_cards():
    # ---------------- AUTH CHECK ----------------
    if "user" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor(dictionary=True, buffered=True)

    # ---------------- COURSES FOR DROPDOWN ----------------
    cursor.execute("SELECT * FROM courses")
    courses = cursor.fetchall()

    selected_course = request.args.get("course", "").strip()

    # ---------------- FETCH ALL SEATING & EXAM DATA ----------------
    # We join exams to get the date, and we order by Roll Number so we can group them easily
    if selected_course:
        cursor.execute("""
            SELECT s.name, s.roll, s.branch, s.section,
                   st.subject_name, st.hall, st.seat, e.exam_date
            FROM seating st
            JOIN students s ON st.roll = s.roll
            JOIN exams e ON UPPER(st.subject_name) = UPPER(e.subject_name)
            WHERE UPPER(s.branch) = UPPER(%s)
            ORDER BY s.roll, e.exam_date ASC
        """, (selected_course,))
    else:
        cursor.execute("""
            SELECT s.name, s.roll, s.branch, s.section,
                   st.subject_name, st.hall, st.seat, e.exam_date
            FROM seating st
            JOIN students s ON st.roll = s.roll
            JOIN exams e ON UPPER(st.subject_name) = UPPER(e.subject_name)
            ORDER BY s.roll, e.exam_date ASC
        """)

    records = cursor.fetchall()

    # ---------------- GROUP DATA BY STUDENT ----------------
    # This is the magic fix! We group multiple subjects under the same Roll Number
    students_dict = {}
    
    for r in records:
        roll = r['roll']
        
        # If this is the first time seeing this student, create their profile
        if roll not in students_dict:
            students_dict[roll] = {
                "name": r["name"],
                "roll": r["roll"],
                "branch": r["branch"],
                "section": r["section"],
                "exams": [] # Empty list ready to hold their subjects
            }
        
        # Add the current exam subject/date/seat to their profile
        students_dict[roll]["exams"].append({
            "date": r["exam_date"],
            "subject": r["subject_name"],
            "hall": r["hall"],
            "seat": r["seat"]
        })

    # Convert the dictionary back into a simple list of students for the HTML
    students_list = list(students_dict.values())

    cursor.close()
    db.close()

    # ---------------- RENDER ----------------
    return render_template(
        "print_admit_cards.html", 
        students=students_list, 
        courses=courses, 
        selected_course=selected_course
    )

# ---------------- STUDENT ADMIT CARD (SAFE ADD) ----------------

@app.route("/student_admit_card")
def student_admit_card():
    if "student_roll" not in session:
        return redirect("/")

    roll = session["student_roll"]

    db = get_db()
    # 🔥 Use dictionary=True so we can easily access column names
    cursor = db.cursor(dictionary=True, buffered=True)

    # 🔥 NEW SQL: Fetches ALL seats for this student and gets the dates!
    cursor.execute("""
        SELECT s.name, s.roll, s.branch, s.section,
               st.subject_name, st.hall, st.seat, e.exam_date
        FROM seating st
        JOIN students s ON st.roll = s.roll
        JOIN exams e ON UPPER(st.subject_name) = UPPER(e.subject_name)
        WHERE s.roll = %s
        ORDER BY e.exam_date ASC
    """, (roll,))

    records = cursor.fetchall()

    # 🔥 SAFETY FIX: Prevent crash if student has no seat assigned yet
    if not records:
        cursor.close()
        db.close()
        return "Admit card or seating details not found. Please check back later.", 404

    # Group all the records into one student dictionary
    student_data = {
        "name": records[0]["name"],
        "roll": records[0]["roll"],
        "branch": records[0]["branch"],
        "section": records[0]["section"],
        "exams": []  # List to hold all subjects
    }

    # Add every exam to the list
    for r in records:
        student_data["exams"].append({
            "date": r["exam_date"],
            "subject": r["subject_name"],
            "hall": r["hall"],
            "seat": r["seat"]
        })

    cursor.close()
    db.close()

    # 🔥 Pass it in a list so it works with your new HTML loop
    return render_template("print_admit_cards.html", students=[student_data])

# ---------------- STUDENT PANEL ----------------
@app.route("/student_panel")
def student_panel():
    from datetime import datetime 

    if "student_roll" not in session:
        return redirect("/")

    roll = session["student_roll"]
    db = get_db()
    cursor = db.cursor(dictionary=True, buffered=True)

    # ---------------------------------------------------------
    # 🔥 FIX 1: Only get student info first (Don't grab seats blindly)
    # ---------------------------------------------------------
    cursor.execute("""
        SELECT name, roll, branch, section 
        FROM students 
        WHERE roll = %s
    """, (roll,))
    result = cursor.fetchone()

    if not result:
        cursor.close(); db.close()
        return render_template("student_panel.html", result=None, seating=[], show_seating=False)

    # ---------------------------------------------------------
    # 2. Find the exact Upcoming Exam
    # ---------------------------------------------------------
    upcoming_exam = None
    show_seating = False 
    exam_date_obj = None 

    if result.get("branch"):
        today = datetime.now().date()
        cursor.execute("""
            SELECT * FROM exams 
            WHERE UPPER(course) = UPPER(%s) 
            AND exam_date >= %s
            ORDER BY exam_date ASC 
            LIMIT 1
        """, (result["branch"].strip(), today))
        
        upcoming_exam = cursor.fetchone()

        if upcoming_exam:
            exam_date_val = upcoming_exam['exam_date']
            if isinstance(exam_date_val, str):
                exam_date_obj = datetime.strptime(exam_date_val, '%Y-%m-%d').date()
            else:
                exam_date_obj = exam_date_val
            
            days_left = (exam_date_obj - today).days
            # Temporarily set to 5 for your Viva testing. Change to 1 for real 24-hr lock!
            if days_left <= 5:  
                show_seating = True

    # ---------------------------------------------------------
    # 🔥 FIX 2: Now fetch the seat ONLY for this specific subject
    # ---------------------------------------------------------
    hall = None
    if upcoming_exam:
        cursor.execute("""
            SELECT hall, seat 
            FROM seating 
            WHERE roll = %s AND UPPER(TRIM(subject_name)) = UPPER(TRIM(%s))
        """, (roll, upcoming_exam['subject_name']))
        seat_data = cursor.fetchone()
        
        if seat_data:
            result['hall'] = seat_data['hall']
            result['seat'] = seat_data['seat']
            hall = seat_data['hall']
        else:
            result['hall'] = None
            result['seat'] = None

    # 3. Handle Locked State
    if not show_seating or not hall:
        if result:
            result['hall'] = "🔒"; result['seat'] = "🔒"
            result['row'] = "-"; result['column'] = "-"
        cursor.close(); db.close()
        return render_template("student_panel.html", result=result, seating=[], upcoming_exam=upcoming_exam, show_seating=show_seating)

    # ---------------------------------------------------------
    # 4. Generate the Grid (THE SQUISH FIX)
    # ---------------------------------------------------------
    db_date_str = exam_date_obj.strftime('%Y-%m-%d')

    cursor.execute("""
    SELECT DISTINCT s.name, s.roll, s.branch, st.seat
    FROM seating st
    JOIN students s ON st.roll = s.roll
    JOIN exams e ON UPPER(TRIM(st.subject_name)) = UPPER(TRIM(e.subject_name))
    WHERE TRIM(st.hall) = TRIM(%s) 
    AND DATE(e.exam_date) = %s
    ORDER BY st.seat
    """, (hall, db_date_str))

    raw_seating = cursor.fetchall()

    # ---------------------------------------------------------
    # 5. Grid Logic: Rebuild the FULL physical layout (including EMPTY seats)
    # ---------------------------------------------------------
    per_row = 6
    full_seating = []

    if raw_seating:
        # Find the highest seat number to know how big to make the grid
        max_seat = max(s['seat'] for s in raw_seating)
        # Round up to complete the final row (e.g., if max is 32, make it 36)
        remainder = max_seat % per_row
        total_slots = max_seat + (per_row - remainder) if remainder != 0 else max_seat

        # STEP A: Pre-fill the hall with empty chairs
        for i in range(1, total_slots + 1):
            full_seating.append({
                "name": "",
                "roll": "EMPTY",   # This will print "EMPTY" in the HTML box!
                "branch": "",
                "seat": i,
                "row": ((i - 1) // per_row) + 1,
                "column": ((i - 1) % per_row) + 1
            })

        # STEP B: Place the actual students in their assigned chairs
        for s in raw_seating:
            seat_idx = s['seat'] - 1  # Arrays start at 0, seats start at 1
            
            if s.get("branch"):
                s["branch"] = s["branch"].strip().upper()
                
            s["row"] = (seat_idx // per_row) + 1
            s["column"] = (seat_idx % per_row) + 1

            # Check if this is the logged-in student to lock their top Row/Col correctly
            if str(s["roll"]).strip().upper() == str(roll).strip().upper():
                result["row"] = s["row"]
                result["column"] = s["column"]

            # Drop the real student into the correct physical chair, replacing the dummy
            if seat_idx < len(full_seating):
                full_seating[seat_idx] = s

    cursor.close()
    db.close()

    return render_template(
        "student_panel.html",
        result=result,
        seating=full_seating, # 🔥 We are now passing the padded grid!
        upcoming_exam=upcoming_exam,
        show_seating=show_seating
    )
# -------- DELETE TEACHER --------
@app.route("/delete_teacher/<int:id>")
def delete_teacher(id):
    if "user" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM teachers WHERE id=%s", (id,))
    db.commit()
    cursor.close()
    db.close()

    return redirect("/teachers")


# -------- EDIT TEACHER --------
@app.route("/edit_teacher/<int:id>", methods=["GET", "POST"])
def edit_teacher(id):
    if "user" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        cursor.execute(
            "UPDATE teachers SET name=%s, subject=%s WHERE id=%s",
            (request.form.get("name"), request.form.get("subject"), id)
        )
        db.commit()
        return redirect("/teachers")

    cursor.execute("SELECT * FROM teachers WHERE id=%s", (id,))
    teacher = cursor.fetchone()

    cursor.close()
    db.close()

    return render_template("edit_teacher.html", teacher=teacher)


# -------- DELETE HALL --------
@app.route("/delete_hall/<int:id>")
def delete_hall(id):
    if "user" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM halls WHERE id=%s", (id,))
    db.commit()
    cursor.close()
    db.close()

    return redirect("/halls")


# -------- EDIT HALL --------
@app.route("/edit_hall/<int:id>", methods=["GET", "POST"])
def edit_hall(id):
    if "user" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        cursor.execute(
            "UPDATE halls SET hall=%s, capacity=%s WHERE id=%s",
            (request.form.get("hall"), request.form.get("capacity"), id)
        )
        db.commit()
        return redirect("/halls")

    cursor.execute("SELECT * FROM halls WHERE id=%s", (id,))
    hall = cursor.fetchone()

    cursor.close()
    db.close()

    return render_template("edit_hall.html", hall=hall)




@app.route("/setup_admin")
def setup_admin():
    from werkzeug.security import generate_password_hash
    db = get_db()
    cursor = db.cursor()
    
    # This generates the REAL mathematical hash for 'admin123'
    hashed_pw = generate_password_hash("admin123", method='pbkdf2:sha256')
    
    try:
        # Clears any broken admin accounts first
        cursor.execute("DELETE FROM admins WHERE username = 'admin'")
        # Inserts the real one
        cursor.execute("INSERT INTO admins (username, password_hash) VALUES (%s, %s)", ('admin', hashed_pw))
        db.commit()
        cursor.close()
        db.close()
        return "SUCCESS! Admin created. Go to /login and type: admin / admin123"
    except Exception as e:
        return f"Error: {e}"


# ---------------- RUN ----------------

if __name__ == "__main__":
    app.run(debug=True)