from db import get_db

db = get_db()
cursor = db.cursor()

# 1. Edge Case: 0 Students
cursor.execute("INSERT IGNORE INTO courses(course_code, course_name) VALUES ('GHOST_COURSE', 'Ghost')")
cursor.execute("INSERT IGNORE INTO exams(exam_date, exam_time, course, subject_name) VALUES ('2027-01-01', '10:00', 'GHOST_COURSE', 'Ghost Subject')")

# 2. Edge Case: Capacity Exceeded (Strict Gap Mode)
cursor.execute("INSERT IGNORE INTO courses(course_code, course_name) VALUES ('HEAVY_A', 'Heavy A'), ('HEAVY_B', 'Heavy B')")
cursor.execute("INSERT IGNORE INTO exams(exam_date, exam_time, course, subject_name) VALUES ('2027-02-02', '10:00', 'HEAVY_A', 'Heavy Sub A'), ('2027-02-02', '10:00', 'HEAVY_B', 'Heavy Sub B')")

heavy_students = []
for i in range(200):
    heavy_students.append((f'Student HA{i}', f'HA{i}', 'HEAVY_A', 'Heavy Sub A', 'A', '123'))
for i in range(200):
    heavy_students.append((f'Student HB{i}', f'HB{i}', 'HEAVY_B', 'Heavy Sub B', 'A', '123'))

cursor.executemany("INSERT IGNORE INTO students(name, roll, branch, subject, section, password) VALUES (%s,%s,%s,%s,%s,%s)", heavy_students)

db.commit()
print('Edge case data injected.')
