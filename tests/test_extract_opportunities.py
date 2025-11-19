# tests/test_extract_opportunities.py
from bs4 import BeautifulSoup
import monitor

def test_extract_no_data():
    html = """
    <div id="opportunityannouncementwidget">
      <h4 class="alert alert-warning">No Data</h4>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    opportunities, has = monitor.extract_opportunities(soup)
    assert opportunities == []
    assert has is False

def test_extract_table_opportunity():
    html = """
    <div id="opportunityannouncementwidget">
      <table>
        <tr><th>Opportunity</th><th>Download</th><th>File Name</th></tr>
        <tr>
          <td>Opportunity A</td>
          <td><a href="/dl">Download</a></td>
          <td>oppA.pdf</td>
        </tr>
      </table>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    opportunities, has = monitor.extract_opportunities(soup)
    assert has is True
    assert len(opportunities) == 1
    assert opportunities[0] == "Opportunity A - oppA.pdf"

def test_extract_script_opportunities():
    html = """
    <html>
        <script>
            var opportunityAnnouncementData = [
                {
                    "OpportunityName": "Script Opp 1",
                    "FileName": "script1.pdf",
                    "Download": "/download/1"
                },
                {
                    "OpportunityName": "Script Opp 2",
                    "FileName": "script2.pdf", 
                    "Download": "/download/2"
                }
            ];
        </script>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    opportunities, has = monitor.extract_opportunities_from_script_tags(soup)
    assert has is True
    assert len(opportunities) == 2
    assert "Script Opp 1 - script1.pdf" in opportunities
    assert "Script Opp 2 - script2.pdf" in opportunities

def test_extract_dynamic_content():
    html = """
    <div id="opportunityannouncementwidget">
        <a href="#">Download Opportunity File</a>
        <p>Check out this new opportunity!</p>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    opportunities, has = monitor.extract_opportunities_from_dynamic_content(soup)
    assert has is True
    assert "Opportunities available (details in portal)" in opportunities

def test_extract_mixed_content():
    html = """
    <html>
        <script>
            var portalSettings = {"user": "test"};
        </script>
        <div id="opportunityannouncementwidget">
            <table>
                <tr><th>Opportunity</th><th>Download</th><th>File Name</th></tr>
                <tr>
                    <td>Table Opportunity</td>
                    <td><a href="#">Download</a></td>
                    <td>table.pdf</td>
                </tr>
            </table>
        </div>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    opportunities, has = monitor.extract_opportunities(soup)
    assert has is True
    assert len(opportunities) == 1
    assert opportunities[0] == "Table Opportunity - table.pdf"
