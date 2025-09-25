import requests
from bs4 import BeautifulSoup
import hashlib
import os
import sys

# Get credentials and settings from environment variables
ARISE_USERNAME = os.getenv('ARISE_USERNAME')
ARISE_PASSWORD = os.getenv('ARISE_PASSWORD')
PUSHOVER_USER_KEY = os.getenv('PUSHOVER_USER_KEY')
PUSHOVER_API_TOKEN = os.getenv('PUSHOVER_API_TOKEN')

def send_pushover_notification(message):
    """Send a push notification via Pushover"""
    if not PUSHOVER_API_TOKEN or not PUSHOVER_USER_KEY:
        print("Pushover credentials not set.")
        return False
        
    data = {
        "token": PUSHOVER_API_TOKEN,
        "user": PUSHOVER_USER_KEY,
        "message": message,
        "title": "🚨 Arise Opportunity Alert"
    }
    response = requests.post("https://api.pushover.net/1/messages.json", data=data)
    return response.status_code == 200

def check_for_changes():
    # Create a session to maintain login state
    session = requests.Session()
    
    # Add a common browser user-agent to appear more legitimate
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
    })
    
    # STEP 1: TRY TO LOGIN
    # This is a simplified login attempt. You may need to adjust the form data based on the actual Arise login page.
    login_url = "https://link.arise.com/"  # This might need to be the specific login form URL
    login_payload = {
        'username': ARISE_USERNAME,
        'password': ARISE_PASSWORD,
    }
    
    print("Attempting to log in...")
    login_response = session.post(login_url, data=login_payload)
    
    # Check if login was successful by looking for a logout link or a common post-login element
    if 'logout' not in login_response.text.lower():
        print("Login may have failed. The script will continue but may not access protected content.")
        # Don't return False here; still try to access the page as the structure might be different.
    
    # STEP 2: ACCESS THE OPPORTUNITIES PAGE
    target_url = "https://link.arise.com/reference"
    print("Fetching the opportunities page...")
    page_response = session.get(target_url)
    
    if page_response.status_code != 200:
        send_pushover_notification(f"Error: Could not access the page. HTTP Status: {page_response.status_code}")
        return False
    
    # Parse the HTML content
    soup = BeautifulSoup(page_response.content, 'html.parser')
    
    # STEP 3: FOCUS ON THE RELEVANT SECTION
    # Try to find the specific widget or table containing opportunities.
    # The following line targets the div with ID 'opportunityannouncementwidget' based on the page source you provided.
    opportunity_section = soup.find('div', id='opportunityannouncementwidget')
    
    # If that specific div isn't found, use the entire page body as a fallback.
    if opportunity_section:
        content_to_hash = opportunity_section.get_text()
    else:
        content_to_hash = soup.find('body').get_text() if soup.find('body') else page_response.text
    
    # STEP 4: CREATE A HASH OF THE CONTENT
    current_hash = hashlib.md5(content_to_hash.encode('utf-8')).hexdigest()
    print(f"Current content hash: {current_hash}")
    
    # STEP 5: CHECK AGAINST THE PREVIOUS HASH
    # The previous hash will be stored in a file that persists between workflow runs using GitHub's cache action.
    previous_hash = None
    try:
        with open('previous_hash.txt', 'r') as f:
            previous_hash = f.read().strip()
    except FileNotFoundError:
        print("No previous hash found. This is likely the first run.")
    
    # If it's the first run, just save the hash and exit.
    if previous_hash is None:
        with open('previous_hash.txt', 'w') as f:
            f.write(current_hash)
        print("Initial hash saved. Monitoring will start on the next run.")
        return True
    
    # STEP 6: COMPARE AND NOTIFY
    if current_hash != previous_hash:
        print("Change detected! Sending notification.")
        notification_message = "A change was detected on the Arise opportunities page. Check https://link.arise.com/reference"
        if send_pushover_notification(notification_message):
            print("Notification sent successfully.")
        # Save the new hash as the previous hash for next time
        with open('previous_hash.txt', 'w') as f:
            f.write(current_hash)
        return True
    else:
        print("No changes detected.")
        return True

if __name__ == "__main__":
    # Check that all required environment variables are set
    if not ARISE_USERNAME or not ARISE_PASSWORD:
        print("Error: Arise username or password not set in environment variables.")
        sys.exit(1)
        
    success = check_for_changes()
    sys.exit(0 if success else 1)
