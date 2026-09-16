import pytest
from werkzeug.security import generate_password_hash

def test_login_page_renders(client):
    """Test that the login page loads correctly via GET request"""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Login" in response.data

def test_login_missing_fields(client):
    """Test login fails when required fields are missing"""
    response = client.post("/", data={
        "role": "",
        "username": "",
        "password": ""
    })
    # Check if the page re-renders with an error message
    assert response.status_code == 200
    assert b"Please select a role and enter both username and password." in response.data

def test_admin_login_success(client, mock_db_connection):
    """Test successful admin login"""
    # Setup the mock database to return a valid admin user
    hashed_pw = generate_password_hash("admin123", method='pbkdf2:sha256')
    mock_db_connection.fetchone.return_value = {
        "username": "admin",
        "password_hash": hashed_pw
    }

    response = client.post("/", data={
        "role": "admin",
        "username": "admin",
        "password": "admin123"
    })
    
    # Should redirect to /dashboard
    assert response.status_code == 302
    assert "/dashboard" in response.headers["Location"]
    
    # Verify the database was queried correctly
    mock_db_connection.execute.assert_called_once()
    args = mock_db_connection.execute.call_args[0]
    assert "SELECT * FROM admins" in args[0]
    assert args[1] == ("admin",)

def test_student_login_success(client, mock_db_connection):
    """Test successful student login using roll number as password"""
    mock_db_connection.fetchone.return_value = {
        "roll": "MCA123",
        "password": None # Simulating a user who uses roll as password
    }

    response = client.post("/", data={
        "role": "student",
        "username": "mca123", # Test case insensitivity
        "password": "MCA123"
    })
    
    # Should redirect to /student_panel
    assert response.status_code == 302
    assert "/student_panel" in response.headers["Location"]

def test_student_login_invalid_password(client, mock_db_connection):
    """Test student login fails with incorrect password"""
    mock_db_connection.fetchone.return_value = {
        "roll": "MCA123",
        "password": "SecurePassword" 
    }

    response = client.post("/", data={
        "role": "student",
        "username": "MCA123",
        "password": "WrongPassword"
    })
    
    # Should stay on login page and show error
    assert response.status_code == 200
    assert b"Invalid Password" in response.data
