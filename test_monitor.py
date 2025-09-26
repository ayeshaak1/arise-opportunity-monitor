import pytest
import os
import tempfile
import sys
from unittest.mock import Mock, patch, MagicMock
from bs4 import BeautifulSoup

# Add the project root to Python path so we can import monitor
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import monitor

# Test HTML samples
NO_DATA_HTML = """
<div id="opportunityannouncementwidget">
    <table class="table table-condensed">
        <tbody>
            <tr>
                <td colspan="3">
                    <h4 class="alert alert-warning">No Data</h4>
                </td>
            </tr>
        </tbody>
    </table>
</div>
"""

WITH_OPPORTUNITIES_HTML = """
<div id="opportunityannouncementwidget">
    <table class="table table-condensed">
        <thead>
            <tr>
                <th>Opportunity</th>
                <th>Download</th>
                <th>File Name</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Test Opportunity 1</td>
                <td><a class="orangetext" href="#">Download</a></td>
                <td>file1.pdf</td>
            </tr>
            <tr>
                <td>Test Opportunity 2</td>
                <td><a class="orangetext" href="#">Download</a></td>
                <td>file2.pdf</td>
            </tr>
        </tbody>
    </table>
</div>
"""

@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing"""
    with patch.dict(os.environ, {
        'ARISE_USERNAME': 'testuser',
        'ARISE_PASSWORD': 'testpass',
        'GMAIL_ADDRESS': 'test@test.com',
        'GMAIL_APP_PASSWORD': 'testpass'
    }):
        yield

@pytest.fixture
def temp_state_file():
    """Create a temporary state file for testing"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        temp_path = f.name
    yield temp_path
    # Clean up
    if os.path.exists(temp_path):
        os.unlink(temp_path)

def test_extract_opportunities_no_data():
    """Test extracting opportunities when no data is present"""
    soup = BeautifulSoup(NO_DATA_HTML, 'html.parser')
    opportunities, has_opportunities = monitor.extract_opportunities(soup)
    
    assert opportunities == []
    assert has_opportunities == False

def test_extract_opportunities_with_opportunities():
    """Test extracting opportunities when data is present"""
    soup = BeautifulSoup(WITH_OPPORTUNITIES_HTML, 'html.parser')
    opportunities, has_opportunities = monitor.extract_opportunities(soup)
    
    assert len(opportunities) == 2
    assert has_opportunities == True
    assert "Test Opportunity 1 - file1.pdf" in opportunities
    assert "Test Opportunity 2 - file2.pdf" in opportunities

def test_extract_opportunities_no_widget():
    """Test when opportunity widget is not found"""
    soup = BeautifulSoup("<html><body>No widget here</body></html>", 'html.parser')
    opportunities, has_opportunities = monitor.extract_opportunities(soup)
    
    assert opportunities == []
    assert has_opportunities == False

@patch('monitor.requests.Session')
@patch('monitor.send_email_notification')
def test_state_transition_no_data_to_opportunities(mock_email, mock_session, mock_env_vars, temp_state_file):
    """Test state transition from no data to opportunities"""
    # Mock the session and responses
    mock_session_instance = MagicMock()
    mock_session.return_value = mock_session_instance
    
    # Mock login response
    mock_session_instance.post.return_value.status_code = 302
    
    # Mock page response with opportunities
    mock_session_instance.get.return_value.status_code = 200
    mock_session_instance.get.return_value.content = WITH_OPPORTUNITIES_HTML.encode()
    
    # Mock the state file path
    with patch('monitor.open', create=True) as mock_open:
        # First call: no previous state file
        mock_open.side_effect = [
            FileNotFoundError(),  # First read fails (no file)
            MagicMock(),  # First write succeeds
        ]
        
        # Mock the file operations for the second call
        mock_open.side_effect = None
        mock_open.return_value.__enter__ = lambda self: self
        mock_open.return_value.__exit__ = Mock()
        mock_open.return_value.read.return_value = "abc123|NO_DATA|"
        mock_open.return_value.write = Mock()
        
        # Run the monitor (first run - should save state)
        result1 = monitor.check_for_changes()
        
        # Run again with different content (should detect change)
        result2 = monitor.check_for_changes()
        
        # Email should be sent on state change
        assert mock_email.called

@patch('monitor.smtplib.SMTP')
def test_email_sending(mock_smtp, mock_env_vars):
    """Test email sending functionality"""
    # Mock SMTP server
    mock_server = MagicMock()
    mock_smtp.return_value = mock_server
    
    # Test sending email
    result = monitor.send_email_notification("Test message", ["Opp 1 - file1.pdf"])
    
    assert result == True
    mock_smtp.assert_called_once_with('smtp.gmail.com', 587)
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once()
    mock_server.sendmail.assert_called_once()
    mock_server.quit.assert_called_once()

def test_state_file_operations(temp_state_file):
    """Test reading and writing state files"""
    # Test writing state
    test_state = "test_hash|OPPORTUNITIES_AVAILABLE|Test Opp 1 - file1.pdf,Test Opp 2 - file2.pdf"
    
    with open(temp_state_file, 'w') as f:
        f.write(test_state)
    
    # Test reading state
    with open(temp_state_file, 'r') as f:
        content = f.read()
    
    assert content == test_state

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
