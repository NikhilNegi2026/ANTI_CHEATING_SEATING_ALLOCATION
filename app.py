from flask import Flask
import os
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect

# Import blueprints
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.student import student_bp
from routes.seating import seating_bp

load_dotenv()

app = Flask(__name__)
csrf = CSRFProtect(app)

# Enforce secure secret key usage
secret_key = os.getenv("SECRET_KEY")
if not secret_key or secret_key == "fallback_secret_key":
    print("WARNING: Using an insecure fallback secret key! Please set SECRET_KEY in .env")
    app.secret_key = "fallback_secret_key"
else:
    app.secret_key = secret_key

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(student_bp)
app.register_blueprint(seating_bp)

if __name__ == "__main__":
    app.run(debug=True)