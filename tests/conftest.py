import sys
import os
import threading
import time
import requests
import socket

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from app import app as flask_app
from unittest.mock import MagicMock

@pytest.fixture(scope="session")
def app():
    flask_app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False
    })
    yield flask_app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def mock_db_connection(monkeypatch):
    mock_conn = MagicMock()
    monkeypatch.setattr("routes.auth.get_db", lambda: mock_conn)
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_cursor

# Custom threaded live server for Windows compatibility
@pytest.fixture(scope="session")
def threaded_live_server(app):
    # Find a free port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('localhost', 0))
    port = s.getsockname()[1]
    s.close()
    
    url = f"http://localhost:{port}"
    
    def run_server():
        # Disable werkzeug output for cleaner tests
        import logging
        log = logging.getLogger('werkzeug')
        log.disabled = True
        app.run(port=port, debug=False, use_reloader=False)
        
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    
    # Wait for server to be available
    start_time = time.time()
    while time.time() - start_time < 5:
        try:
            requests.get(url)
            break
        except requests.ConnectionError:
            time.sleep(0.1)
            
    yield url
