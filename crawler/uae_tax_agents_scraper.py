import asyncio
import re
import csv
import os
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd


class UAETaxAgentsScraper:
    def __init__(self, headless=True):
        self.base_url = "https://tax.gov.ae/en/tax.support/tax.agents/registered.tax.agents.aspx"
        self.driver = None
        self.headless = headless
        self.all_records = []
        
    def setup_driver(self):
        """Initialize Selenium WebDriver with Chrome"""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        print("WebDriver initialized successfully")
        
    def extract_records_from_page(self, page_source):
        """Extract establishment records from the current page HTML"""
        soup = BeautifulSoup(page_source, 'html.parser')
        records = []
        
        # Debug: Check if we're getting the right HTML
        # Save page source for debugging
        with open('debug_page.html', 'w', encoding='utf-8') as f:
            f.write(page_source)
        
        # Find all establishment containers - updated selector based on actual HTML
        establishments = soup.find_all('li', class_='taxAgentListItem')
        
        print(f"Found {len(establishments)} establishment containers")
        
        for establishment in establishments:
            try:
                # Extract TAAN number
                taan_elem = establishment.find('h3')
                taan_number = ""
                if taan_elem:
                    taan_text = taan_elem.get_text(strip=True)
                    taan_match = re.search(r'TAAN:\s*(\d+)', taan_text)
                    if taan_match:
                        taan_number = taan_match.group(1)
                
                # Extract agent name from h2 tag
                agent_name_elem = establishment.find('h2')
                agent_name = agent_name_elem.get_text(strip=True) if agent_name_elem else ""
                
                # Extract establishment/company name from div with class 'company'
                company_div = establishment.find('div', class_='company')
                establishment_name = ""
                if company_div:
                    # Get the company name (text directly in the div, not in child elements)
                    company_text = company_div.get_text(separator='\n', strip=True).split('\n')
                    if company_text:
                        establishment_name = company_text[0].strip()
                
                # Extract location from branchLocation paragraph
                location_elem = establishment.find('p', class_='branchLocation')
                location = location_elem.get_text(strip=True) if location_elem else ""
                
                # Extract website
                website = ""
                website_link = establishment.find('a', href=True, string=re.compile(r'http|www', re.I))
                if not website_link:
                    # Try to find website in the establishment details
                    for link in establishment.find_all('a', href=True):
                        href = link.get('href', '')
                        if 'http' in href or 'www' in href:
                            website = href
                            break
                else:
                    website = website_link.get('href', '')
                
                # Extract emails
                emails = []
                email_links = establishment.find_all('a', href=re.compile(r'^mailto:', re.I))
                for email_link in email_links:
                    email = email_link.get('href', '').replace('mailto:', '').strip()
                    if email and '@' in email:
                        emails.append(email)
                
                # Also look for emails in text
                text_content = establishment.get_text()
                email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
                text_emails = re.findall(email_pattern, text_content)
                emails.extend([e for e in text_emails if e not in emails])
                
                # Extract phone numbers
                phones = []
                phone_links = establishment.find_all('a', href=re.compile(r'^tel:', re.I))
                for phone_link in phone_links:
                    phone = phone_link.get('href', '').replace('tel:', '').strip()
                    if phone:
                        phones.append(phone)
                
                # Also look for phone numbers in text
                phone_pattern = r'\+971[\s-]?\d{1,2}[\s-]?\d{7,8}'
                text_phones = re.findall(phone_pattern, text_content)
                phones.extend([p for p in text_phones if p not in phones])
                
                # Create a single record per establishment with all details
                # Join multiple emails and phones with semicolon
                all_emails = '; '.join(emails) if emails else ''
                all_phones = '; '.join(phones) if phones else ''
                
                records.append({
                    'taan_number': taan_number,
                    'agent_name': agent_name,  # Member/agent name
                    'establishment_name': establishment_name,
                    'location': location,
                    'website': website,
                    'emails': all_emails,  # All emails concatenated
                    'phones': all_phones,  # All phones concatenated
                    'extraction_timestamp': datetime.now().isoformat()
                })
                    
            except Exception as e:
                print(f"Error extracting establishment data: {e}")
                continue
                
        return records
    
    def click_page_button(self, page_number):
        """Click on a specific page number using various navigation methods"""
        try:
            # Wait for pagination to be present
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "RadDataPager"))
            )
            
            if page_number == 1:
                # First page is usually already loaded
                return True
                
            # Try different methods to navigate to the page
            
            # Method 1: Try to find and click the page button directly
            try:
                page_button = self.driver.find_element(
                    By.XPATH, 
                    f"//a[contains(@class, 'rdpPageButton') and text()='{page_number}']"
                )
                self.driver.execute_script("arguments[0].click();", page_button)
                time.sleep(3)  # Wait longer for page to fully load
                print(f"Successfully navigated to page {page_number} using direct button click")
                return True
            except NoSuchElementException:
                print(f"Page button {page_number} not directly visible")
            
            # Method 2: Click on the page link using href javascript
            try:
                # Find link with javascript:__doPostBack pattern
                page_links = self.driver.find_elements(
                    By.XPATH, 
                    f"//a[contains(@href, 'PageButton{page_number}')]"
                )
                if page_links:
                    # Click the first matching link
                    page_links[0].click()
                    time.sleep(3)  # Wait longer for page to fully load
                    print(f"Successfully navigated to page {page_number} using href link")
                    return True
            except Exception as e:
                print(f"Error clicking page link: {e}")
            
            # Method 3: Use Next button to navigate sequentially
            if page_number > 1:
                print(f"Attempting to reach page {page_number} using Next button")
                for _ in range(page_number - 1):
                    try:
                        # Find the Next button
                        next_button = self.driver.find_element(
                            By.XPATH,
                            "//a[contains(@href, 'LinkButtonNext') or contains(@class, 'rdpPageNext')]"
                        )
                        # Scroll to button and click
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                        time.sleep(0.5)
                        next_button.click()
                        time.sleep(3)  # Wait longer for page to fully load
                        print(f"Clicked Next button, now on page {_ + 2}")
                    except NoSuchElementException:
                        print(f"Could not find Next button")
                        return False
                    except Exception as e:
                        print(f"Error clicking Next button: {e}")
                        return False
                        
                return True
                
        except TimeoutException:
            print(f"Timeout waiting for pagination controls on page {page_number}")
            return False
        except Exception as e:
            print(f"Error clicking page {page_number}: {e}")
            return False
    
    def get_total_pages(self):
        """Get the total number of pages from the pagination control"""
        try:
            # Wait for pagination to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "RadDataPager"))
            )
            
            # First try to find the "Last" button which contains the total page count
            try:
                last_button = self.driver.find_element(By.CSS_SELECTOR, "a.rdpPageLast")
                if last_button:
                    # Extract page number from the href or onclick attribute
                    href = last_button.get_attribute('href')
                    if href:
                        # Look for PageButton61 pattern in href
                        match = re.search(r'PageButton(\d+)', href)
                        if match:
                            return int(match.group(1))
            except NoSuchElementException:
                pass
            
            # Try to find page info text like "Page 1 of 61"
            try:
                page_info_elements = self.driver.find_elements(By.CSS_SELECTOR, ".rdpWrap, .rdpPagerLabel")
                for elem in page_info_elements:
                    text = elem.text
                    # Look for patterns like "Page 1 of 61" or "1 of 61"
                    match = re.search(r'(?:Page\s+)?\d+\s+of\s+(\d+)', text, re.IGNORECASE)
                    if match:
                        total = int(match.group(1))
                        print(f"Found total pages from page info: {total}")
                        return total
            except Exception:
                pass
            
            # Try to find the last visible page number button
            page_buttons = self.driver.find_elements(By.CSS_SELECTOR, "a.rdpPageButton")
            if page_buttons:
                # Get the last visible page number
                last_page_text = page_buttons[-1].text
                if last_page_text.isdigit():
                    # If we see page 10, there might be more pages
                    # Check if there's a next/ellipsis indicator
                    try:
                        next_button = self.driver.find_element(By.CSS_SELECTOR, "a.rdpPageNext:not(.aspNetDisabled)")
                        if next_button:
                            # If next button exists and is enabled, there are more pages
                            # Return a higher number to continue scraping
                            print("Next button found, more pages available")
                            return 61  # Use the known total
                    except NoSuchElementException:
                        pass
                    return int(last_page_text)
                    
        except Exception as e:
            print(f"Error getting total pages: {e}")
            
        # Default to 61 pages since we know that's the actual count
        print("Using default page count of 61")
        return 61
    
    def scrape_all_pages(self, max_pages=None):
        """Scrape all pages or up to max_pages"""
        try:
            self.setup_driver()
            
            # Navigate to the base URL
            print(f"Navigating to {self.base_url}")
            self.driver.get(self.base_url)
            
            # Wait for the data to load
            try:
                # Wait for either the list view or the establishment containers
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".RadListView, .agentouter, .agentlist"))
                )
                print("Page loaded, waiting for data...")
                time.sleep(3)  # Wait longer for all dynamic content to load
            except TimeoutException:
                print("Warning: Could not find expected elements, continuing anyway...")
                time.sleep(2)
            
            # Get total pages
            total_pages = self.get_total_pages()
            print(f"Total pages detected: {total_pages}")
            
            if max_pages:
                total_pages = min(total_pages, max_pages)
                print(f"Limiting to {total_pages} pages")
            
            # Scrape each page
            for page_num in range(1, total_pages + 1):
                print(f"\nScraping page {page_num}/{total_pages}")
                
                if page_num > 1:
                    # Navigate to the next page
                    if not self.click_page_button(page_num):
                        print(f"Failed to navigate to page {page_num}, continuing...")
                        continue
                
                # Extract data from current page
                page_records = self.extract_records_from_page(self.driver.page_source)
                self.all_records.extend(page_records)
                print(f"Extracted {len(page_records)} records from page {page_num}")
                
                # Small delay between pages to avoid overwhelming the server
                time.sleep(1)
                
        except Exception as e:
            print(f"Error during scraping: {e}")
        finally:
            if self.driver:
                self.driver.quit()
                print("WebDriver closed")
    
    def save_to_csv(self, filename='uae_tax_agents_full.csv'):
        """Save all scraped records to CSV"""
        if not self.all_records:
            print("No records to save")
            return None
            
        fieldnames = ['taan_number', 'agent_name', 'establishment_name', 'location', 'website', 'emails', 'phones', 'extraction_timestamp']
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for record in self.all_records:
                writer.writerow(record)
        
        print(f"\nSaved {len(self.all_records)} records to {filename}")
        
        # Show summary statistics
        df = pd.DataFrame(self.all_records)
        unique_establishments = df['establishment_name'].nunique()
        records_with_email = len(df[df['emails'] != ''])
        records_with_phone = len(df[df['phones'] != ''])
        
        print(f"\nSummary:")
        print(f"- Total records: {len(self.all_records)}")
        print(f"- Unique establishments: {unique_establishments}")
        print(f"- Records with email: {records_with_email}")
        print(f"- Records with phone: {records_with_phone}")
        
        return filename


async def main():
    """Main function to run the scraper"""
    scraper = UAETaxAgentsScraper(headless=False)  # Set to True for headless mode
    
    # Scrape first 3 pages to test pagination
    scraper.scrape_all_pages(max_pages=61)
    
    # Save results to CSV
    csv_file = scraper.save_to_csv('uae_tax_agents_test.csv')
    
    if csv_file:
        # Display first few records
        df = pd.read_csv(csv_file)
        print(f"\nFirst 5 records from {csv_file}:")
        print(df.head().to_string(index=False))


if __name__ == "__main__":
    # For regular Python script
    asyncio.run(main())