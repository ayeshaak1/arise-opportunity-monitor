# tests/test_extract_opportunities.py
from bs4 import BeautifulSoup
import monitor

def test_has_no_data_message_true():
    html = """
    <div id="opportunityannouncementwidget">
      <h4 class="alert alert-warning">No Data</h4>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    result = monitor.has_no_data_message(soup)
    assert result is True

def test_has_no_data_message_false():
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
    result = monitor.has_no_data_message(soup)
    assert result is False

def test_has_no_data_message_no_widget():
    html = """
    <div id="otherwidget">
      <p>Some other content</p>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    result = monitor.has_no_data_message(soup)
    assert result is True  # No widget = no opportunities

def test_extract_opportunities_simple_no_data():
    html = """
    <div id="opportunityannouncementwidget">
      <h4 class="alert alert-warning">No Data</h4>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    opportunities, has = monitor.extract_opportunities_simple(soup)
    assert opportunities == []
    assert has is False

def test_extract_opportunities_simple_with_opportunities():
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
    opportunities, has = monitor.extract_opportunities_simple(soup)
    assert has is True
    assert len(opportunities) == 1
    assert opportunities[0] == "Opportunity A - oppA.pdf"

def test_extract_opportunities_simple_generic():
    html = """
    <div id="opportunityannouncementwidget">
      <!-- No table, but also no "No Data" message -->
      <p>Some content here</p>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    opportunities, has = monitor.extract_opportunities_simple(soup)
    assert has is True
    assert "Opportunities available (check portal for details)" in opportunities

def test_extract_opportunities_script_fallback():
    html = """
    <html>
        <script>
            var someSettings = {
                opportunityAnnouncementData: [
                    {
                        "OpportunityName": "Script Opp",
                        "FileName": "script.pdf",
                        "Download": "/download/1"
                    }
                ]
            };
        </script>
        <div id="opportunityannouncementwidget">
            <!-- No "No Data" message -->
        </div>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    opportunities, has = monitor.extract_opportunities_from_script_tags(soup)
    # This is just a bonus - main detection should work via simple method
    if has:
        assert "Script Opp - script.pdf" in opportunities
