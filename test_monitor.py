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
        """Test extraction when opportunities are present (no 'No Data' message)"""
        soup = BeautifulSoup(HTML_WITH_OPPORTUNITIES, 'html.parser')
        opportunities, has_opportunities = monitor.extract_opportunities(soup)
        
        assert has_opportunities == True
        assert len(opportunities) == 1
        assert "New opportunities available" in opportunities[0]

    def test_extract_opportunities_widget_not_found(self):
        """Test extraction when widget is not present"""
        soup = BeautifulSoup(HTML_WITHOUT_WIDGET, 'html.parser')
        opportunities, has_opportunities = monitor.extract_opportunities(soup)
        
        assert opportunities == []
        assert has_opportunities == False

    def test_extract_opportunities_empty_widget(self):
        """Test extraction when widget exists but has no content"""
        html_empty_widget = """
        <html>
            <body>
                <div id="opportunityannouncementwidget">
                </div>
            </body>
        </html>
        """
        soup = BeautifulSoup(html_empty_widget, 'html.parser')
        opportunities, has_opportunities = monitor.extract_opportunities(soup)
        
        # No "No Data" message = opportunities exist
        assert has_opportunities == True
        assert "New opportunities available" in opportunities[0]

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
            
            result = monitor.send_email_notification(
                "Test message", 
                ["Opp 1", "Opp 2"],
                "new_opportunities"
            )
            
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

@patch('monitor.requests.Session')
@patch('monitor.send_email_notification')
@patch('builtins.open', new_callable=mock_open)
class TestIntegration:
    def test_successful_monitoring_flow(self, mock_file, mock_email, mock_session):
        """Test the complete monitoring flow"""
        # Mock the session and responses
        mock_session_instance = Mock()
        mock_session.return_value = mock_session_instance
        
        # Mock successful login - ensure response has text attribute
        mock_post_response = Mock()
        mock_post_response.status_code = 200
        mock_post_response.url = "https://link.arise.com/dashboard"
        mock_post_response.text = ""
        mock_post_response.content = b""
        
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.text = HTML_WITH_NO_DATA
        mock_get_response.content = HTML_WITH_NO_DATA.encode()
        mock_get_response.url = "https://link.arise.com/reference"
        
        mock_session_instance.post.return_value = mock_post_response
        mock_session_instance.get.return_value = mock_get_response
        
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

    def test_state_transitions_with_change_types(self, mock_file, mock_email, mock_session):
        """Test that different state transitions use correct change types"""
        mock_session_instance = Mock()
        mock_session.return_value = mock_session_instance
        
        # Mock responses with text attribute
        mock_post_response = Mock()
        mock_post_response.status_code = 200
        mock_post_response.url = "https://link.arise.com/dashboard"
        mock_post_response.text = ""
        mock_post_response.content = b""
        
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.text = HTML_WITH_OPPORTUNITIES
        mock_get_response.content = HTML_WITH_OPPORTUNITIES.encode()
        mock_get_response.url = "https://link.arise.com/reference"
        
        mock_session_instance.post.return_value = mock_post_response
        mock_session_instance.get.return_value = mock_get_response
        
        with patch.dict(os.environ, {
            'ARISE_USERNAME': 'testuser',
            'ARISE_PASSWORD': 'testpass'
        }):
            # Test NO_DATA -> OPPORTUNITIES_AVAILABLE should use "new_opportunities"
            mock_file.return_value.read.return_value = f"{hashlib.md5(b'NO_DATA:').hexdigest()}|NO_DATA|"
            
            result = monitor.check_for_changes()
            assert result == True
            
            # Check that email was called with new_opportunities change_type
            mock_email.assert_called_once()
            call_kwargs = mock_email.call_args[1]
            assert call_kwargs.get('change_type') == 'new_opportunities'

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
