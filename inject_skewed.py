from db import get_db

db = get_db()
cursor = db.cursor()

# Edge Case 3: Highly Asymmetric Populations
cursor.execute("INSERT IGNORE INTO courses(course_code, course_name) VALUES ('SKEWED_A', 'Skewed A'), ('SKEWED_B', 'Skewed B')")
cursor.execute("INSERT IGNORE INTO exams(exam_date, exam_time, course, subject_name) VALUES ('2027-03-03', '10:00', 'SKEWED_A', 'Subject A'), ('2027-03-03', '10:00', 'SKEWED_B', 'Subject B')")

skewed_students = []
for i in range(150):
    skewed_students.append((f'Student SA{i}', f'SA{i}', 'SKEWED_A', 'Subject A', 'A', '123'))
for i in range(10):
    skewed_students.append((f'Student SB{i}', f'SB{i}', 'SKEWED_B', 'Subject B', 'A', '123'))

cursor.executemany("INSERT IGNORE INTO students(name, roll, branch, subject, section, password) VALUES (%s,%s,%s,%s,%s,%s)", skewed_students)

db.commit()
print('Asymmetric edge case data injected.')
