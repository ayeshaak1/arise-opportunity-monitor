import requests
from bs4 import BeautifulSoup
import hashlib
import os
import json
import sys
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AriseMonitor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Get credentials from environment variables
        self.username = os.getenv('ARISE_USERNAME')
        self.password = os.getenv('ARISE_PASSWORD')
        self.pushbullet_token = os.getenv('PUSHBULLET_TOKEN')
        
        if not self.username or not self.password:
            logger.error("Missing ARISE_USERNAME or ARISE_PASSWORD environment variables")
            sys.exit(1)
    
    def login_to_portal(self):
        """Attempt to login to Arise portal"""
        try:
            # First, get the main page to establish session
            main_page = "https://link.arise.com/"
            logger.info("🔄 Attempting to login to Arise portal...")
            
            response = self.session.get(main_page)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for login form - we'll try to find it dynamically
            login_form = soup.find('form', {'action': lambda x: x and ('login' in x.lower() if x else False)})
            
            if not login_form:
                # Try alternative approach - look for username/password fields
                username_field = soup.find('input', {'name': lambda x: x and any(keyword in x.lower() for keyword in ['username', 'email', 'user'])})
                if username_field:
                    login_payload = {
                        username_field['name']: self.username,
                        'password': self.password
                    }
                    
                    # Try to find the form action
                    form = username_field.find_parent('form')
                    if form and form.get('action'):
                        login_url = form['action']
                        if login_url.startswith('/'):
                            login_url = f"https://link.arise.com{login_url}"
                    else:
                        login_url = main_page  # Fallback
                    
                    logger.info(f"📝 Found login form, attempting to submit...")
                    login_response = self.session.post(login_url, data=login_payload, allow_redirects=True)
                    
                    # Check if login was successful
                    if 'logout' in login_response.text.lower() or 'dashboard' in login_response.text.lower():
                        logger.info("✅ Login successful!")
                        return True
            
            logger.warning("⚠️  Could not find standard login form, trying direct approach...")
            
            # Fallback: Try common login endpoints
            common_login_urls = [
                "https://link.arise.com/Account/Login",
                "https://link.arise.com/login",
                "https://link.arise.com/signin"
            ]
            
            for login_url in common_login_urls:
                try:
                    login_payload = {
                        'Username': self.username,
                        'Password': self.password,
                        'Email': self.username,
                        'UserID': self.username
                    }
                    
                    response = self.session.post(login_url, data=login_payload, allow_redirects=True)
                    if response.status_code == 200 and ('logout' in response.text.lower() or 'welcome' in response.text.lower()):
                        logger.info("✅ Login successful with fallback method!")
                        return True
                except:
                    continue
            
            logger.error("❌ All login attempts failed")
            return False
            
        except Exception as e:
            logger.error(f"❌ Login error: {e}")
            return False
    
    def get_opportunity_content(self):
        """Extract opportunity announcements from the reference page"""
        try:
            target_url = "https://link.arise.com/reference"
            logger.info("🌐 Fetching opportunities page...")
            
            response = self.session.get(target_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Method 1: Look for the specific widget by ID
            opportunity_widget = soup.find('div', id='opportunityannouncementwidget')
            
            if opportunity_widget:
                content = opportunity_widget.get_text(separator=' ', strip=True)
                logger.info("✅ Found opportunity widget")
                return content
            
            # Method 2: Look for tables with opportunity data
            tables = soup.find_all('table')
            for i, table in enumerate(tables):
                table_text = table.get_text().lower()
                if any(keyword in table_text for keyword in ['opportunity', 'announcement', 'program']):
                    content = table.get_text(separator=' ', strip=True)
                    logger.info(f"✅ Found opportunities in table {i+1}")
                    return content
            
            # Method 3: Look for specific text patterns
            page_text = soup.get_text().lower()
            if 'program announcement' in page_text:
                # Extract section around this text
                start_idx = page_text.find('program announcement')
                content = soup.get_text()[start_idx:start_idx+1000]  # Get 1000 chars after
                logger.info("✅ Found program announcement section")
                return content
            
            logger.warning("⚠️  No specific opportunity content found, using full page text")
            return soup.get_text(separator=' ', strip=True)[:2000]  # Limit size
            
        except Exception as e:
            logger.error(f"❌ Error fetching opportunities: {e}")
            return None
    
    def send_pushbullet_notification(self, title, message):
        """Send push notification to iPhone via Pushbullet"""
        if not self.pushbullet_token:
            logger.error("❌ No Pushbullet token configured")
            return False
            
        try:
            data = {
                "type": "note",
                "title": title,
                "body": message
            }
            
            headers = {
                'Access-Token': self.pushbullet_token,
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                'https://api.pushbullet.com/v2/pushes',
                data=json.dumps(data),
                headers=headers
            )
            
            if response.status_code == 200:
                logger.info("📱 Push notification sent successfully!")
                return True
            else:
                logger.error(f"❌ Push notification failed: {response.text}")
                return False
        except Exception as e:
            logger.error(f"❌ Push notification error: {e}")
            return False
    
    def check_for_changes(self):
        """Main function to check for opportunity changes"""
        # Login first
        if not self.login_to_portal():
            return False
        
        # Get current content
        current_content = self.get_opportunity_content()
        if current_content is None:
            logger.error("❌ Could not retrieve opportunity content")
            return False
        
        # Create content hash (fingerprint)
        current_hash = hashlib.md5(current_content.encode('utf-8')).hexdigest()
        logger.info(f"🔑 Content hash: {current_hash[:16]}...")
        
        # Try to read previous hash from file
        previous_hash = None
        hash_file = 'last_hash.txt'
        
        if os.path.exists(hash_file):
            with open(hash_file, 'r') as f:
                previous_hash = f.read().strip()
            logger.info(f"📖 Previous hash: {previous_hash[:16]}...")
        else:
            logger.info("📖 No previous hash found (first run)")
        
        # Compare hashes
        if previous_hash is None:
            logger.info("💾 Storing initial hash for future comparison")
            with open(hash_file, 'w') as f:
                f.write(current_hash)
            return True
        elif current_hash != previous_hash:
            logger.info("🎉 CHANGE DETECTED! New opportunities available!")
            
            # Send push notification
            notification_msg = f"New Arise opportunities detected!\n\nPreview: {current_content[:150]}..."
            self.send_pushbullet_notification("🚨 Arise Opportunity Alert!", notification_msg)
            
            # Update the hash
            with open(hash_file, 'w') as f:
                f.write(current_hash)
            
            return True
        else:
            logger.info("✅ No changes detected")
            return False

def main():
    monitor = AriseMonitor()
    success = monitor.check_for_changes()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
