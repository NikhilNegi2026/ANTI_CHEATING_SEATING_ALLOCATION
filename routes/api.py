from flask import Blueprint, jsonify
from db import get_db

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

@api_bp.route("/students", methods=["GET"])
def get_all_students():
    """
    REST API Endpoint that returns a list of all students in JSON format.
    """
    db = get_db()
    cursor = db.cursor(dictionary=True, buffered=True)
    
    try:
        cursor.execute("SELECT roll, name, department, year FROM students")
        students = cursor.fetchall()
        
        return jsonify({
            "status": "success",
            "count": len(students),
            "data": students
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        cursor.close()
        db.close()
