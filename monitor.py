import requests
from bs4 import BeautifulSoup
import hashlib
import os
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
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
    msg = MimeMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = "🚨 New Arise Opportunity Alert!"
    msg.attach(MimeText(message, 'plain'))

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

    # STEP 1: Attempt to log in (this is a basic attempt; may need adjustment)
    login_url = "https://link.arise.com/"
    login_payload = {
        'username': arise_username,
        'password': arise_password,
    }
    logger.info("Attempting to log in...")
    login_response = session.post(login_url, data=login_payload)

    # A simple check for login success - look for a logout link
    if 'logout' not in login_response.text.lower():
        logger.warning("Login may have failed. Will try to proceed anyway.")

    # STEP 2: Access the opportunities page
    target_url = "https://link.arise.com/reference"
    logger.info("Fetching the opportunities page...")
    page_response = session.get(target_url)

    if page_response.status_code != 200:
        send_email_notification(f"Error: Could not access the Arise page. HTTP Status: {page_response.status_code}")
        return False

    # Parse the HTML
    soup = BeautifulSoup(page_response.content, 'html.parser')

    # STEP 3: Focus on the relevant section. Try the specific widget first.
    opportunity_section = soup.find('div', id='opportunityannouncementwidget')
    if opportunity_section:
        content_to_hash = opportunity_section.get_text()
    else:
        # Fallback: use the entire body if the specific widget isn't found
        content_to_hash = soup.find('body').get_text() if soup.find('body') else page_response.text

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
    if current_hash != previous_hash:
        logger.info("🎉 Change detected! Sending notification.")
        notification_message = "A change was detected on the Arise opportunities page. Check https://link.arise.com/reference"
        send_email_notification(notification_message)
        # Save the new hash for the next comparison
        with open('previous_hash.txt', 'w') as f:
            f.write(current_hash)
        return True
    else:
        logger.info("✅ No changes detected.")
        return True

if __name__ == "__main__":
    # Check that required environment variables are set
    if not os.getenv('ARISE_USERNAME') or not os.getenv('ARISE_PASSWORD'):
        logger.error("Error: Arise username or password not set.")
        sys.exit(1)
    success = check_for_changes()
    sys.exit(0 if success else 1)
