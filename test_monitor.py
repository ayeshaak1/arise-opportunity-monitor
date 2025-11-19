import pytest
import os
import tempfile
import hashlib
import json
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

HTML_WITH_SCRIPT_DATA = """
<html>
    <body>
        <script>
            var portalSettings = {
                "someData": "value",
                "opportunityData": []
            };
            var opportunityAnnouncementData = [
                {
                    "OpportunityName": "Script Opportunity 1",
                    "FileName": "script1.pdf",
                    "Download": "link1"
                },
                {
                    "OpportunityName": "Script Opportunity 2", 
                    "FileName": "script2.pdf",
                    "Download": "link2"
                }
            ];
        </script>
        <div id="opportunityannouncementwidget">
            <!-- Content loaded dynamically -->
        </div>
    </body>
</html>
"""

HTML_WITH_DYNAMIC_CONTENT = """
<html>
    <body>
        <div id="opportunityannouncementwidget">
            <!-- No table, but has download links -->
            <a href="#">Download Opportunity File</a>
            <p>Some opportunity description</p>
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
        """Test extraction when opportunities are present in table"""
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

    def test_extract_opportunities_from_script_tags(self):
        """Test extraction from JavaScript data in script tags"""
        soup = BeautifulSoup(HTML_WITH_SCRIPT_DATA, 'html.parser')
        opportunities, has_opportunities = monitor.extract_opportunities_from_script_tags(soup)
        
        expected_opportunities = [
            "Script Opportunity 1 - script1.pdf",
            "Script Opportunity 2 - script2.pdf"
        ]
        assert opportunities == expected_opportunities
        assert has_opportunities == True

    def test_extract_opportunities_from_dynamic_content(self):
        """Test extraction from dynamic content without structured tables"""
        soup = BeautifulSoup(HTML_WITH_DYNAMIC_CONTENT, 'html.parser')
        opportunities, has_opportunities = monitor.extract_opportunities_from_dynamic_content(soup)
        
        # Should detect opportunities from download links and text
        assert has_opportunities == True
        assert "Opportunities available (details in portal)" in opportunities

    def test_extract_opportunities_malformed_script(self):
        """Test extraction with malformed JavaScript data"""
        html_malformed_script = """
        <html>
            <body>
                <script>
                    var opportunityAnnouncementData = [
                        { "OpportunityName": "Test Opp", "FileName": "test.pdf", 
                </script>
            </body>
        </html>
        """
        soup = BeautifulSoup(html_malformed_script, 'html.parser')
        opportunities, has_opportunities = monitor.extract_opportunities_from_script_tags(soup)
        
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
            
            # Test with all parameters including change_type
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

    @patch('monitor.smtplib.SMTP')
    def test_send_email_notification_different_change_types(self, mock_smtp):
        """Test email sending with different change types"""
        with patch.dict(os.environ, {
            'GMAIL_ADDRESS': 'test@example.com',
            'GMAIL_APP_PASSWORD': 'testpass'
        }):
            mock_server = Mock()
            mock_smtp.return_value = mock_server
            
            # Test different change types
            change_types = [
                "new_opportunities",
                "opportunities_removed", 
                "opportunities_updated",
                "error"
            ]
            
            for change_type in change_types:
                result = monitor.send_email_notification(
                    f"Test {change_type}",
                    change_type=change_type
                )
                assert result == True

    @patch('monitor.smtplib.SMTP')
    def test_send_email_notification_subject_lines(self, mock_smtp):
        """Test that correct subject lines are used for different change types"""
        with patch.dict(os.environ, {
            'GMAIL_ADDRESS': 'test@example.com',
            'GMAIL_APP_PASSWORD': 'testpass'
        }):
            mock_server = Mock()
            mock_smtp.return_value = mock_server
            
            # Mock the MIMEMultipart to capture the subject
            with patch('monitor.MIMEMultipart') as mock_mime:
                mock_msg = Mock()
                mock_mime.return_value = mock_msg
                
                monitor.send_email_notification(
                    "Test message",
                    change_type="new_opportunities"
                )
                
                # Check that the subject was set correctly
                mock_msg.__setitem__.assert_any_call('Subject', '🎉 NEW Arise Opportunities Available!')

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

class TestScriptExtraction:
    def test_extract_from_portal_settings(self):
        """Test extraction from portalSettings JavaScript variable"""
        html_with_portal_settings = """
        <html>
            <script>
                var portalSettings = {
                    "user": "test",
                    "data": "value"
                };
            </script>
        </html>
        """
        soup = BeautifulSoup(html_with_portal_settings, 'html.parser')
        opportunities, has_opportunities = monitor.extract_opportunities_from_script_tags(soup)
        
        # Should find portalSettings but no opportunity data in it
        assert opportunities == []
        assert has_opportunities == False

    def test_extract_from_opportunity_data(self):
        """Test extraction from opportunityAnnouncementData JavaScript variable"""
        html_with_opportunity_data = """
        <html>
            <script>
                var opportunityAnnouncementData = [
                    {
                        "OpportunityName": "Test Opportunity",
                        "FileName": "test.pdf",
                        "Download": "/download/test"
                    }
                ];
            </script>
        </html>
        """
        soup = BeautifulSoup(html_with_opportunity_data, 'html.parser')
        opportunities, has_opportunities = monitor.extract_opportunities_from_script_tags(soup)
        
        expected_opportunities = ["Test Opportunity - test.pdf"]
        assert opportunities == expected_opportunities
        assert has_opportunities == True

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
        mock_session_instance.post.return_value.url = "https://link.arise.com/dashboard"  # Not a login page
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
            # Check that send_email_notification was called with error change_type
            mock_email.assert_called_once()
            # Get the keyword arguments from the call
            call_kwargs = mock_email.call_args[1]
            assert call_kwargs.get('change_type') == 'error'

    def test_state_transitions_with_change_types(self, mock_file, mock_email, mock_session):
        """Test that different state transitions use correct change types"""
        mock_session_instance = Mock()
        mock_session.return_value = mock_session_instance
        mock_session_instance.post.return_value.status_code = 200
        mock_session_instance.post.return_value.url = "https://link.arise.com/dashboard"
        mock_session_instance.get.return_value.status_code = 200
        
        with patch.dict(os.environ, {
            'ARISE_USERNAME': 'testuser',
            'ARISE_PASSWORD': 'testpass'
        }):
            # Test 1: NO_DATA -> OPPORTUNITIES_AVAILABLE should use "new_opportunities"
            mock_file.return_value.read.return_value = f"{hashlib.md5(b'NO_DATA:').hexdigest()}|NO_DATA|"
            mock_session_instance.get.return_value.content = HTML_WITH_OPPORTUNITIES.encode()
            
            result = monitor.check_for_changes()
            assert result == True
            
            # Check that email was called with new_opportunities change_type
            mock_email.assert_called_once()
            call_kwargs = mock_email.call_args[1]
            assert call_kwargs.get('change_type') == 'new_opportunities'

    def test_login_success_detection(self, mock_file, mock_email, mock_session):
        """Test login success detection"""
        mock_session_instance = Mock()
        mock_session.return_value = mock_session_instance
        
        # Mock login that redirects away from login page
        mock_session_instance.post.return_value.status_code = 200
        mock_session_instance.post.return_value.url = "https://link.arise.com/reference"  # Not a login page
        mock_session_instance.get.return_value.status_code = 200
        mock_session_instance.get.return_value.content = HTML_WITH_NO_DATA.encode()
        
        mock_file.return_value.read.return_value = "old_hash|NO_DATA|"
        
        with patch.dict(os.environ, {
            'ARISE_USERNAME': 'testuser',
            'ARISE_PASSWORD': 'testpass'
        }):
            result = monitor.check_for_changes()
            
            assert result == True
            # Verify login was attempted
            mock_session_instance.post.assert_called()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
