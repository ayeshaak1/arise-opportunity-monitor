"""
Selenium-based OAuth handler for Arise portal
This is a more reliable approach for handling OAuth flows with form_post response mode
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import logging
import requests
import re
import os
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def handle_oauth_login_selenium(username, password, headless=True):
    """
    Handle OAuth login using Selenium for more reliable form handling
    Returns a requests.Session with cookies from the browser
    """
    logger.info("🌐 Starting Selenium-based OAuth login...")
    
    # Set up Chrome options
    chrome_options = Options()
    if headless:
        chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    # For GitHub Actions/Linux environments
    if os.getenv('GITHUB_ACTIONS') or os.path.exists('/usr/bin/chromium-browser'):
        chrome_options.add_argument('--remote-debugging-port=9222')
        # Use system chromium if available
        if os.path.exists('/usr/bin/chromium-browser'):
            chrome_options.binary_location = '/usr/bin/chromium-browser'
    
    driver = None
    try:
        # Initialize Chrome driver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.implicitly_wait(10)
        
        # Step 1: Navigate to portal
        logger.info("🔍 Navigating to Arise portal...")
        driver.get('https://link.arise.com/')
        time.sleep(2)
        
        # Step 2: Wait for and fill login form
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.NAME, "Username"))).clear()
        driver.find_element(By.NAME, "Username").send_keys(username)
        driver.find_element(By.NAME, "Password").clear()
        driver.find_element(By.NAME, "Password").send_keys(password)
        driver.find_element(By.NAME, "button").click()
        
        # Step 3: Wait for OAuth authorization or portal redirect
        time.sleep(3)
        
        # Check if we're on authorization page
        current_url = driver.current_url
        logger.info(f"📍 Current URL after login: {current_url}")
        
        # If we're on authorization page, look for form and submit it
        if 'connect/authorize' in current_url or 'oauth.arise.com' in current_url:
            logger.info("🔐 On OAuth authorization page, looking for authorization form...")
            time.sleep(2)
            
            # Look for form that posts to link.arise.com
            try:
                # Try to find and submit the authorization form
                auth_form = driver.find_element(By.TAG_NAME, "form")
                form_action = auth_form.get_attribute("action")
                logger.info(f"🔍 Found authorization form with action: {form_action}")
                
                if 'link.arise.com' in form_action:
                    # Submit the form
                    submit_button = auth_form.find_element(By.CSS_SELECTOR, "input[type='submit'], button[type='submit']")
                    submit_button.click()
                    logger.info("✅ Authorization form submitted")
                    time.sleep(3)
            except Exception as e:
                logger.warning(f"⚠️  Could not find/submit authorization form: {e}")
                # Try to navigate directly to portal
                logger.info("🔄 Attempting direct navigation to portal...")
                driver.get('https://link.arise.com/home')
                time.sleep(3)
        
        # Step 4: Wait for portal to load
        wait.until(lambda d: 'link.arise.com' in d.current_url and 'login' not in d.current_url.lower())
        final_url = driver.current_url
        logger.info(f"✅ Successfully logged in! Final URL: {final_url}")
        
        # Step 5: Extract cookies and create requests session
        cookies = driver.get_cookies()
        session = requests.Session()
        
        for cookie in cookies:
            session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain', ''))
        
        # Set headers to match browser
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        
        logger.info("✅ Session created with browser cookies")
        return session, final_url
        
    except Exception as e:
        logger.error(f"❌ Selenium login failed: {e}")
        return None, None
    finally:
        if driver:
            driver.quit()
            logger.info("🔒 Browser closed")

def get_reference_page_with_selenium(session, headless=True):
    """
    Use Selenium to load the reference page and quickly check for "No Data" message.
    Optimized for speed - checks page source directly instead of waiting for widget.
    Returns: (soup, has_opportunities)
    """
    logger.info("🌐 Using Selenium to load reference page with JavaScript...")
    
    chrome_options = Options()
    if headless:
        chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    # For GitHub Actions/Linux environments
    if os.getenv('GITHUB_ACTIONS') or os.path.exists('/usr/bin/chromium-browser'):
        chrome_options.add_argument('--remote-debugging-port=9222')
        # Use system chromium if available
        if os.path.exists('/usr/bin/chromium-browser'):
            chrome_options.binary_location = '/usr/bin/chromium-browser'
    
    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.implicitly_wait(5)  # Reduced from 10
        
        # First, we need to be logged in - copy cookies from session
        # Navigate to the domain first (required before adding cookies)
        driver.get('https://link.arise.com/')
        time.sleep(2)
        
        # Add all cookies from the session
        cookies_added = 0
        cookie_names = []
        for cookie in session.cookies:
            try:
                # Try different domain formats
                domains_to_try = [
                    cookie.domain or '.arise.com',
                    '.arise.com',
                    'link.arise.com',
                    '.link.arise.com'
                ]
                
                added = False
                for domain in domains_to_try:
                    try:
                        cookie_dict = {
                            'name': cookie.name,
                            'value': cookie.value,
                            'domain': domain,
                            'path': cookie.path or '/'
                        }
                        # Add secure flag if cookie is secure
                        if hasattr(cookie, 'secure') and cookie.secure:
                            cookie_dict['secure'] = True
                        driver.add_cookie(cookie_dict)
                        cookies_added += 1
                        cookie_names.append(cookie.name)
                        added = True
                        break
                    except Exception as e:
                        logger.debug(f"Failed to add cookie {cookie.name} to domain {domain}: {e}")
                        continue
                
                if not added:
                    logger.warning(f"⚠️  Could not add cookie: {cookie.name}")
            except Exception as e:
                logger.debug(f"Error processing cookie {cookie.name}: {e}")
        
        logger.debug(f"✅ Added {cookies_added} cookies to browser")
        
        # Navigate to home first to verify cookies work
        driver.get('https://link.arise.com/home')
        time.sleep(2)  # Reduced from 3
        home_url = driver.current_url
        
        # Check if we're still logged in
        if 'login' in home_url.lower() or 'oauth' in home_url.lower():
            logger.error("❌ Cookies not working - redirected to login!")
            logger.error("❌ Cannot access reference page without valid session")
            return None, False
        
        # Navigate to reference page
        driver.get('https://link.arise.com/reference')
        
        # Wait for navigation and verify we're on the reference page
        time.sleep(2)  # Reduced from 4
        current_url = driver.current_url
        page_title = driver.title
        
        # Check if we got redirected to login
        if 'login' in current_url.lower() or 'oauth' in current_url.lower() or 'login' in page_title.lower():
            logger.error(f"❌ Redirected to login! Current URL: {current_url}, Title: {page_title}")
            logger.error("❌ Session cookies may have expired or are invalid")
            # Save the login page for debugging
            debug_file = os.path.join(os.path.dirname(__file__), 'debug_login_redirect.html')
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(f"<!-- URL: {current_url} -->\n")
                f.write(f"<!-- Title: {page_title} -->\n")
                f.write(driver.page_source)
            logger.info(f"💾 Saved login redirect page to {debug_file}")
            return None, False
        
        if '/reference' not in current_url.lower():
            logger.warning(f"⚠️  Not on reference page! Current URL: {current_url}")
            # Try navigating again
            logger.info("🔄 Attempting to navigate to reference page again...")
            driver.get('https://link.arise.com/reference')
            time.sleep(4)
            current_url = driver.current_url
            page_title = driver.title
            logger.info(f"📍 URL after second navigation attempt: {current_url}")
            logger.info(f"📍 Page title after second attempt: {page_title}")
            
            if 'login' in current_url.lower() or 'login' in page_title.lower():
                logger.error("❌ Still redirected to login after second attempt")
                return None, False
        
        # Verify we're actually on the reference page (not login)
        final_url = driver.current_url
        page_title = driver.title
        logger.info(f"📍 Final URL: {final_url}")
        logger.info(f"📍 Page title: {page_title}")
        
        if 'login' in final_url.lower() or 'login' in page_title.lower():
            logger.error("❌ Still on login page! Cookies may not be working.")
            logger.error("❌ Cannot proceed - need to be logged in to access reference page")
            return None, False
        
        # Wait for page to load (minimal wait)
        wait = WebDriverWait(driver, 10)  # Reduced from 30
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        # Wait for page to be interactive
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        # Wait for jQuery and Knockout to load
        try:
            WebDriverWait(driver, 10).until(lambda d: d.execute_script("return typeof jQuery !== 'undefined' && typeof ko !== 'undefined';"))
            logger.debug("✅ jQuery and Knockout loaded")
        except:
            logger.debug("⚠️  jQuery/Knockout check timed out, continuing anyway")
        
        # Wait for page to be fully loaded (check document.readyState)
        try:
            WebDriverWait(driver, 10).until(lambda d: d.execute_script("return document.readyState === 'complete';"))
            logger.info("✅ Page fully loaded")
        except:
            logger.warning("⚠️  Page readyState check timed out")
        
        # Wait for widgets to render - give it more time
        logger.info("⏳ Waiting for widgets to render...")
        time.sleep(8)  # Increased wait time for widgets to load via AJAX
        
        # Try to wait for network activity to complete
        try:
            # Check if there are any pending AJAX requests
            pending_requests = driver.execute_script("""
                if (typeof jQuery !== 'undefined') {
                    return jQuery.active || 0;
                }
                return 0;
            """)
            if pending_requests > 0:
                logger.info(f"⏳ Waiting for {pending_requests} AJAX requests to complete...")
                WebDriverWait(driver, 15).until(lambda d: d.execute_script("return (typeof jQuery === 'undefined' || jQuery.active === 0);"))
                logger.info("✅ AJAX requests completed")
        except:
            pass
        
        widget = None
        widget_soup = None
        
        # First, list all divs with IDs to understand structure
        try:
            divs_info = driver.execute_script("""
                var divs = document.querySelectorAll('div[id]');
                var divList = [];
                for (var i = 0; i < Math.min(divs.length, 50); i++) {
                    divList.push({
                        id: divs[i].id,
                        class: divs[i].className,
                        text: divs[i].textContent.substring(0, 50).trim()
                    });
                }
                return divList;
            """)
            logger.info(f"📋 Found {len(divs_info)} divs with IDs")
            # Look for widget_landing or accordion-related divs
            for div_info in divs_info:
                if 'widget' in div_info['id'].lower() or 'accordion' in div_info['id'].lower() or 'opportunity' in div_info['id'].lower():
                    logger.info(f"  📌 Relevant div: ID={div_info['id']}, Class={div_info['class'][:40]}, Text={div_info['text']}")
        except Exception as e:
            logger.debug(f"Could not list divs: {e}")
        
        # Method 1: Wait for widget_landing container, then find Program Announcement
        widget_landing = None
        try:
            logger.info("🔍 Looking for widget_landing container...")
            # Try to find widget_landing (might not exist or might be loaded later)
            try:
                widget_landing = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.ID, "widget_landing"))
                )
                logger.info("✅ Found widget_landing container")
            except:
                # Try alternative containers
                try:
                    widget_landing = driver.find_element(By.CSS_SELECTOR, "div.accordion, div[id*='widget'], div[id*='landing']")
                    logger.info("✅ Found alternative container")
                except:
                    logger.info("⚠️  widget_landing not found, searching entire page")
            
            # Wait a bit more for widgets to render inside
            if widget_landing:
                time.sleep(3)
            else:
                time.sleep(2)
            
            # Now search for Program Announcement
            widget_info = driver.execute_script("""
                // Find widget_landing container (or use document if not found)
                var searchContainer = document.getElementById('widget_landing');
                if (!searchContainer) {
                    // Try to find accordion or widget container
                    searchContainer = document.querySelector('div.accordion, div[id*="widget"], div[id*="landing"]') || document.body;
                }
                
                // Find "Program Announcement" text
                var allElements = searchContainer.getElementsByTagName('*');
                var programAnnouncementElement = null;
                
                for (var i = 0; i < allElements.length; i++) {
                    var text = allElements[i].textContent || '';
                    if (text.includes('Program Announcement')) {
                        programAnnouncementElement = allElements[i];
                        break;
                    }
                }
                
                if (!programAnnouncementElement) {
                    // Try XPath as fallback
                    var xpath = "//*[contains(text(), 'Program Announcement')]";
                    var result = document.evaluate(xpath, searchContainer, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                    programAnnouncementElement = result.singleNodeValue;
                }
                
                if (!programAnnouncementElement) return null;
                
                // Navigate up to find accordion group
                var current = programAnnouncementElement;
                var widget = null;
                var widgetId = null;
                
                // Go up to find accordion group or widget
                for (var i = 0; i < 10 && current; i++) {
                    if (current.tagName === 'DIV') {
                        var id = current.id || '';
                        var className = current.className || '';
                        
                        // Check if this is the widget itself
                        if (id.toLowerCase().includes('opportunityannouncementwidget')) {
                            widget = current;
                            widgetId = id;
                            break;
                        }
                        
                        // Check if this is an accordion group - look for widget within
                        if (className.includes('accordion-group') || className.includes('accordion-heading')) {
                            // Search for widget in this accordion group
                            var widgetDiv = current.querySelector('div[id*="opportunityannouncementwidget" i]');
                            if (widgetDiv) {
                                widget = widgetDiv;
                                widgetId = widgetDiv.id;
                                break;
                            }
                            // Also check accordion-body
                            var accordionBody = current.querySelector('div.accordion-body[id*="opportunity" i]');
                            if (accordionBody && accordionBody.id.toLowerCase().includes('opportunityannouncementwidget')) {
                                widget = accordionBody;
                                widgetId = accordionBody.id;
                                break;
                            }
                        }
                    }
                    current = current.parentElement;
                    if (!current || current === searchContainer || current === document.body) break;
                }
                
                // If still not found, search all divs in search container
                if (!widget) {
                    var allDivs = searchContainer.querySelectorAll('div[id]');
                    for (var i = 0; i < allDivs.length; i++) {
                        var id = allDivs[i].id || '';
                        if (id.toLowerCase().includes('opportunityannouncementwidget')) {
                            widget = allDivs[i];
                            widgetId = id;
                            break;
                        }
                    }
                }
                
                if (widget) {
                    return {
                        html: widget.outerHTML,
                        id: widgetId,
                        text: widget.textContent.substring(0, 200)
                    };
                }
                return null;
            """)
            
            if widget_info:
                logger.debug(f"✅ Widget found via fast path! ID: {widget_info['id']}")
                widget_soup = BeautifulSoup(widget_info['html'], 'html.parser')
                try:
                    widget = driver.find_element(By.ID, widget_info['id'])
                except:
                    widget = driver.find_element(By.CSS_SELECTOR, f"div#{widget_info['id']}")
            else:
                logger.info("⚠️  Fast path didn't find widget, trying direct ID search...")
        except Exception as e:
            logger.debug(f"Fast path method failed: {e}")
        
        # Method 2: Direct ID search (if fast path failed)
        if not widget:
            try:
                logger.info("🔍 Trying direct widget ID search...")
                widget_info = driver.execute_script("""
                    // Try exact ID first
                    var widget = document.getElementById('opportunityannouncementwidget');
                    if (widget) {
                        return {
                            html: widget.outerHTML,
                            id: 'opportunityannouncementwidget',
                            text: widget.textContent.substring(0, 200)
                        };
                    }
                    return null;
                """)
                
                if widget_info:
                    logger.debug(f"✅ Widget found via direct ID! ID: {widget_info['id']}")
                    widget_soup = BeautifulSoup(widget_info['html'], 'html.parser')
                    widget = driver.find_element(By.ID, "opportunityannouncementwidget")
            except Exception as e:
                logger.debug(f"Direct ID search failed: {e}")
        
        # Method 3: If widget not found, try expanding accordion and searching again
        if not widget:
            try:
                logger.info("🔍 Widget not found, trying to expand accordion...")
                
                # Find accordion toggle - try multiple methods
                toggle = None
                
                # Method 1: Find by "Program Announcement" text first, then find toggle nearby
                try:
                    program_announcement = driver.find_element(By.XPATH, "//*[contains(text(), 'Program Announcement')]")
                    logger.info("✅ Found 'Program Announcement' text")
                    # Find toggle in same accordion group
                    parent = program_announcement.find_element(By.XPATH, "./ancestor::div[contains(@class, 'accordion-group') or contains(@class, 'accordion-heading')]")
                    toggle = parent.find_element(By.CSS_SELECTOR, "a.accordion-toggle, a[data-toggle='collapse']")
                    logger.info("📂 Found accordion toggle via 'Program Announcement'")
                except:
                    # Method 2: Try direct selectors
                    toggle_selectors = [
                        "a[href='#opportunityannouncementwidget']",
                        "a[href*='opportunityannouncementwidget']",
                        "a.accordion-toggle[href*='opportunity']",
                        "//a[contains(@href, 'opportunityannouncementwidget')]",
                        "//a[contains(@href, 'opportunity') and contains(@class, 'accordion-toggle')]",
                    ]
                    
                    for selector in toggle_selectors:
                        try:
                            if selector.startswith('//'):
                                toggle = driver.find_element(By.XPATH, selector)
                            else:
                                toggle = driver.find_element(By.CSS_SELECTOR, selector)
                            logger.info(f"📂 Found accordion toggle: {selector}")
                            break
                        except:
                            continue
                
                if toggle:
                    # Scroll into view and click
                    driver.execute_script("arguments[0].scrollIntoView(true);", toggle)
                    time.sleep(0.5)
                    toggle.click()
                    logger.info("✅ Clicked accordion toggle")
                    
                    # Wait for accordion to expand and widget to appear
                    time.sleep(2)
                    
                    # Wait for widget to appear and be visible
                    try:
                        widget = WebDriverWait(driver, 10).until(
                            EC.visibility_of_element_located((By.ID, "opportunityannouncementwidget"))
                        )
                        logger.info("✅ Found widget after expanding accordion (visible)")
                        widget_html = widget.get_attribute('outerHTML')
                        widget_soup = BeautifulSoup(widget_html, 'html.parser')
                    except:
                        # Try presence first, then check visibility
                        try:
                            widget = WebDriverWait(driver, 5).until(
                                EC.presence_of_element_located((By.ID, "opportunityannouncementwidget"))
                            )
                            # Check if it's visible
                            if widget.is_displayed():
                                logger.info("✅ Found widget after expanding accordion (present and visible)")
                                widget_html = widget.get_attribute('outerHTML')
                                widget_soup = BeautifulSoup(widget_html, 'html.parser')
                            else:
                                logger.warning("⚠️  Widget found but not visible")
                                widget = None
                        except:
                            pass
                        
                        # Try JavaScript search again
                        if not widget:
                            widget_html = driver.execute_script("""
                            var widget = document.getElementById('opportunityannouncementwidget');
                            if (widget) {
                                return widget.outerHTML;
                            }
                            // Also try case-insensitive
                            var allDivs = document.querySelectorAll('div[id]');
                            for (var i = 0; i < allDivs.length; i++) {
                                if (allDivs[i].id.toLowerCase().includes('opportunityannouncementwidget')) {
                                    return allDivs[i].outerHTML;
                                }
                            }
                            return null;
                            """)
                            if widget_html:
                                widget_soup = BeautifulSoup(widget_html, 'html.parser')
                                widget = driver.find_element(By.CSS_SELECTOR, "div[id*='opportunityannouncementwidget' i]")
                                logger.info("✅ Found widget via JavaScript after expanding accordion")
                else:
                    logger.warning("⚠️  Could not find accordion toggle")
            except Exception as e:
                logger.debug(f"Accordion expansion method failed: {e}")
        
        # Extract widget HTML and check for "No Data"
        has_no_data = False
        if widget:
            # Get widget HTML directly from Selenium (if not already got via JavaScript)
            if not widget_soup:
                widget_html = widget.get_attribute('outerHTML')
                widget_soup = BeautifulSoup(widget_html, 'html.parser')
                logger.debug(f"📝 Created widget_soup from outerHTML (length: {len(widget_html)})")
            else:
                widget_html = str(widget_soup)
                logger.debug(f"📝 Using existing widget_soup (length: {len(widget_html)})")
            
            # Save widget HTML for debugging (only if needed)
            # Commented out to reduce I/O overhead
            # widget_debug_file = os.path.join(os.path.dirname(__file__), 'debug_widget.html')
            # try:
            #     with open(widget_debug_file, 'w', encoding='utf-8') as f:
            #         f.write(widget_html)
            # except Exception as e:
            #     pass
            
            # Get text using JavaScript to ensure we get rendered content (including Knockout.js bound data)
            widget_text = driver.execute_script("""
                var widget = arguments[0];
                if (!widget) return '';
                return widget.textContent || widget.innerText || '';
            """, widget)
            
            # Also get the HTML to check for content
            widget_html_content = widget.get_attribute('innerHTML') or widget.get_attribute('outerHTML') or ''
            
            logger.debug(f"📊 Widget text length: {len(widget_text)}, HTML length: {len(widget_html_content)}")
            
            # Check for "No Data" in widget text or HTML
            if 'No Data' in widget_text or '<h4 class=alert alert-warning>No Data</h4>' in widget_html_content:
                has_no_data = True
                logger.info("📭 Found 'No Data' in widget")
            else:
                # Check for table rows with actual data in the HTML
                # Look for table rows that contain opportunity data (not just empty rows)
                try:
                    # Use JavaScript to find table rows with actual content
                    row_count = driver.execute_script("""
                        var widget = arguments[0];
                        if (!widget) return 0;
                        var rows = widget.querySelectorAll('table tbody tr');
                        var count = 0;
                        for (var i = 0; i < rows.length; i++) {
                            var rowText = rows[i].textContent || rows[i].innerText || '';
                            // Check if row has meaningful content (not just whitespace or "No Data")
                            if (rowText.trim().length > 5 && !rowText.includes('No Data')) {
                                count++;
                            }
                        }
                        return count;
                    """, widget)
                    
                    logger.debug(f"📊 Found {row_count} table rows with content")
                    
                    if row_count == 0:
                        # Also check HTML directly for opportunity names
                        if 'OpportunityName' in widget_html_content or 'Reliance' in widget_html_content or 'Download' in widget_html_content:
                            # HTML contains opportunity data even if text extraction failed
                            logger.info("✅ Found opportunity data in HTML - opportunities exist")
                            has_no_data = False
                        else:
                            has_no_data = True
                            logger.debug("📭 No table rows with content found - assuming 'No Data'")
                    else:
                        logger.debug(f"✅ Found {row_count} table rows with content - opportunities exist")
                        has_no_data = False
                except Exception as e:
                    logger.debug(f"Could not check table rows: {e}")
                    # Fallback: check HTML for opportunity indicators
                    if 'OpportunityName' in widget_html_content or 'Reliance' in widget_html_content:
                        logger.debug("✅ Found opportunity indicators in HTML - opportunities exist")
                        has_no_data = False
                    else:
                        logger.debug("⚠️  Could not determine opportunity status from widget")
        else:
            # Widget not found - check page source for "No Data"
            logger.warning("⚠️  Widget not found, checking page source for 'No Data'")
            page_source = driver.page_source
            if 'No Data' in page_source:
                # Check if it's in opportunity context
                no_data_pattern = r'(?:opportunityannouncementwidget|Program Announcement|opportunity.*announcement).{0,500}No Data|No Data.{0,500}(?:opportunityannouncementwidget|Program Announcement|opportunity.*announcement)'
                if re.search(no_data_pattern, page_source, re.IGNORECASE):
                    has_no_data = True
                    logger.info("📭 Found 'No Data' in page source (opportunity context)")
        
        # Determine if opportunities exist
        has_opportunities = not has_no_data
        
        # Get full page HTML for parsing - wait a moment for any final rendering
        if widget:
            # Scroll widget into view to ensure it's fully rendered
            driver.execute_script("arguments[0].scrollIntoView(true);", widget)
            time.sleep(0.5)
        
        page_html = driver.page_source
        soup = BeautifulSoup(page_html, 'html.parser')
        
        # Save page source for debugging (only if needed - commented out to reduce I/O)
        # debug_file = os.path.join(os.path.dirname(__file__), 'debug_selenium_page.html')
        # try:
        #     current_url = driver.current_url
        #     page_title = driver.title
        #     with open(debug_file, 'w', encoding='utf-8') as f:
        #         f.write(f"<!-- URL: {current_url} -->\n")
        #         f.write(f"<!-- Title: {page_title} -->\n")
        #         f.write(f"<!-- Widget Found: {widget is not None} -->\n")
        #         f.write(page_html)
        # except Exception as e:
        #     pass
        
        # Always inject widget into soup if we found it (for extract_opportunities to find it)
        if widget and widget_soup:
            # Check if widget is already in page_source
            existing_widget = soup.find('div', id='opportunityannouncementwidget')
            if existing_widget:
                # Replace with our extracted version (which might be more complete)
                widget_elem = widget_soup.find('div', id='opportunityannouncementwidget')
                if widget_elem:
                    existing_widget.replace_with(widget_elem)
                    logger.info("✅ Replaced widget in soup with extracted version")
            else:
                # Widget not in page_source, inject it
                logger.info("📝 Injecting widget into soup (not in page_source)")
                container = soup.find('div', id='widget_landing') or soup.find('div', class_='accordion') or soup.find('body')
                if container:
                    widget_elem = widget_soup.find('div', id='opportunityannouncementwidget')
                    if widget_elem:
                        container.append(widget_elem)
                        logger.info("✅ Widget injected into soup")
        
        logger.debug(f"📊 Has opportunities: {has_opportunities}")
        if not widget:
            logger.warning("⚠️  Widget not found in DOM")
        
        # Extract opportunity names if opportunities exist
        opportunity_names = []
        if has_opportunities and widget_soup:
            try:
                # Look for table rows with opportunity data
                tables = widget_soup.find_all('table')
                
                for table in tables:
                    # Look for tbody rows (header is in thead, so all tbody rows are data)
                    tbody = table.find('tbody')
                    if tbody:
                        rows = tbody.find_all('tr')
                    else:
                        # Fallback: skip first row if no tbody
                        rows = table.find_all('tr')[1:]
                    
                    for row in rows:
                        cells = row.find_all('td')
                        if len(cells) >= 1:
                            opportunity_name = cells[0].get_text(strip=True)
                            if opportunity_name and opportunity_name != "No Data" and len(opportunity_name) > 0:
                                opportunity_names.append(opportunity_name)
                                logger.debug(f"📋 Extracted opportunity: {opportunity_name}")
                
                if not opportunity_names:
                    logger.warning("⚠️  No opportunity names extracted - trying alternative method")
                    # Try using JavaScript to extract from the actual DOM
                    if widget:
                        try:
                            js_opportunities = driver.execute_script("""
                                var widget = arguments[0];
                                if (!widget) return [];
                                var opportunities = [];
                                var rows = widget.querySelectorAll('table tbody tr');
                                for (var i = 0; i < rows.length; i++) {
                                    var cells = rows[i].querySelectorAll('td');
                                    if (cells.length > 0) {
                                        var oppName = (cells[0].textContent || cells[0].innerText || '').trim();
                                        if (oppName && oppName !== 'No Data' && oppName.length > 0) {
                                            opportunities.push(oppName);
                                        }
                                    }
                                }
                                return opportunities;
                            """, widget)
                            if js_opportunities:
                                opportunity_names = js_opportunities
                                logger.debug(f"📋 Extracted {len(opportunity_names)} opportunity(ies) via JavaScript")
                        except Exception as js_e:
                            logger.debug(f"JavaScript extraction also failed: {js_e}")
            except Exception as e:
                logger.warning(f"⚠️  Could not extract opportunity names: {e}")
                import traceback
                logger.debug(traceback.format_exc())
        
        return soup, has_opportunities, opportunity_names
            
    except Exception as e:
        logger.error(f"❌ Selenium reference page load failed: {e}")
        return None, False, []
    finally:
        if driver:
            driver.quit()
