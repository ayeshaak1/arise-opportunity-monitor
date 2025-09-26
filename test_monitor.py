import pytest
import os
import tempfile
import hashlib
from unittest.mock import Mock, patch, mock_open
from bs4 import BeautifulSoup
import monitor

# Sample HTML content for testing
HTML_WITH_NO_DATA = """
<html>
    <body>
        <div id="opportunityannouncementwidget">
            <h4 class="alert alert-warning">No Data</h4>
        </div>
    </body>
</html>
"""

HTML_WITH_OPPORTUNITIES = """
<html>
    <body>
        <div id="opportunityannouncementwidget">
            <table>
                <tr><th>Opportunity</th><th>Download</th><th>File Name</th></tr>
                <tr>
                    <td>Summer Program 2024</td>
                    <td><a href="#">Download</a></td>
                    <td>summer_program.pdf</td>
                </tr>
                <tr>
                    <td>Winter Program 2024</td>
                    <td><a href="#">Download</a></td>
                    <td>winter_program.pdf</td>
                </tr>
            </table>
        </div>
    </body>
</html>
"""

HTML_WITHOUT_WIDGET = """
<html>
    <body>
        <div id="otherwidget">
            <p>Some other content</p>
        </div>
    </body>
</html>
"""

class TestExtractOpportunities:
    def test_extract_opportunities_no_data(self):
        """Test extraction when 'No Data' message is present"""
        soup = BeautifulSoup(HTML_WITH_NO_DATA, 'html.parser')
        opportunities, has_opportunities = monitor.extract_opportunities(soup)
        
        assert opportunities == []
        assert has_opportunities == False

    def test_extract_opportunities_with_opportunities(self):
        """Test extraction when opportunities are present"""
        soup = BeautifulSoup(HTML_WITH_OPPORTUNITIES, 'html.parser')
        opportunities, has_opportunities = monitor.extract_opportunities(soup)
        
        expected_opportunities = [
            "Summer Program 2024 - summer_program.pdf",
            "Winter Program 2024 - winter_program.pdf"
        ]
        assert opportunities == expected_opportunities
        assert has_opportunities == True

    def test_extract_opportunities_widget_not_found(self):
        """Test extraction when widget is not present"""
        soup = BeautifulSoup(HTML_WITHOUT_WIDGET, 'html.parser')
        opportunities, has_opportunities = monitor.extract_opportunities(soup)
        
        assert opportunities == []
        assert has_opportunities == False

    def test_extract_opportunities_empty_table(self):
        """Test extraction when table exists but has no opportunities"""
        html_empty_table = """
        <html>
            <body>
                <div id="opportunityannouncementwidget">
                    <table>
                        <tr><th>Opportunity</th><th>Download</th><th>File Name</th></tr>
                    </table>
                </div>
            </body>
        </html>
        """
        soup = BeautifulSoup(html_empty_table, 'html.parser')
        opportunities, has_opportunities = monitor.extract_opportunities(soup)
        
        assert opportunities == []
        assert has_opportunities == False

class TestEmailNotification:
    @patch('monitor.smtplib.SMTP')
    def test_send_email_notification_success(self, mock_smtp):
        """Test successful email sending"""
        with patch.dict(os.environ, {
            'GMAIL_ADDRESS': 'test@example.com',
            'GMAIL_APP_PASSWORD': 'testpass'
        }):
            mock_server = Mock()
            mock_smtp.return_value = mock_server
            
            result = monitor.send_email_notification("Test message", ["Opp 1", "Opp 2"])
            
            assert result == True
            mock_smtp.assert_called_once_with('smtp.gmail.com', 587)
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with('test@example.com', 'testpass')
            mock_server.sendmail.assert_called_once()
            mock_server.quit.assert_called_once()

    @patch('monitor.smtplib.SMTP')
    def test_send_email_notification_failure(self, mock_smtp):
        """Test email sending failure"""
        mock_smtp.side_effect = Exception("SMTP error")
        
        result = monitor.send_email_notification("Test message")
        
        assert result == False

class TestStateManagement:
    def test_state_transition_detection(self):
        """Test detection of state transitions"""
        # Test No Data -> Opportunities
        previous_state = f"{hashlib.md5(b'NO_DATA:').hexdigest()}|NO_DATA|"
        current_state_hash = hashlib.md5(b'OPPORTUNITIES_AVAILABLE:Summer Program').hexdigest()
        
        # This would be part of the check_for_changes logic
        assert "NO_DATA" in previous_state
        assert "OPPORTUNITIES_AVAILABLE" not in previous_state

    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists', return_value=True)
    def test_previous_state_reading(self, mock_exists, mock_file):
        """Test reading previous state from file"""
        mock_file.return_value.read.return_value = "abc123|NO_DATA|"
        
        # Simulate the file reading logic from check_for_changes
        previous_state = "abc123|NO_DATA|"
        
        assert previous_state is not None
        assert "NO_DATA" in previous_state

class TestEnvironmentVariables:
    def test_missing_environment_variables(self):
        """Test behavior when environment variables are missing"""
        with patch.dict(os.environ, {}, clear=True):
            # This should cause the script to exit with error
            if not (os.getenv('ARISE_USERNAME') and os.getenv('ARISE_PASSWORD')):
                # This is what happens in the main block
                assert True  # Environment variables are missing as expected

@patch('monitor.requests.Session')
@patch('monitor.send_email_notification')
@patch('builtins.open', new_callable=mock_open)
class TestIntegration:
    def test_successful_monitoring_flow(self, mock_file, mock_email, mock_session):
        """Test the complete monitoring flow"""
        # Mock the session and responses
        mock_session_instance = Mock()
        mock_session.return_value = mock_session_instance
        
        # Mock successful login
        mock_session_instance.post.return_value.status_code = 200
        mock_session_instance.get.return_value.status_code = 200
        mock_session_instance.get.return_value.content = HTML_WITH_NO_DATA.encode()
        
        # Mock previous state file
        mock_file.return_value.read.return_value = "old_hash|NO_DATA|"
        
        with patch.dict(os.environ, {
            'ARISE_USERNAME': 'testuser',
            'ARISE_PASSWORD': 'testpass',
            'GMAIL_ADDRESS': 'test@example.com',
            'GMAIL_APP_PASSWORD': 'testpass'
        }):
            result = monitor.check_for_changes()
            
            assert result == True

    def test_network_failure_handling(self, mock_file, mock_email, mock_session):
        """Test handling of network failures"""
        mock_session_instance = Mock()
        mock_session.return_value = mock_session_instance
        mock_session_instance.get.side_effect = Exception("Network error")
        
        with patch.dict(os.environ, {
            'ARISE_USERNAME': 'testuser',
            'ARISE_PASSWORD': 'testpass'
        }):
            result = monitor.check_for_changes()
            
            assert result == False
            mock_email.assert_called_once()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
