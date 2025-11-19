# tests/test_check_for_changes.py
import os
import requests
import monitor

class MockResponse:
    def __init__(self, text, status_code=200, headers=None, url=None):
        self.status_code = status_code
        self.content = text.encode('utf-8')
        self.headers = headers or {}
        self.url = url or "https://link.arise.com/dashboard"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

class MockSession:
    def __init__(self):
        self.headers = {}
        self.timeout = None

    def post(self, url, data=None, allow_redirects=False, timeout=None):
        return MockResponse("", status_code=200, url="https://link.arise.com/dashboard")

    def get(self, url, timeout=None):
        return MockResponse(os.environ.get("CURRENT_HTML", ""), status_code=200)

def test_flow_no_data_to_opportunities(tmp_path, monkeypatch):
    # Work in a clean tmp dir so previous_state.txt is isolated
    monkeypatch.chdir(tmp_path)

    # Provide dummy credentials
    monkeypatch.setenv("ARISE_USERNAME", "dummy")
    monkeypatch.setenv("ARISE_PASSWORD", "dummy")

    # Replace requests.Session with our mock
    monkeypatch.setattr(requests, "Session", lambda: MockSession())

    notifications = []
    def fake_send_email_notification(message, opportunity_details=None, change_type=None):
        notifications.append((message, opportunity_details, change_type))
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

    # 2) Second run: page now contains opportunities -> should trigger notification
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
    message, details, change_type = notifications[0]
    assert "NEW OPPORTUNITIES" in message
    assert details is not None
    assert change_type == "new_opportunities"
