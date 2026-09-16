from flask import Blueprint, render_template, request, redirect, session
from datetime import datetime, date
from db import get_db

student_bp = Blueprint('student', __name__)

@student_bp.route("/student_panel")
def student_panel():
    if "student_roll" not in session:
        return redirect("/")

    roll = session["student_roll"]
    db = get_db()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("""
        SELECT name, roll, branch, section 
        FROM students 
        WHERE roll = %s
    """, (roll,))
    result = cursor.fetchone()

    if not result:
        cursor.close()
        db.close()
        return render_template("student_panel.html", result=None, seating=[], show_seating=False)

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
            if days_left <= 1:  
                show_seating = True

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

    if not show_seating or not hall:
        if result:
            result['hall'] = "🔒"
            result['seat'] = "🔒"
            result['row'] = "-"
            result['column'] = "-"
        cursor.close()
        db.close()
        return render_template("student_panel.html", result=result, seating=[], upcoming_exam=upcoming_exam, show_seating=show_seating)

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

    per_row = 6
    full_seating = []

    if raw_seating:
        max_seat = max(s['seat'] for s in raw_seating)
        remainder = max_seat % per_row
        total_slots = max_seat + (per_row - remainder) if remainder != 0 else max_seat

        for i in range(1, total_slots + 1):
            full_seating.append({
                "name": "",
                "roll": "EMPTY",
                "branch": "",
                "seat": i,
                "row": ((i - 1) // per_row) + 1,
                "column": ((i - 1) % per_row) + 1
            })

        for s in raw_seating:
            seat_idx = s['seat'] - 1
            
            if s.get("branch"):
                s["branch"] = s["branch"].strip().upper()
                
            s["row"] = (seat_idx // per_row) + 1
            s["column"] = (seat_idx % per_row) + 1

            if str(s["roll"]).strip().upper() == str(roll).strip().upper():
                result["row"] = s["row"]
                result["column"] = s["column"]

            if seat_idx < len(full_seating):
                full_seating[seat_idx] = s

    cursor.close()
    db.close()

    return render_template(
        "student_panel.html",
        result=result,
        seating=full_seating,
        upcoming_exam=upcoming_exam,
        show_seating=show_seating
    )

@student_bp.route("/student_admit_card")
def student_admit_card():
    if "student_roll" not in session:
        return redirect("/")

    roll = session["student_roll"]

    db = get_db()
    cursor = db.cursor(dictionary=True, buffered=True)

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

    if not records:
        cursor.close()
        db.close()
        return "Admit card or seating details not found. Please check back later.", 404

    student_data = {
        "name": records[0]["name"],
        "roll": records[0]["roll"],
        "branch": records[0]["branch"],
        "section": records[0]["section"],
        "exams": []
    }

    today = datetime.now().date()
    for r in records:
        exam_date_val = r["exam_date"]
        if isinstance(exam_date_val, str):
            exam_date_obj = datetime.strptime(exam_date_val, '%Y-%m-%d').date()
        else:
            exam_date_obj = exam_date_val
            
        days_left = (exam_date_obj - today).days
        if days_left <= 1:
            hall_disp = r["hall"]
            seat_disp = r["seat"]
        else:
            hall_disp = "🔒 (24h Lock)"
            seat_disp = "🔒"

        student_data["exams"].append({
            "date": r["exam_date"],
            "subject": r["subject_name"],
            "hall": hall_disp,
            "seat": seat_disp
        })

    cursor.close()
    db.close()

    return render_template("print_admit_cards.html", students=[student_data])
