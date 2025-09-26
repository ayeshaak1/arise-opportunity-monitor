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
