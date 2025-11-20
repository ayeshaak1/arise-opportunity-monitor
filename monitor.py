import requests
from bs4 import BeautifulSoup
import hashlib
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import sys
import requests.packages.urllib3
import re

requests.packages.urllib3.disable_warnings()  # Disable SSL warnings for speed

# Set shorter timeouts for faster failure
REQUEST_TIMEOUT = 10  # seconds

# Set up logging to see what's happening
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to import Selenium for OAuth handling (optional)
try:
    from monitor_selenium import handle_oauth_login_selenium
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logger.debug("Selenium not available, using requests-only OAuth")

def send_email_notification(message, opportunity_details=None, change_type="new_opportunities"):
    """
    Sends an email notification using Gmail's SMTP server.
    """
    sender_email = os.getenv('GMAIL_ADDRESS')
    sender_password = os.getenv('GMAIL_APP_PASSWORD')
    receiver_email = sender_email  # Send the alert to yourself

    # Create the email message with specific subject based on change type
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    
    # Different subject lines based on the type of change
    subject_lines = {
        "new_opportunities": "🎉 NEW Arise Opportunities Available!",
        "opportunities_removed": "⚠️ Arise Opportunities Removed", 
        "opportunities_updated": "📊 Arise Opportunities Updated",
        "error": "❌ Arise Monitor Error"
    }
    
    msg['Subject'] = subject_lines.get(change_type, "🚨 Arise Opportunity Alert")
    
    # Build the email body
    email_body = message + "\n\n"
    
    if opportunity_details:
        email_body += "📋 AVAILABLE OPPORTUNITIES:\n"
        for opportunity in opportunity_details:
            email_body += f"  • {opportunity}\n"
        email_body += "\n"
    
    email_body += "🔗 Direct Link: https://link.arise.com/reference\n\n"
    
    # Different footer messages based on change type
    if change_type == "new_opportunities":
        email_body += "This alert was triggered because new opportunities became available!"
    elif change_type == "opportunities_removed":
        email_body += "All previous opportunities have been removed from the Program Announcement section."
    elif change_type == "opportunities_updated":
        email_body += "The available opportunities have been updated or modified."
    else:
        email_body += "This is an automated alert from your Arise Opportunity Monitor."

    msg.attach(MIMEText(email_body, 'plain'))

    try:
        # Connect to Gmail's SMTP server and send the email
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()  # Upgrade the connection to secure
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, receiver_email, text)
        server.quit()
        logger.info("✅ Email notification sent successfully!")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send email: {e}")
        return False

def extract_opportunities(soup):
    """
    SUPER SIMPLE CHECK: Look for "No Data" message in the entire page.
    If "No Data" is found in the opportunity widget → no opportunities
    If "No Data" is NOT found → opportunities exist
    """
    # Try multiple ways to find the widget
    opportunity_widget = None
    
    # Method 1: Look for div with id containing 'opportunityannouncementwidget'
    opportunity_widget = soup.find('div', id=lambda x: x and 'opportunityannouncementwidget' in x.lower())
    
    # Method 2: If not found, look for div with class containing 'opportunityannouncementwidget'
    if not opportunity_widget:
        def class_matcher(class_attr):
            if not class_attr:
                return False
            if isinstance(class_attr, list):
                return any('opportunityannouncementwidget' in str(c).lower() for c in class_attr)
            return 'opportunityannouncementwidget' in str(class_attr).lower()
        opportunity_widget = soup.find('div', class_=class_matcher)
    
    # Method 3: Look for the widget by searching for "Program Announcement" text nearby
    if not opportunity_widget:
        program_announcement = soup.find(string=lambda text: text and 'Program Announcement' in text)
        if program_announcement:
            # Find the parent div that likely contains the widget
            parent = program_announcement.find_parent('div')
            if parent:
                opportunity_widget = parent.find('div', id=lambda x: x and 'opportunityannouncementwidget' in x.lower() if x else False)
    
    # Method 4: Search for the widget template or script tag that references it
    if not opportunity_widget:
        # Look for script tags or templates that mention the widget
        widget_scripts = soup.find_all('script', string=lambda text: text and 'opportunityannouncementwidget' in text.lower() if text else False)
        if widget_scripts:
            # Try to find the widget div near these scripts
            for script in widget_scripts:
                parent = script.find_parent()
                if parent:
                    opportunity_widget = parent.find('div', id=lambda x: x and 'opportunityannouncementwidget' in x.lower() if x else False)
                    if opportunity_widget:
                        break
    
    # Method 5: Search more broadly - look for any div with "opportunity" and "announcement" in id or class
    if not opportunity_widget:
        all_divs = soup.find_all('div')
        for div in all_divs:
            div_id = div.get('id', '').lower()
            div_class = ' '.join(div.get('class', [])).lower() if div.get('class') else ''
            if 'opportunity' in div_id and 'announcement' in div_id:
                opportunity_widget = div
                logger.info(f"Found widget via broad search: id={div.get('id')}")
                break
            elif 'opportunity' in div_class and 'announcement' in div_class:
                opportunity_widget = div
                logger.info(f"Found widget via class search: class={div.get('class')}")
                break
    
    if not opportunity_widget:
        logger.info("📭 Opportunity widget not found - trying fallback method")
        # Fallback: Check the entire page for "No Data" in context of opportunities
        page_text = soup.get_text()
        # Look for "No Data" near opportunity-related terms
        if 'No Data' in page_text and ('opportunity' in page_text.lower() or 'announcement' in page_text.lower()):
            logger.info("📭 'No Data' found in page context - NO opportunities available")
            return [], False
        else:
            # If we can't find the widget but also can't confirm "No Data", 
            # we should log a warning but assume no opportunities to be safe
            logger.warning("⚠️  Widget not found and cannot determine opportunity status - assuming NO_DATA")
            return [], False
    
    widget_id = opportunity_widget.get('id', 'unknown id')
    logger.info(f"✅ Found opportunity widget: {widget_id}")
    
    # Get ALL text from the widget (simple approach)
    widget_text = opportunity_widget.get_text()
    logger.info(f"Widget text length: {len(widget_text)} characters")
    logger.debug(f"Widget text preview: {widget_text[:300]}...")
    
    # Check if widget is in loading state (has loading image or "Loading" text)
    loading_indicators = opportunity_widget.find_all('img', src=lambda x: x and 'clock_graphic' in x.lower() if x else False)
    if loading_indicators:
        logger.warning("⚠️  Widget appears to be in loading state - content may not be fully loaded")
        logger.warning("⚠️  This may require JavaScript execution (Selenium/Playwright) to get accurate results")
    
    # Check for "No Data" in multiple ways:
    # 1. Direct text content
    # 2. In any h4 tags with alert-warning class
    # 3. In table empty state messages
    
    no_data_found = False
    
    # Check direct text
    if 'No Data' in widget_text:
        no_data_found = True
        logger.info("📭 'No Data' found in widget text")
    
    # Check for h4 with alert-warning class containing "No Data"
    no_data_h4 = opportunity_widget.find_all('h4', class_=lambda x: x and 'alert' in ' '.join(x).lower() if isinstance(x, list) else 'alert' in str(x).lower() if x else False)
    for h4 in no_data_h4:
        if 'No Data' in h4.get_text():
            no_data_found = True
            logger.info("📭 'No Data' found in alert h4 tag")
            break
    
    # Check DataTables empty state (might be in script tags or data attributes)
    if not no_data_found:
        # Look for DataTables configuration that might indicate empty state
        scripts = soup.find_all('script', string=lambda text: text and 'sEmptyTable' in text if text else False)
        for script in scripts:
            if 'No Data' in script.string and 'opportunity' in script.string.lower():
                no_data_found = True
                logger.info("📭 'No Data' found in DataTables configuration")
                break
    
    if no_data_found:
        logger.info("📭 'No Data' message found - NO opportunities available")
        return [], False
    else:
        # Check if widget has any actual content (not just loading state)
        # Look for tables with data rows
        tables = opportunity_widget.find_all('table')
        has_table_data = False
        for table in tables:
            rows = table.find_all('tr')
            # If we have more than just header rows, there might be data
            if len(rows) > 1:
                # Check if any row has actual data (not just headers)
                for row in rows[1:]:  # Skip header row
                    cells = row.find_all(['td', 'th'])
                    if cells and any(cell.get_text(strip=True) for cell in cells):
                        has_table_data = True
                        break
                if has_table_data:
                    break
        
        if has_table_data or widget_text.strip() and 'Loading' not in widget_text:
            logger.info("🎯 Widget has content - checking for opportunities...")
            # Try to extract opportunity details from tables
            opportunities = extract_opportunity_details(opportunity_widget)
            if not opportunities:
                opportunities = ["New opportunities available - check Arise portal for details"]
            logger.info(f"📋 Extracted opportunities: {opportunities}")
            return opportunities, True
        else:
            # Widget exists but appears empty or in loading state
            logger.warning("⚠️  Widget found but appears empty or in loading state")
            logger.warning("⚠️  This may indicate JavaScript needs to execute to load content")
            logger.warning("⚠️  Assuming NO_DATA for safety (may need Selenium/Playwright for accurate detection)")
            return [], False

def find_widget_api_endpoint(soup, session):
    """
    Try to find the API endpoint that loads opportunity widget data.
    Returns the endpoint URL if found, None otherwise.
    """
    # Look for JavaScript variables or API calls that might load widget data
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string:
            # Look for API endpoints related to opportunities
            import re
            # Common patterns for API endpoints
            patterns = [
                r'/api/[^"\']*opportunity[^"\']*',
                r'/Reference/[^"\']*opportunity[^"\']*',
                r'/Widget/[^"\']*opportunity[^"\']*',
            ]
            for pattern in patterns:
                matches = re.findall(pattern, script.string, re.IGNORECASE)
                if matches:
                    endpoint = matches[0]
                    if not endpoint.startswith('http'):
                        endpoint = 'https://link.arise.com' + endpoint
                    logger.info(f"🔍 Found potential API endpoint: {endpoint}")
                    return endpoint
    return None

def extract_opportunity_details(widget):
    """
    Try to extract specific opportunity details from tables
    Returns only the opportunity name (first column), not the file name
    """
    opportunities = []
    
    # Look for tables in the widget
    tables = widget.find_all('table')
    for table in tables:
        # Look for table rows (skip header row)
        rows = table.find_all('tr')[1:]  # Skip the first header row
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 1:  # At least the Opportunity column
                opportunity_name = cells[0].get_text(strip=True)
                
                if opportunity_name and opportunity_name != "No Data" and len(opportunity_name) > 0:
                    # Only add the opportunity name, not the file name
                    opportunities.append(opportunity_name)
    
    return opportunities

def handle_oauth_login(session, username, password):
    """
    Handle the OAuth login flow for Arise portal
    """
    # Step 1: Start at the main portal page to get redirected to OAuth
    logger.info("🔄 Starting OAuth login flow...")
    initial_response = session.get('https://link.arise.com/', allow_redirects=True, timeout=REQUEST_TIMEOUT)
    
    # Step 2: We should be redirected to the OAuth login page
    if 'oauth.arise.com' in initial_response.url:
        logger.info(f"🔐 Redirected to OAuth login: {initial_response.url}")
        soup = BeautifulSoup(initial_response.content, 'html.parser')
        
        # Look for the login form on the OAuth page
        login_form = soup.find('form')
        if login_form:
            form_action = login_form.get('action', '')
            logger.info(f"🔐 Found login form with action: {form_action}")
            
            # Submit login credentials to the OAuth endpoint
            login_data = {
                'Username': username,
                'Password': password,
                'button': 'login'
            }
            
            # If there are any hidden fields, include them
            hidden_fields = login_form.find_all('input', {'type': 'hidden'})
            for field in hidden_fields:
                name = field.get('name')
                value = field.get('value', '')
                if name:
                    login_data[name] = value
            
            # Post to the OAuth login endpoint
            oauth_login_url = form_action
            if not oauth_login_url.startswith('http'):
                oauth_login_url = 'https://oauth.arise.com' + oauth_login_url
                
            logger.info(f"🔐 Posting login to OAuth endpoint: {oauth_login_url}")
            login_response = session.post(oauth_login_url, data=login_data, allow_redirects=False, timeout=REQUEST_TIMEOUT)
            
            if login_response.status_code in [302, 303] and 'Location' in login_response.headers:
                redirect_url = login_response.headers['Location']
                logger.info(f"✅ OAuth login successful, redirecting to: {redirect_url}")
                
                # Make the redirect URL absolute if it's relative
                if redirect_url.startswith('/'):
                    redirect_url = 'https://oauth.arise.com' + redirect_url
                elif not redirect_url.startswith('http'):
                    redirect_url = 'https://oauth.arise.com/' + redirect_url
                
                # Follow all redirects to get to the final page
                logger.info(f"🔄 Following redirect to: {redirect_url}")
                final_response = session.get(redirect_url, allow_redirects=True, timeout=REQUEST_TIMEOUT)
                logger.info(f"🏁 Final URL after redirects: {final_response.url}")
                
                # Check if we need to handle OAuth consent form
                if 'connect/authorize' in final_response.url:
                    logger.info("🔐 Handling OAuth authorization form...")
                    return handle_oauth_authorization(session, final_response)
                else:
                    return final_response
            else:
                logger.error(f"❌ OAuth login failed with status: {login_response.status_code}")
                return None
        else:
            logger.error("❌ Could not find login form on OAuth page")
            return None
    else:
        logger.info("ℹ️  Not redirected to OAuth, using direct login")
        return None

def handle_oauth_authorization(session, auth_response):
    """
    Handle the OAuth authorization form submission
    Based on user feedback: submitting the form logs them out, but they can access after re-login.
    So we'll try to skip the form submission and directly access the portal.
    """
    soup = BeautifulSoup(auth_response.content, 'html.parser')
    
    # First, check if we're already redirected or can access the portal directly
    # Sometimes the authorization is already complete and we just need to follow redirects
    # Check if the URL actually starts with link.arise.com (not just contains it in query params)
    from urllib.parse import urlparse
    parsed_url = urlparse(auth_response.url)
    if parsed_url.netloc == 'link.arise.com':
        logger.info("✅ Already redirected to portal, following redirects...")
        portal_response = session.get(auth_response.url, allow_redirects=True, timeout=REQUEST_TIMEOUT)
        logger.info(f"🏁 Final portal URL: {portal_response.url}")
        return portal_response
    
    # Check if there's a meta refresh or JavaScript redirect in the page
    meta_refresh = soup.find('meta', attrs={'http-equiv': 'refresh'})
    if meta_refresh:
        content = meta_refresh.get('content', '')
        # Extract URL from meta refresh (format: "0;url=https://...")
        import re
        url_match = re.search(r'url=(.+)', content, re.IGNORECASE)
        if url_match:
            redirect_url = url_match.group(1)
            logger.info(f"🔍 Found meta refresh redirect to: {redirect_url}")
            portal_response = session.get(redirect_url, allow_redirects=True, timeout=REQUEST_TIMEOUT)
            logger.info(f"🏁 Final portal URL: {portal_response.url}")
            return portal_response
    
    # Look for the authorization form
    auth_form = soup.find('form')
    if auth_form:
        form_action = auth_form.get('action', '')
        logger.info(f"🔐 Found OAuth authorization form with action: {form_action}")
        
        # Based on user feedback: submitting the form logs them out
        # So we'll try to skip form submission and access portal directly
        logger.info("🔍 Attempting direct portal access without form submission (form submission causes logout)")
        try:
            portal_response = session.get('https://link.arise.com/home', allow_redirects=True, timeout=REQUEST_TIMEOUT)
            parsed_portal_url = urlparse(portal_response.url)
            if parsed_portal_url.netloc == 'link.arise.com' and 'login' not in portal_response.url.lower():
                logger.info("✅ Successfully accessed portal without form submission")
                logger.info(f"🏁 Final portal URL: {portal_response.url}")
                return portal_response
            else:
                logger.info(f"⚠️  Direct access redirected to: {portal_response.url}, will try form submission")
        except Exception as e:
            logger.debug(f"Direct access failed: {e}, will try form submission")
        
        # Extract all form fields (hidden and visible)
        form_data = {}
        form_inputs = auth_form.find_all('input')
        for input_field in form_inputs:
            name = input_field.get('name')
            value = input_field.get('value', '')
            if name:
                form_data[name] = value
        
        logger.info(f"🔐 Submitting OAuth authorization with {len(form_data)} fields")
        
        # Submit the authorization form
        if not form_action.startswith('http'):
            form_action = 'https://oauth.arise.com' + form_action
        
        # Add Referer header to make the request look more legitimate
        headers = {
            'Referer': auth_response.url,
            'Origin': 'https://oauth.arise.com'
        }
            
        auth_submit_response = session.post(form_action, data=form_data, headers=headers, allow_redirects=False, timeout=REQUEST_TIMEOUT)
        
        # Debug: Save the response for inspection if it's an error
        if auth_submit_response.status_code >= 400:
            debug_file = os.path.join(os.path.dirname(__file__), 'debug_oauth_response.html')
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(auth_submit_response.text)
            logger.debug(f"💾 Saved OAuth response to {debug_file} for inspection")
        
        # Check if response_mode is form_post - in this case, the response might contain a form that auto-submits
        # The response might be HTML with a form that posts to the portal
        # Even if we get a 500 error, the response body might contain the form we need
        if auth_submit_response.status_code in [200, 500]:
            # Check if response contains a form that posts to link.arise.com
            response_soup = BeautifulSoup(auth_submit_response.content, 'html.parser')
            auto_submit_form = response_soup.find('form', action=lambda x: x and 'link.arise.com' in x if x else False)
            if auto_submit_form:
                logger.info("🔍 Found auto-submit form in response (form_post mode)")
                # Extract form data and submit it
                auto_form_data = {}
                for input_field in auto_submit_form.find_all('input'):
                    name = input_field.get('name')
                    value = input_field.get('value', '')
                    if name:
                        auto_form_data[name] = value
                
                form_action_url = auto_submit_form.get('action', '')
                if not form_action_url.startswith('http'):
                    form_action_url = 'https://link.arise.com' + form_action_url
                
                logger.info(f"🔐 Submitting auto-form to: {form_action_url}")
                portal_response = session.post(form_action_url, data=auto_form_data, allow_redirects=True, timeout=REQUEST_TIMEOUT)
                parsed_portal_url = urlparse(portal_response.url)
                if parsed_portal_url.netloc == 'link.arise.com' and 'login' not in portal_response.url.lower():
                    logger.info("✅ Successfully accessed portal via auto-submit form")
                    logger.info(f"🏁 Final portal URL: {portal_response.url}")
                    return portal_response
        
        # Check for redirect
        if auth_submit_response.status_code in [302, 303] and 'Location' in auth_submit_response.headers:
            redirect_url = auth_submit_response.headers['Location']
            logger.info(f"✅ OAuth authorization successful, redirecting to: {redirect_url}")
            
            # Make the redirect URL absolute if it's relative
            if redirect_url.startswith('/'):
                redirect_url = 'https://oauth.arise.com' + redirect_url
            elif not redirect_url.startswith('http'):
                redirect_url = 'https://oauth.arise.com/' + redirect_url
            
            # Follow the final redirect to the actual portal
            logger.info(f"🔄 Following final redirect to portal: {redirect_url}")
            portal_response = session.get(redirect_url, allow_redirects=True, timeout=REQUEST_TIMEOUT)
            logger.info(f"🏁 Final portal URL: {portal_response.url}")
            return portal_response
        elif auth_submit_response.status_code == 200:
            # Sometimes successful authorization returns 200 with redirect in content
            logger.info("🔍 Got 200 response, checking for redirect in content...")
            # Try to access portal directly
            portal_response = session.get('https://link.arise.com/home', allow_redirects=True, timeout=REQUEST_TIMEOUT)
            parsed_portal_url = urlparse(portal_response.url)
            if parsed_portal_url.netloc == 'link.arise.com' and 'login' not in portal_response.url.lower():
                logger.info("✅ Successfully accessed portal after authorization")
                logger.info(f"🏁 Final portal URL: {portal_response.url}")
                return portal_response
            else:
                logger.warning(f"⚠️  Portal access redirected to: {portal_response.url}")
        else:
            logger.warning(f"⚠️  OAuth authorization returned status: {auth_submit_response.status_code}")
            # Even if we get an error, the authorization might have completed
            # Based on user feedback: form submission logs them out, but they can access after re-login
            # So let's try accessing the portal anyway - the session might still be valid
            logger.info("🔄 Attempting portal access after form submission (authorization may have completed despite error)...")
            try:
                # Try accessing the portal - sometimes the form submission works even with 500 error
                portal_response = session.get('https://link.arise.com/home', allow_redirects=True, timeout=REQUEST_TIMEOUT)
                parsed_portal_url = urlparse(portal_response.url)
                if parsed_portal_url.netloc == 'link.arise.com' and 'login' not in portal_response.url.lower():
                    logger.info("✅ Successfully accessed portal after form submission (despite error response)")
                    logger.info(f"🏁 Final portal URL: {portal_response.url}")
                    return portal_response
                else:
                    logger.warning(f"⚠️  Portal access redirected to: {portal_response.url}")
                    # If we're redirected to login, the form submission did log us out
                    # In this case, we'd need to re-authenticate, but that's complex
                    # For now, return None and let the main function handle it
            except Exception as e:
                logger.debug(f"Portal access failed: {e}")
            return None
    else:
        logger.warning("⚠️  No authorization form found - trying direct portal access")
        # No form found, try accessing portal directly
        try:
            portal_response = session.get('https://link.arise.com/home', allow_redirects=True, timeout=REQUEST_TIMEOUT)
            parsed_portal_url = urlparse(portal_response.url)
            if parsed_portal_url.netloc == 'link.arise.com' and 'login' not in portal_response.url.lower():
                logger.info("✅ Successfully accessed portal without authorization form")
                logger.info(f"🏁 Final portal URL: {portal_response.url}")
                return portal_response
        except Exception as e:
            logger.debug(f"Direct access failed: {e}")
        logger.error("❌ Could not find OAuth authorization form and direct access failed")
        return None

def check_for_changes():
    """
    Main function to check for opportunity changes on the Arise portal.
    """
    # Create a session to maintain login state
    session = requests.Session()
    session.timeout = REQUEST_TIMEOUT
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    })

    # Get credentials from environment variables
    arise_username = os.getenv('ARISE_USERNAME')
    arise_password = os.getenv('ARISE_PASSWORD')

    if not arise_username or not arise_password:
        logger.error("❌ Missing ARISE_USERNAME or ARISE_PASSWORD environment variables")
        return False

    # STEP 1: Handle OAuth login
    logger.info("Attempting to log in...")
    oauth_result = handle_oauth_login(session, arise_username, arise_password)
    
    login_successful = False
    
    if oauth_result and oauth_result.status_code == 200:
        # Check if we're actually on a logged-in page (not a login page)
        final_url = oauth_result.url
        if 'link.arise.com' in final_url and 'login' not in final_url.lower():
            logger.info("✅ OAuth login successful! Reached the portal.")
            login_successful = True
        else:
            logger.warning(f"⚠️  OAuth login may have failed - final URL: {final_url}")
    else:
        logger.warning("⚠️  OAuth login failed or returned unexpected response")
    
    # If requests-based OAuth failed, try Selenium as fallback
    if not login_successful and SELENIUM_AVAILABLE:
        logger.info("🔄 Requests-based OAuth failed, trying Selenium-based OAuth...")
        try:
            selenium_session, selenium_url = handle_oauth_login_selenium(arise_username, arise_password, headless=True)
            if selenium_session and selenium_url:
                if 'link.arise.com' in selenium_url and 'login' not in selenium_url.lower():
                    logger.info("✅ Selenium OAuth login successful! Reached the portal.")
                    session = selenium_session  # Use the Selenium session
                    login_successful = True
                else:
                    logger.warning(f"⚠️  Selenium OAuth may have failed - final URL: {selenium_url}")
        except Exception as e:
            logger.error(f"❌ Selenium OAuth failed: {e}")
    
    if not login_successful:
        logger.error("❌ All login attempts failed!")
        send_email_notification("Arise monitor authentication failed - check your credentials", change_type="error")
        return False

    # STEP 2: Access the references page
    target_url = "https://link.arise.com/reference"
    logger.info("Fetching the references page...")
    
    try:
        # If we used Selenium for login, try using it for the reference page too (to handle JavaScript)
        use_selenium_for_page = SELENIUM_AVAILABLE and login_successful
        current_opportunities = []
        has_opportunities_now = False
        
        if use_selenium_for_page:
            logger.info("🌐 Using Selenium to load reference page (JavaScript execution needed)...")
            try:
                from monitor_selenium import get_reference_page_with_selenium
                widget_soup, has_opportunities_from_selenium, opportunity_names_from_selenium = get_reference_page_with_selenium(session, headless=True)
                
                if widget_soup:
                    # Use Selenium result directly (it's more reliable for JavaScript-rendered content)
                    has_opportunities_now = has_opportunities_from_selenium
                    logger.info(f"📊 Selenium detected opportunities: {has_opportunities_now}")
                    
                    # Try to extract opportunity details if opportunities exist
                    if has_opportunities_now:
                        # Use opportunity names from Selenium extraction if available
                        if opportunity_names_from_selenium:
                            current_opportunities = opportunity_names_from_selenium
                            logger.info(f"📋 Using opportunity names from Selenium: {current_opportunities}")
                        else:
                            # Fallback to regular extraction
                            current_opportunities, _ = extract_opportunities(widget_soup)
                            if not current_opportunities:
                                # If we can't extract details, use a generic message
                                current_opportunities = ["New opportunities available - check Arise portal for details"]
                    else:
                        current_opportunities = []
                    
                    # Still get the full page for other checks
                    page_response = session.get(target_url, timeout=REQUEST_TIMEOUT)
                    soup = BeautifulSoup(page_response.content, 'html.parser')
                else:
                    # Fallback to regular method
                    page_response = session.get(target_url, timeout=REQUEST_TIMEOUT)
                    soup = BeautifulSoup(page_response.content, 'html.parser')
                    current_opportunities, has_opportunities_now = extract_opportunities(soup)
            except Exception as e:
                logger.warning(f"⚠️  Selenium page load failed: {e}, falling back to requests")
                page_response = session.get(target_url, timeout=REQUEST_TIMEOUT)
                soup = BeautifulSoup(page_response.content, 'html.parser')
                current_opportunities, has_opportunities_now = extract_opportunities(soup)
        else:
            page_response = session.get(target_url, timeout=REQUEST_TIMEOUT)
            logger.info(f"📄 Reference page status: {page_response.status_code}")
            logger.info(f"📄 Final URL: {page_response.url}")
            
            # Save the page for debugging
            debug_file = os.path.join(os.path.dirname(__file__), 'debug_page.html')
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(page_response.text)
            logger.info(f"💾 Saved page content to {debug_file} for inspection")
            
            # Also log a snippet to help debug widget detection
            if 'opportunityannouncementwidget' in page_response.text.lower():
                logger.info("✅ Found 'opportunityannouncementwidget' text in page HTML")
                # Find the line number where it appears
                lines = page_response.text.split('\n')
                for i, line in enumerate(lines, 1):
                    if 'opportunityannouncementwidget' in line.lower():
                        logger.debug(f"   Found at line {i}: {line.strip()[:100]}")
                        break
            else:
                logger.warning("⚠️  'opportunityannouncementwidget' text NOT found in page HTML")
            
            page_response.raise_for_status()  # Raises an exception for bad status codes
            
            if page_response.status_code != 200:
                logger.error(f"Failed to fetch page: HTTP {page_response.status_code}")
                return False

            # Parse the HTML
            soup = BeautifulSoup(page_response.content, 'html.parser')
            
            # STEP 3: Extract opportunities using SIMPLE "No Data" check
            current_opportunities, has_opportunities_now = extract_opportunities(soup)

        # Check if we're actually on the reference page
        page_title = soup.find('title')
        if page_title:
            logger.info(f"🔍 Page title: {page_title.get_text()}")
        
        # Check if we're being redirected to login
        if 'login' in page_response.url.lower():
            logger.error("❌ Redirected to login page - authentication failed")
            send_email_notification("Arise monitor authentication failed - redirected to login", change_type="error")
            return False

        # STEP 4: Try to find API endpoint for widget data (optional enhancement)
        api_endpoint = find_widget_api_endpoint(soup, session)
        if api_endpoint:
            logger.info(f"🔍 Found API endpoint, but using current method for now")
        
        # STEP 5: Read previous state
        previous_state = None
        try:
            with open('previous_state.txt', 'r') as f:
                previous_state = f.read().strip()
        except FileNotFoundError:
            logger.info("No previous state found. This is the first run.")

        # STEP 6: Determine current state representation
        # Use a simple string that represents the opportunity state
        if has_opportunities_now:
            current_state = "OPPORTUNITIES_AVAILABLE"
            state_details = ",".join(current_opportunities) if current_opportunities else "opportunities_available"
        else:
            current_state = "NO_DATA"
            state_details = ""

        current_state_hash = hashlib.md5(f"{current_state}:{state_details}".encode('utf-8')).hexdigest()

        # If it's the first run, save the state and send notification if opportunities are found
        if previous_state is None:
            with open('previous_state.txt', 'w') as f:
                f.write(f"{current_state_hash}|{current_state}|{state_details}")
            logger.info(f"💾 Initial state saved: {current_state}")
            
            # Send notification on first run if opportunities are found
            if has_opportunities_now:
                notification_message = "🎉 OPPORTUNITIES AVAILABLE! 🎉\n\nThis is the first run of the monitor. Opportunities are currently available in the Program Announcement section."
                opportunity_details = current_opportunities if current_opportunities else None
                send_email_notification(notification_message, opportunity_details, "new_opportunities")
                logger.info("📧 First run notification sent - opportunities found")
            else:
                logger.info("ℹ️  First run - no opportunities found, no notification sent")
            
            return True

        # STEP 7: Parse previous state
        try:
            previous_hash, previous_state_str, previous_details = previous_state.split('|', 2)
        except ValueError:
            logger.error("❌ Corrupted previous state file")
            previous_hash = ""
            previous_state_str = ""
            previous_details = ""

        # STEP 8: Check for changes
        change_detected = False
        notification_message = ""
        change_type = "opportunities_updated"  # default

        if current_state_hash != previous_hash:
            # State has changed
            if current_state == "OPPORTUNITIES_AVAILABLE" and previous_state_str == "NO_DATA":
                # This is what we're looking for! No Data → Opportunities Available
                change_detected = True
                change_type = "new_opportunities"
                notification_message = "🎉 NEW OPPORTUNITIES DETECTED! 🎉\n\nThe Program Announcement section has changed from 'No Data' to showing available opportunities."
                logger.info("🚨 Change detected: No Data → Opportunities Available")
                
            elif current_state == "NO_DATA" and previous_state_str == "OPPORTUNITIES_AVAILABLE":
                # Opportunities disappeared
                change_detected = True
                change_type = "opportunities_removed"
                notification_message = "⚠️ Opportunities Removed\n\nAll opportunities have been removed from the Program Announcement section."
                logger.info("⚠️ Change detected: Opportunities Available → No Data")
                
            else:
                # Other state changes (opportunities changed but both states have opportunities)
                change_detected = True
                change_type = "opportunities_updated"
                notification_message = "📊 Opportunities Updated\n\nThe available opportunities have changed."
                logger.info("📊 Change detected: Opportunities updated")

        # STEP 9: Handle notifications and state saving
        if change_detected:
            logger.info("🎉 Change detected! Sending notification.")
            
            # Only include opportunity details if we have opportunities now
            opportunity_details = current_opportunities if has_opportunities_now else None
            
            send_email_notification(notification_message, opportunity_details, change_type)
            
            # Save the new state
            with open('previous_state.txt', 'w') as f:
                f.write(f"{current_state_hash}|{current_state}|{state_details}")
                
            logger.info("💾 New state saved")
            return True
        else:
            logger.info("✅ No changes detected in opportunity status.")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error monitoring page: {e}")
        send_email_notification(f"Arise monitor error: {str(e)}", change_type="error")
        return False

if __name__ == "__main__":
    # Check that required environment variables are set
    required_vars = ['ARISE_USERNAME', 'ARISE_PASSWORD', 'GMAIL_ADDRESS', 'GMAIL_APP_PASSWORD']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"❌ Error: Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)
    
    success = check_for_changes()
    sys.exit(0 if success else 1)
