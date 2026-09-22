import pytest

def test_api_get_students(client, monkeypatch, mock_db_connection):
    """
    Test the REST API endpoint that returns students in JSON format.
    """
    from unittest.mock import MagicMock
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_db_connection
    monkeypatch.setattr("routes.api.get_db", lambda: mock_conn)
    
    # 1. Setup our mock database to return two fake students
    mock_db_connection.fetchall.return_value = [
        {"roll": "CS01", "name": "Alice", "department": "Computer Science", "year": "2"},
        {"roll": "CS02", "name": "Bob", "department": "Computer Science", "year": "2"}
    ]

    # 2. Make a GET request to our new API endpoint
    response = client.get("/api/v1/students")

    # 3. Assert the HTTP Status Code is 200 OK
    assert response.status_code == 200

    # 4. Parse the JSON response
    json_data = response.json

    # 5. Assert the JSON structure is exactly what we expect from a REST API
    assert json_data["status"] == "success"
    assert json_data["count"] == 2
    assert len(json_data["data"]) == 2
    assert json_data["data"][0]["name"] == "Alice"
    assert json_data["data"][1]["name"] == "Bob"

    # Verify the database was queried correctly
    mock_db_connection.execute.assert_called_once()
    args = mock_db_connection.execute.call_args[0]
    assert "SELECT roll, name, department, year FROM students" in args[0]
