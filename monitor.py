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
        email_body += "📋 OPPORTUNITY DETAILS:\n"
        email_body += "=" * 50 + "\n"
        for opportunity in opportunity_details:
            email_body += f"• {opportunity}\n"
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
    # Look for the opportunity announcement widget - use case-insensitive search
    opportunity_widget = soup.find('div', id=lambda x: x and 'opportunityannouncementwidget' in x.lower())
    
    if not opportunity_widget:
        logger.info("📭 Opportunity widget not found")
        return [], False
    
    # Get ALL text from the widget (simple approach)
    widget_text = opportunity_widget.get_text()
    
    # Simple check: if "No Data" appears anywhere in the widget text
    if 'No Data' in widget_text:
        logger.info("📭 'No Data' message found - NO opportunities available")
        return [], False
    else:
        logger.info("🎯 No 'No Data' message found - OPPORTUNITIES AVAILABLE!")
        # Try to extract opportunity details from tables
        opportunities = extract_opportunity_details(opportunity_widget)
        if not opportunities:
            opportunities = ["New opportunities available - check Arise portal for details"]
        logger.info(f"📋 Extracted opportunities: {opportunities}")
        return opportunities, True

def extract_opportunity_details(widget):
    """
    Try to extract specific opportunity details from tables
    """
    opportunities = []
    
    # Look for tables in the widget
    tables = widget.find_all('table')
    for table in tables:
        # Look for table rows (skip header row)
        rows = table.find_all('tr')[1:]  # Skip the first header row
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 3:  # Should have Opportunity, Download, File Name columns
                opportunity_name = cells[0].get_text(strip=True)
                file_name = cells[2].get_text(strip=True)
                
                if opportunity_name and opportunity_name != "No Data":
                    opportunity_str = f"{opportunity_name} - {file_name}"
                    opportunities.append(opportunity_str)
    
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
        if 'login' not in oauth_result.url.lower() and 'account/login' not in oauth_result.url.lower():
            logger.info("✅ OAuth login successful!")
            login_successful = True
        else:
            logger.warning("⚠️  OAuth login may have failed - still on login page")
    else:
        logger.warning("⚠️  OAuth login failed or returned unexpected response")
    
    # If OAuth failed, try direct login to OAuth endpoint
    if not login_successful:
        logger.info("🔄 Trying direct OAuth login...")
        try:
            # Try posting directly to the OAuth login endpoint
            oauth_login_data = {
                'Username': arise_username,
                'Password': arise_password,
                'button': 'login'
            }
            direct_response = session.post(
                'https://oauth.arise.com/Account/Login', 
                data=oauth_login_data, 
                allow_redirects=True,
                timeout=REQUEST_TIMEOUT
            )
            
            if direct_response.status_code == 200 and 'login' not in direct_response.url.lower():
                login_successful = True
                logger.info("✅ Direct OAuth login successful!")
            else:
                logger.warning("❌ Direct OAuth login failed")
        except Exception as e:
            logger.warning(f"Direct OAuth login failed: {e}")
    
    if not login_successful:
        logger.error("❌ All login attempts failed!")
        send_email_notification("Arise monitor authentication failed - check your credentials", change_type="error")
        return False

    # STEP 2: Access the references page
    target_url = "https://link.arise.com/reference"
    logger.info("Fetching the references page...")
    
    try:
        page_response = session.get(target_url, timeout=REQUEST_TIMEOUT)
        logger.info(f"📄 Reference page status: {page_response.status_code}")
        logger.info(f"📄 Final URL: {page_response.url}")
        
        # Save the page for debugging
        with open('debug_page.html', 'w', encoding='utf-8') as f:
            f.write(page_response.text)
        logger.info("💾 Saved page content to debug_page.html for inspection")
        
        page_response.raise_for_status()  # Raises an exception for bad status codes
        
        if page_response.status_code != 200:
            logger.error(f"Failed to fetch page: HTTP {page_response.status_code}")
            return False

        # Parse the HTML
        soup = BeautifulSoup(page_response.content, 'html.parser')

        # Check if we're actually on the reference page
        page_title = soup.find('title')
        if page_title:
            logger.info(f"🔍 Page title: {page_title.get_text()}")
        
        # Check if we're being redirected to login
        if 'login' in page_response.url.lower():
            logger.error("❌ Redirected to login page - authentication failed")
            send_email_notification("Arise monitor authentication failed - redirected to login", change_type="error")
            return False

        # STEP 3: Extract opportunities using SIMPLE "No Data" check
        current_opportunities, has_opportunities_now = extract_opportunities(soup)
        
        # STEP 4: Read previous state
        previous_state = None
        try:
            with open('previous_state.txt', 'r') as f:
                previous_state = f.read().strip()
        except FileNotFoundError:
            logger.info("No previous state found. This is the first run.")

        # STEP 5: Determine current state representation
        # Use a simple string that represents the opportunity state
        if has_opportunities_now:
            current_state = "OPPORTUNITIES_AVAILABLE"
            state_details = ",".join(current_opportunities) if current_opportunities else "opportunities_available"
        else:
            current_state = "NO_DATA"
            state_details = ""

        current_state_hash = hashlib.md5(f"{current_state}:{state_details}".encode('utf-8')).hexdigest()

        # If it's the first run, just save the state and exit
        if previous_state is None:
            with open('previous_state.txt', 'w') as f:
                f.write(f"{current_state_hash}|{current_state}|{state_details}")
            logger.info(f"💾 Initial state saved: {current_state}")
            return True

        # STEP 6: Parse previous state
        try:
            previous_hash, previous_state_str, previous_details = previous_state.split('|', 2)
        except ValueError:
            logger.error("❌ Corrupted previous state file")
            previous_hash = ""
            previous_state_str = ""
            previous_details = ""

        # STEP 7: Check for changes
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

        # STEP 8: Handle notifications and state saving
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
