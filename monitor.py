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
    # Look for the opportunity announcement widget
    opportunity_widget = soup.find('div', id='opportunityannouncementwidget')
    
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

def check_for_changes():
    """
    Main function to check for opportunity changes on the Arise portal.
    """
    # Create a session to maintain login state
    session = requests.Session()
    session.timeout = REQUEST_TIMEOUT
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })

    # Get credentials from environment variables
    arise_username = os.getenv('ARISE_USERNAME')
    arise_password = os.getenv('ARISE_PASSWORD')

    # STEP 1: Simple login approach (old working logic)
    login_successful = False
    
    if arise_username and arise_password:
        logger.info("Attempting to log in...")
        
        # Try different login endpoints and form fields (old working approach)
        login_attempts = [
            {
                'url': 'https://link.arise.com/Account/Login',
                'data': {'username': arise_username, 'password': arise_password}
            },
            {
                'url': 'https://link.arise.com/login', 
                'data': {'email': arise_username, 'password': arise_password}
            },
            {
                'url': 'https://link.arise.com/',
                'data': {'Username': arise_username, 'Password': arise_password}
            }
        ]
        
        for attempt in login_attempts:
            try:
                response = session.post(attempt['url'], data=attempt['data'], allow_redirects=False)
                if response.status_code in [200, 302]:  # Success or redirect
                    # Check if we got a session cookie or redirect to dashboard
                    if 'set-cookie' in response.headers or response.status_code == 302:
                        login_successful = True
                        logger.info("✅ Login successful!")
                        break
            except Exception as e:
                logger.warning(f"Login attempt failed: {e}")
                continue
                
        if not login_successful:
            logger.warning("⚠️  Login attempts failed, but will try to access page anyway")
    else:
        logger.warning("⚠️  No login credentials provided, accessing as guest")

    # STEP 2: Access the references page
    target_url = "https://link.arise.com/reference"
    logger.info("Fetching the references page...")
    
    try:
        page_response = session.get(target_url, timeout=REQUEST_TIMEOUT)
        page_response.raise_for_status()  # Raises an exception for bad status codes
        
        if page_response.status_code != 200:
            logger.error(f"Failed to fetch page: HTTP {page_response.status_code}")
            return False

        # Parse the HTML
        soup = BeautifulSoup(page_response.content, 'html.parser')

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
