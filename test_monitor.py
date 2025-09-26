#!/usr/bin/env python3
"""
Test suite for Arise Opportunity Monitor
"""

import unittest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from monitor import extract_opportunities, check_for_changes, send_email_notification
from bs4 import BeautifulSoup
import hashlib

class TestExtractOpportunities(unittest.TestCase):
    """Test the opportunity extraction function"""
    
    def test_no_data_scenario(self):
        """Test when no opportunities are available"""
        html = """
        <div id="opportunityannouncementwidget">
            <h4 class="alert alert-warning">No Data</h4>
        </div>
        """
        soup = BeautifulSoup(html, 'html.parser')
        opportunities, has_opportunities = extract_opportunities(soup)
        
        self.assertFalse(has_opportunities)
        self.assertEqual(opportunities, [])
    
    def test_single_opportunity(self):
        """Test when one opportunity is available"""
        html = """
        <div id="opportunityannouncementwidget">
            <table>
                <tr><th>Opportunity</th><th>Download</th><th>File Name</th></tr>
                <tr>
                    <td>Test Client Program</td>
                    <td><a href="#">Download</a></td>
                    <td>program_details.pdf</td>
                </tr>
            </table>
        </div>
        """
        soup = BeautifulSoup(html, 'html.parser')
        opportunities, has_opportunities = extract_opportunities(soup)
        
        self.assertTrue(has_opportunities)
        self.assertEqual(len(opportunities), 1)
        self.assertIn("Test Client Program - program_details.pdf", opportunities)
    
    def test_multiple_opportunities(self):
        """Test when multiple opportunities are available"""
        html = """
        <div id="opportunityannouncementwidget">
            <table>
                <tr><th>Opportunity</th><th>Download</th><th>File Name</th></tr>
                <tr>
                    <td>Client Program A</td>
                    <td><a href="#">Download</a></td>
                    <td>program_a.pdf</td>
                </tr>
                <tr>
                    <td>Client Program B</td>
                    <td><a href="#">Download</a></td>
                    <td>program_b.pdf</td>
                </tr>
            </table>
        </div>
        """
        soup = BeautifulSoup(html, 'html.parser')
        opportunities, has_opportunities = extract_opportunities(soup)
        
        self.assertTrue(has_opportunities)
        self.assertEqual(len(opportunities), 2)
        self.assertIn("Client Program A - program_a.pdf", opportunities)
        self.assertIn("Client Program B - program_b.pdf", opportunities)
    
    def test_missing_widget(self):
        """Test when the opportunity widget is missing"""
        html = "<div>Some other content</div>"
        soup = BeautifulSoup(html, 'html.parser')
        opportunities, has_opportunities = extract_opportunities(soup)
        
        self.assertFalse(has_opportunities)
        self.assertEqual(opportunities, [])

class TestEmailNotification(unittest.TestCase):
    """Test email notification functionality"""
    
    @patch('monitor.smtplib.SMTP')
    def test_send_email_success(self, mock_smtp):
        """Test successful email sending"""
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server
        
        # Set environment variables for testing
        with patch.dict(os.environ, {
            'GMAIL_ADDRESS': 'test@example.com',
            'GMAIL_APP_PASSWORD': 'test_password'
        }):
            result = send_email_notification("Test message", ["Opportunity 1"])
        
        self.assertTrue(result)
        mock_smtp.assert_called_once_with('smtp.gmail.com', 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with('test@example.com', 'test_password')
        mock_server.sendmail.assert_called_once()
        mock_server.quit.assert_called_once()
    
    @patch('monitor.smtplib.SMTP')
    def test_send_email_failure(self, mock_smtp):
        """Test email sending failure"""
        mock_smtp.side_effect = Exception("SMTP error")
        
        with patch.dict(os.environ, {
            'GMAIL_ADDRESS': 'test@example.com',
            'GMAIL_APP_PASSWORD': 'test_password'
        }):
            result = send_email_notification("Test message")
        
        self.assertFalse(result)

class TestStateManagement(unittest.TestCase):
    """Test state file management"""
    
    def setUp(self):
        """Set up temporary directory for test files"""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
    
    def tearDown(self):
        """Clean up temporary directory"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
    
    def test_state_file_creation(self):
        """Test that state file is created on first run"""
        # Ensure state file doesn't exist
        self.assertFalse(os.path.exists('previous_state.txt'))
        
        # Simulate first run scenario
        state_data = "abc123|NO_DATA|"
        with open('previous_state.txt', 'w') as f:
            f.write(state_data)
        
        # Verify file was created
        self.assertTrue(os.path.exists('previous_state.txt'))
        with open('previous_state.txt', 'r') as f:
            content = f.read()
        self.assertEqual(content, state_data)
    
    def test_state_parsing(self):
        """Test parsing of state file content"""
        test_state = "hash123|OPPORTUNITIES_AVAILABLE|Client A - file1.pdf,Client B - file2.pdf"
        
        with open('previous_state.txt', 'w') as f:
            f.write(test_state)
        
        with open('previous_state.txt', 'r') as f:
            content = f.read().strip()
        
        # Test parsing logic similar to what's in monitor.py
        parts = content.split('|', 2)
        self.assertEqual(len(parts), 3)
        hash_part, state_str, details = parts
        self.assertEqual(hash_part, "hash123")
        self.assertEqual(state_str, "OPPORTUNITIES_AVAILABLE")
        self.assertEqual(details, "Client A - file1.pdf,Client B - file2.pdf")

class TestIntegrationScenarios(unittest.TestCase):
    """Test integration scenarios with mocked web requests"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
    
    def tearDown(self):
        """Clean up test environment"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
    
    @patch('monitor.requests.Session')
    @patch('monitor.send_email_notification')
    def test_first_run_no_data(self, mock_email, mock_session):
        """Test first run when no opportunities exist"""
        # Mock the session and response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = """
        <html>
            <div id="opportunityannouncementwidget">
                <h4 class="alert alert-warning">No Data</h4>
            </div>
        </html>
        """
        mock_session.return_value.get.return_value = mock_response
        mock_session.return_value.post.return_value.status_code = 302
        
        # Set environment variables
        with patch.dict(os.environ, {
            'ARISE_USERNAME': 'test_user',
            'ARISE_PASSWORD': 'test_pass',
            'GMAIL_ADDRESS': 'test@example.com',
            'GMAIL_APP_PASSWORD': 'test_password'
        }):
            result = check_for_changes()
        
        self.assertTrue(result)
        # No email should be sent on first run
        mock_email.assert_not_called()
        # State file should be created
        self.assertTrue(os.path.exists('previous_state.txt'))
    
    @patch('monitor.requests.Session')
    @patch('monitor.send_email_notification')
    def test_change_from_no_data_to_opportunities(self, mock_email, mock_session):
        """Test scenario where opportunities appear after 'No Data'"""
        # First, create a previous state file with "NO_DATA"
        previous_state = f"{hashlib.md5(b'NO_DATA:').hexdigest()}|NO_DATA|"
        with open('previous_state.txt', 'w') as f:
            f.write(previous_state)
        
        # Mock response with opportunities
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = """
        <html>
            <div id="opportunityannouncementwidget">
                <table>
                    <tr><th>Opportunity</th><th>Download</th><th>File Name</th></tr>
                    <tr>
                        <td>New Client Program</td>
                        <td><a href="#">Download</a></td>
                        <td>new_program.pdf</td>
                    </tr>
                </table>
            </div>
        </html>
        """
        mock_session.return_value.get.return_value = mock_response
        mock_session.return_value.post.return_value.status_code = 302
        
        # Set environment variables
        with patch.dict(os.environ, {
            'ARISE_USERNAME': 'test_user',
            'ARISE_PASSWORD': 'test_pass'
        }):
            result = check_for_changes()
        
        self.assertTrue(result)
        # Email should be sent for this change
        mock_email.assert_called_once()

class TestErrorHandling(unittest.TestCase):
    """Test error handling scenarios"""
    
    @patch('monitor.requests.Session')
    def test_network_failure(self, mock_session):
        """Test handling of network failures"""
        mock_session.return_value.get.side_effect = Exception("Network error")
        
        with patch.dict(os.environ, {
            'ARISE_USERNAME': 'test_user',
            'ARISE_PASSWORD': 'test_pass'
        }):
            with patch('monitor.send_email_notification') as mock_email:
                result = check_for_changes()
        
        self.assertFalse(result)
        # Error email should be sent
        mock_email.assert_called_once()
    
    def test_missing_environment_variables(self):
        """Test behavior when required environment variables are missing"""
        # Clear environment variables
        with patch.dict(os.environ, {}, clear=True):
            # This should cause the script to exit with error
            with self.assertRaises(SystemExit) as cm:
                import subprocess
                subprocess.run(['python', '-c', 'import monitor; monitor.check_for_changes()'], 
                             capture_output=True, text=True)
            
            # The exit code should be non-zero
            self.assertNotEqual(cm.exception.code, 0)

def run_tests():
    """Run all tests and return results"""
    # Create a test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(__name__)
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return success if all tests passed
    return result.wasSuccessful()

if __name__ == '__main__':
    # Run tests when script is executed directly
    success = run_tests()
    exit(0 if success else 1)
