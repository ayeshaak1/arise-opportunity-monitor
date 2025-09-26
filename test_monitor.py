import unittest
from monitor import extract_opportunities
from bs4 import BeautifulSoup

class TestMonitor(unittest.TestCase):

    def test_no_opportunities_found(self):
        # HTML with the "No Data" message
        html_no_data = """
        <div id="opportunityannouncementwidget">
            <h4 class="alert alert-warning">No Data</h4>
        </div>
        """
        soup = BeautifulSoup(html_no_data, 'html.parser')
        opportunities, has_opportunities = extract_opportunities(soup)

        # Check that no opportunities are found
        self.assertFalse(has_opportunities)
        self.assertEqual(opportunities, [])

    def test_opportunities_found(self):
        # HTML with a sample opportunity
        html_with_opportunities = """
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
        soup = BeautifulSoup(html_with_opportunities, 'html.parser')
        opportunities, has_opportunities = extract_opportunities(soup)

        # Check that the opportunity is correctly identified
        self.assertTrue(has_opportunities)
        self.assertIn("Test Client Program - program_details.pdf", opportunities)

if __name__ == '__main__':
    unittest.main()
