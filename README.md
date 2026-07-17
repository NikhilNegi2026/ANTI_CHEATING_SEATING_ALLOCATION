# Exam Seating & Invigilation System

This is a comprehensive web application designed to automate and optimize the process of assigning exam seats for students and allocating invigilation duties for teachers. Built with Python (Flask) and MySQL.

## Features

- **Smart Seat Allocation (The God Tier Algorithm)**: Automatically arranges students in examination halls. It intelligently groups students by branch and forces physical gaps between students of the same course to prevent cheating.
- **Fair Invigilator Assignment**: Assigns teachers to examination halls dynamically while tracking their workload to ensure duties are distributed fairly among all staff.
- **Admin & Student Panels**: 
  - Admins can manage courses, teachers, halls, schedules, and view all seating arrangements.
  - Students can log in to view their specific exam schedules.
- **Bulk Upload**: Import student details via CSV files.

## Tech Stack

- **Backend**: Python, Flask
- **Database**: MySQL
- **Frontend**: HTML, CSS (Jinja2 Templates)

## Setup Instructions

1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>
   cd SEM_2_PROJECT
   ```

2. **Set up a virtual environment (optional but recommended)**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables**:
   Copy `.env.example` to `.env` and configure your MySQL database credentials:
   ```bash
   cp .env.example .env
   ```
   Edit the `.env` file with your specific `DB_USER` and `DB_PASSWORD`.

5. **Database Setup**:
   Create a MySQL database named `exam_system` and import your schema (if you have an export). 

6. **Run the application**:
   ```bash
   python app.py
   ```
   Or run it using flask:
   ```bash
   flask run
   ```

## Author
[Your Name/Handle]
