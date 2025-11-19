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
    assert "New opportunities available" in opportunities[0]

def test_extract_generic_opportunities():
    """Test that ANY content without 'No Data' means opportunities exist"""
    html = """
    <div id="opportunityannouncementwidget">
      <!-- No table, but also no "No Data" message -->
      <p>Some content here</p>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    opportunities, has = monitor.extract_opportunities(soup)
    assert has is True
    assert "New opportunities available" in opportunities[0]

def test_extract_empty_widget():
    """Test that an empty widget without 'No Data' still means opportunities exist"""
    html = """
    <div id="opportunityannouncementwidget">
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    opportunities, has = monitor.extract_opportunities(soup)
    assert has is True
    assert "New opportunities available" in opportunities[0]

def test_extract_no_widget():
    html = """
    <div id="otherwidget">
      <p>Some other content</p>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    opportunities, has = monitor.extract_opportunities(soup)
    assert opportunities == []
    assert has is False
