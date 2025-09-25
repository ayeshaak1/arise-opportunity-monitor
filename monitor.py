import requests
from bs4 import BeautifulSoup
import hashlib
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import sys

# Set up logging to see what's happening
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def send_email_notification(message):
    """
    Sends an email notification using Gmail's SMTP server.
    """
    sender_email = os.getenv('GMAIL_ADDRESS')
    sender_password = os.getenv('GMAIL_APP_PASSWORD')
    receiver_email = sender_email  # Send the alert to yourself

    # Create the email message
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = "🚨 New Arise Opportunity Alert!"
    msg.attach(MIMEText(message, 'plain'))

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

def check_for_changes():
    """
    Main function to check for opportunity changes on the Arise portal.
    """
    # Create a session to maintain login state
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })

    # Get credentials from environment variables
    arise_username = os.getenv('ARISE_USERNAME')
    arise_password = os.getenv('ARISE_PASSWORD')

    # STEP 1: Try multiple login approaches
    login_successful = False
    
    if arise_username and arise_password:
        logger.info("Attempting to log in...")
        
        # Try different login endpoints and form fields
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

    # STEP 2: Access the opportunities page
    target_url = "https://link.arise.com/reference"
    logger.info("Fetching the opportunities page...")
    
    try:
        page_response = session.get(target_url)
        page_response.raise_for_status()  # Raises an exception for bad status codes
        
        if page_response.status_code != 200:
            logger.error(f"Failed to fetch page: HTTP {page_response.status_code}")
            return False

        # Parse the HTML
        soup = BeautifulSoup(page_response.content, 'html.parser')

        # STEP 3: Focus on the relevant section - try multiple selectors
        content_to_hash = ""
        
        # Try the specific widget first
        opportunity_section = soup.find('div', id='opportunityannouncementwidget')
        if opportunity_section:
            content_to_hash = opportunity_section.get_text()
            logger.info("✅ Found opportunity widget")
        else:
            # Try tables with opportunity data
            tables = soup.find_all('table')
            for table in tables:
                table_text = table.get_text().lower()
                if any(keyword in table_text for keyword in ['opportunity', 'announcement', 'program']):
                    content_to_hash = table.get_text()
                    logger.info("✅ Found opportunities in table")
                    break
            
            # Fallback: use specific content areas
            if not content_to_hash:
                main_content = soup.find('div', {'class': ['body-container', 'content-inner']})
                if main_content:
                    content_to_hash = main_content.get_text()
                else:
                    content_to_hash = soup.find('body').get_text() if soup.find('body') else page_response.text
                
                logger.info("⚠️  Using fallback content extraction")

        # STEP 4: Create a hash (fingerprint) of the content
        current_hash = hashlib.md5(content_to_hash.encode('utf-8')).hexdigest()
        logger.info(f"Current content hash: {current_hash}")

        # STEP 5: Check against the previous hash
        previous_hash = None
        try:
            with open('previous_hash.txt', 'r') as f:
                previous_hash = f.read().strip()
        except FileNotFoundError:
            logger.info("No previous hash found. This is the first run.")

        # If it's the first run, just save the hash and exit.
        if previous_hash is None:
            with open('previous_hash.txt', 'w') as f:
                f.write(current_hash)
            logger.info("Initial hash saved. Monitoring will start on the next run.")
            return True

        # STEP 6: Compare and notify
        if current_hash != previous_hash or True:
            logger.info("🎉 Change detected! Sending notification.")
            notification_message = f"New Arise opportunity detected!\n\nPage: https://link.arise.com/reference\n\nContent preview: {content_to_hash[:500]}..."
            send_email_notification(notification_message)
            # Save the new hash for the next comparison
            with open('previous_hash.txt', 'w') as f:
                f.write(current_hash)
            return True
        else:
            logger.info("✅ No changes detected.")
            return True
            
    except Exception as e:
        logger.error(f"Error monitoring page: {e}")
        send_email_notification(f"Arise monitor error: {str(e)}")
        return False

if __name__ == "__main__":
    # Check that required environment variables are set
    if not os.getenv('ARISE_USERNAME') or not os.getenv('ARISE_PASSWORD'):
        logger.error("Error: Arise username or password not set.")
        sys.exit(1)
    success = check_for_changes()
    sys.exit(0 if success else 1)
