import pytest
from playwright.sync_api import Page, expect

def test_login_page_title(page: Page, threaded_live_server):
    """Test that the login page has the correct title"""
    page.goto(threaded_live_server)
    # The title of the login page should be "Anti-Cheating Seating Allocation - Login" or similar
    # We will just check if "Login" is somewhere in the page
    expect(page.locator("h2, h1").first).to_contain_text("Login", ignore_case=True)

def test_student_login_ui_flow(page: Page, threaded_live_server, mock_db_connection):
    """Test the student login flow through the UI"""
    # Setup mock for this test
    mock_db_connection.fetchone.return_value = {
        "roll": "TEST1234",
        "password": None
    }

    # Navigate to app
    page.goto(threaded_live_server)

    # Select role
    page.select_option("select[name='role']", "student")
    
    # Fill username and password
    page.fill("input[name='username']", "TEST1234")
    page.fill("input[name='password']", "TEST1234")
    
    # Click Login
    page.click("button[type='submit']")

    # Expect redirection to student panel (mock db allows login)
    expect(page).to_have_url(f"{threaded_live_server}/student_panel")
    
def test_invalid_login_shows_error(page: Page, threaded_live_server, mock_db_connection):
    """Test that invalid login displays an error message on the screen"""
    # Setup mock to return no user
    mock_db_connection.fetchone.return_value = None

    page.goto(threaded_live_server)
    page.select_option("select[name='role']", "admin")
    page.fill("input[name='username']", "wrong_user")
    page.fill("input[name='password']", "wrong_pass")
    page.click("button[type='submit']")

    # Expect to stay on the same page and see an error
    error_element = page.locator(".alert, .error, p.text-danger, p[style*='color: red']")
    # In case we don't know the exact class, we just check the body text for the error
    expect(page.locator("body")).to_contain_text("Invalid Admin Credentials", ignore_case=True)
