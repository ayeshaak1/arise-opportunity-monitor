# tests/test_check_for_changes.py
import os
import requests
import monitor
import pathlib

# Simple mock response/session for monitor.check_for_changes
class MockResponse:
    def __init__(self, text, status_code=200, headers=None):
        self.status_code = status_code
        self.content = text.encode('utf-8')
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

class MockSession:
    """
    A minimal stand-in for requests.Session used by the tests.
    It exposes 'headers' (a dict) so session.headers.update(...) works,
    and provides post/get methods returning MockResponse objects.
    """
    def __init__(self):
        # requests.Session has a headers dict attribute; mimic that
        self.headers = {}
        # allow test/code to set timeout attribute (monitor sets session.timeout)
        self.timeout = None

    def post(self, url, data=None, allow_redirects=False):
        # Simulate successful login (redirect or set-cookie)
        return MockResponse("", status_code=302, headers={"set-cookie": "session=1"})

    def get(self, url, timeout=None):
        # Use the global CURRENT_HTML that test sets before calling check_for_changes
        return MockResponse(os.environ.get("CURRENT_HTML", ""), status_code=200)

def test_flow_no_data_to_opportunities(tmp_path, monkeypatch):
    # Work in a clean tmp dir so previous_state.txt is isolated
    monkeypatch.chdir(tmp_path)

    # Provide dummy credentials so monitor tries to login (we've mocked session.post)
    monkeypatch.setenv("ARISE_USERNAME", "dummy")
    monkeypatch.setenv("ARISE_PASSWORD", "dummy")

    # Replace requests.Session with our mock that returns controlled HTML
    monkeypatch.setattr(requests, "Session", lambda: MockSession())

    notifications = []
    # Replace real email sending so tests don't send email
    def fake_send_email_notification(message, opportunity_details=None):
        notifications.append((message, opportunity_details))
        return True
    monkeypatch.setattr(monitor, "send_email_notification", fake_send_email_notification)

    # 1) First run: page shows "No Data" -> should initialize previous_state.txt and not notify
    os.environ["CURRENT_HTML"] = """
    <div id="opportunityannouncementwidget">
      <h4 class="alert alert-warning">No Data</h4>
    </div>
    """
    assert monitor.check_for_changes() is True
    # previous_state.txt should exist and contain "NO_DATA"
    p = tmp_path / "previous_state.txt"
    assert p.exists()
    body = p.read_text()
    assert "NO_DATA" in body
    assert len(notifications) == 0

    # 2) Second run: page now contains an opportunity -> should trigger notification
    os.environ["CURRENT_HTML"] = """
    <div id="opportunityannouncementwidget">
      <table>
        <tr><th>Opportunity</th><th>Download</th><th>File Name</th></tr>
        <tr>
          <td>Opportunity B</td>
          <td><a href="#">Download</a></td>
          <td>oppB.pdf</td>
        </tr>
      </table>
    </div>
    """
    assert monitor.check_for_changes() is True
    # Now notifications should have one entry for the transition
    assert len(notifications) == 1
    message, details = notifications[0]
    assert "NEW OPPORTUNITIES" in message or "NEW" in message or "Opportunities" in message
    assert details is not None
    assert any("Opportunity B" in item for item in details)
