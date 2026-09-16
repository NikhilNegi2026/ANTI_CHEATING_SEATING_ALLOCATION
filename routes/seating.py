from flask import Blueprint, render_template, request, redirect, session, flash
from collections import defaultdict
import random
from db import get_db

seating_bp = Blueprint('seating', __name__)

@seating_bp.route("/allocate", methods=["POST"])
def allocate_seats():
    if "user" not in session:
        return redirect("/")

    target_date = request.form.get("exam_date")
    if not target_date:
        flash("Please select an exam date.", "error")
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
        flash("No students scheduled or no halls available for this date.", "error")
        return redirect("/seating")

    # --- RULE 1: GROUP STRICTLY BY COURSE (BRANCH), NOT SUBJECT ---
    branch_groups = defaultdict(list)
    for s in students:
        branch_groups[s["branch"]].append(s)

    for b in branch_groups:
        random.shuffle(branch_groups[b])

    # --- RULE 2: THE HARD MODE SWITCH ---
    num_courses = len(branch_groups.keys())
    is_strict_gap_mode = (num_courses <= 2)

    # --- PRE-FLIGHT CAPACITY CHECK ---
    total_capacity = sum(int(hall["capacity"]) for hall in halls)
    effective_capacity = total_capacity // 2 if is_strict_gap_mode else total_capacity

    if effective_capacity < len(students):
        cursor.close()
        db.close()
        mode_text = "STRICT GAP MODE (1-2 Courses)" if is_strict_gap_mode else "TIGHT PACK MODE (3+ Courses)"
        flash(f"CAPACITY ERROR: You have {len(students)} students, but only {effective_capacity} effective seats available under {mode_text}.", "error")
        return redirect("/seating")

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
                
            if is_strict_gap_mode and seat_idx % 2 != 0:
                hall_grid[seat_idx] = {"branch": "BLANK", "exam_subject": "BLANK"}
                continue
                
            row = seat_idx // row_size
            col = seat_idx % row_size
            
            left_branch = hall_grid.get(seat_idx - 1, {}).get("branch") if col > 0 else None
            top_branch = hall_grid.get(seat_idx - row_size, {}).get("branch") if row > 0 else None
            top_left_branch = hall_grid.get(seat_idx - row_size - 1, {}).get("branch") if row > 0 and col > 0 else None
            top_right_branch = hall_grid.get(seat_idx - row_size + 1, {}).get("branch") if row > 0 and col < row_size - 1 else None
            
            available = [b for b in branch_groups if len(branch_groups[b]) > 0]
            available.sort(key=lambda x: (len(branch_groups[x]), hall_priority[x]), reverse=True)
            
            best_branch = None
            
            for b in available:
                if b != left_branch and b != top_branch and b != top_left_branch and b != top_right_branch:
                    best_branch = b
                    break
                    
            if not best_branch:
                for b in available:
                    if b != left_branch and b != top_branch:
                        best_branch = b
                        break

            if not best_branch:
                hall_grid[seat_idx] = {"branch": "BLANK", "exam_subject": "BLANK"}
                continue 
                
            student = branch_groups[best_branch].pop(0)
            hall_grid[seat_idx] = student
            
            arranged_seating.append((hall_name, seat_idx + 1, student["name"], student["roll"], student["exam_subject"]))

    leftover_students = sum(len(g) for g in branch_groups.values())
    if leftover_students > 0:
        cursor.close()
        db.close()
        flash(f"ALLOCATION FAILED: Could not seat {leftover_students} students due to anti-cheating gap constraints.", "error")
        return redirect("/seating")

    try:
        cursor.execute("""
            DELETE FROM seating 
            WHERE subject_name IN (SELECT subject_name FROM exams WHERE exam_date = %s)
        """, (target_date,))
        
        insert_query = "INSERT INTO seating (hall, seat, student, roll, subject_name) VALUES (%s, %s, %s, %s, %s)"
        cursor.executemany(insert_query, arranged_seating)
        db.commit()
        flash(f"Seats successfully allocated for {target_date}.", "success")
    except Exception as e:
        db.rollback()
        flash(f"CRITICAL DB ERROR: {e}", "error")
    finally:
        cursor.close()
        db.close()

    return redirect("/seating")

@seating_bp.route("/seating")
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

@seating_bp.route("/assign_invigilators")
def assign_invigilators():
    if "user" not in session:
        return redirect("/")

    target_date = request.args.get("exam_date")
    if not target_date:
        flash("Please select an exam date first.", "error")
        return redirect("/invigilation")

    db = get_db()
    cursor = db.cursor(dictionary=True, buffered=True)

    try:
        cursor.execute("""
            SELECT DISTINCT s.hall 
            FROM seating s
            JOIN exams e ON s.subject_name = e.subject_name
            WHERE e.exam_date = %s
        """, (target_date,))
        active_halls = [row['hall'] for row in cursor.fetchall()]

        if not active_halls:
            cursor.close()
            db.close()
            flash(f"No students seated for {target_date}. Allocate seats first!", "error")
            return redirect("/invigilation")

        cursor.execute("SELECT teacher1, teacher2 FROM invigilation_assignments WHERE exam_date = %s", (target_date,))
        prev_rows = cursor.fetchall()
        
        prev_teachers = []
        for row in prev_rows:
            prev_teachers.extend([row['teacher1'], row['teacher2']])

        if prev_teachers:
            format_strings = ','.join(['%s'] * len(prev_teachers))
            cursor.execute(f"""
                UPDATE teachers 
                SET duties_assigned = GREATEST(0, duties_assigned - 1) 
                WHERE name IN ({format_strings})
            """, tuple(prev_teachers))

        cursor.execute("DELETE FROM invigilation_assignments WHERE exam_date = %s", (target_date,))
        cursor.execute("SELECT * FROM teachers ORDER BY duties_assigned ASC")
        teachers = cursor.fetchall()

        if len(teachers) < len(active_halls) * 2:
            flash(f"Shortage Error: You need {len(active_halls) * 2} teachers, but only have {len(teachers)} available.", "error")
            return redirect("/invigilation")

        assignments = []
        newly_assigned_names = []

        for hall in active_halls:
            t1 = teachers.pop(0)
            t2 = teachers.pop(0)
            assignments.append((hall, t1['name'], t2['name'], target_date))
            newly_assigned_names.extend([t1['name'], t2['name']])

        insert_query = "INSERT INTO invigilation_assignments (hall_id, teacher1, teacher2, exam_date) VALUES (%s, %s, %s, %s)"
        cursor.executemany(insert_query, assignments)
        
        if newly_assigned_names:
            format_strings = ','.join(['%s'] * len(newly_assigned_names))
            cursor.execute(f"""
                UPDATE teachers 
                SET duties_assigned = duties_assigned + 1 
                WHERE name IN ({format_strings})
            """, tuple(newly_assigned_names))
            
        db.commit()
        flash(f"Invigilators successfully assigned for {target_date}.", "success")

    except Exception as e:
        db.rollback()
        flash(f"Database Error: {e}", "error")
    finally:
        cursor.close()
        db.close()

    return redirect(f"/invigilation?exam_date={target_date}")

@seating_bp.route("/invigilation")
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
        cursor.execute("SELECT * FROM invigilation_assignments WHERE exam_date = %s", (selected_date,))
        assignments = cursor.fetchall()

        assigned_today = []
        for a in assignments:
            assigned_today.extend([a['teacher1'], a['teacher2']])
            
        if assigned_today:
            placeholders = ','.join(['%s'] * len(assigned_today))
            cursor.execute(f"SELECT * FROM teachers WHERE name NOT IN ({placeholders}) ORDER BY duties_assigned ASC LIMIT 10", tuple(assigned_today))
        else:
            cursor.execute("SELECT * FROM teachers ORDER BY duties_assigned ASC LIMIT 10")
            
        backups = cursor.fetchall()

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

@seating_bp.route("/virtual_view")
def virtual_view():
    if "user" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("SELECT DISTINCT exam_date FROM exams ORDER BY exam_date ASC")
    available_dates = [str(row['exam_date']) for row in cursor.fetchall() if row['exam_date']]

    selected_course = request.args.get("course", "").strip()
    selected_date = request.args.get("exam_date", "").strip()

    if not selected_date and available_dates:
        selected_date = available_dates[0]

    cursor.execute("SELECT * FROM courses")
    courses = cursor.fetchall()

    try:
        cursor.execute("SELECT * FROM invigilation_assignments")
        invig_map = {
            row['hall_id']: [row['teacher1'], row['teacher2']]
            for row in cursor.fetchall()
        }
    except:
        invig_map = {}

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

    cursor.execute("""
        SELECT name 
        FROM teachers 
        ORDER BY duties_assigned ASC 
        LIMIT 5
    """)
    backups = [t['name'] for t in cursor.fetchall()]

    from datetime import datetime
    current_time = datetime.now().strftime("%d %B, %Y | %I:%M %p")

    temp_halls = {}
    for row in seating_results:
        hall_name = row['hall']
        if hall_name not in temp_halls:
            temp_halls[hall_name] = {'invigilators': invig_map.get(hall_name, ["TBD", "TBD"]), 'seats_map': {}}
        temp_halls[hall_name]['seats_map'][row['seat']] = row

    halls_dict = {}
    for h_name, data in temp_halls.items():
        max_seat = max(data['seats_map'].keys()) if data['seats_map'] else 0
        
        seat_list = []
        for i in range(1, max_seat + 1):
            if i in data['seats_map']:
                seat_list.append(data['seats_map'][i])
            else:
                seat_list.append({"name": "Empty Desk", "roll": "---", "branch": "BLANK", "seat": i})
        
        halls_dict[h_name] = {'seats': seat_list, 'invigilators': data['invigilators']}

    cursor.close()
    db.close()

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

@seating_bp.route("/print_admit_cards")
def print_admit_cards():
    if "user" not in session:
        return redirect("/")

    db = get_db()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("SELECT * FROM courses")
    courses = cursor.fetchall()

    selected_course = request.args.get("course", "").strip()

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

    students_dict = {}
    for r in records:
        roll = r['roll']
        if roll not in students_dict:
            students_dict[roll] = {
                "name": r["name"],
                "roll": r["roll"],
                "branch": r["branch"],
                "section": r["section"],
                "exams": []
            }
        students_dict[roll]["exams"].append({
            "date": r["exam_date"],
            "subject": r["subject_name"],
            "hall": r["hall"],
            "seat": r["seat"]
        })

    students_list = list(students_dict.values())

    cursor.close()
    db.close()

    return render_template(
        "print_admit_cards.html", 
        students=students_list, 
        courses=courses, 
        selected_course=selected_course
    )
