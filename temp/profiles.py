import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import logging
import openpyxl
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def save_to_excel(users, file_path):
    try:
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "CodeChef Users"
        
        # Add header
        sheet['A1'] = "Username"
        
        # Add usernames
        for idx, username in enumerate(users, start=2):
            sheet[f'A{idx}'] = username
        
        # Save the file
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)  # Create directory if it doesn't exist
        workbook.save(file_path)
        logging.info(f"Saved {len(users)} users to {file_path}")
    except Exception as e:
        logging.error(f"Failed to save to Excel file {file_path}: {e}")

def get_usernames_from_institution(institution, max_pages_limit=20):
    usernames = set()  # Use set to avoid duplicates
    institution_encoded = urllib.parse.quote(institution)
    page = 1
    previous_total = 0

    # Set up Chrome options for headless mode
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-gpu")  # Helps with compatibility
    chrome_options.add_argument("--log-level=3")  # Suppress unnecessary logs

    driver = webdriver.Chrome(options=chrome_options)

    try:
        while page <= max_pages_limit:
            url = (
                f"https://www.codechef.com/ratings/all"
                f"?filterBy=Institution%3D{institution_encoded}"
                f"&itemsPerPage=50&order=asc&page={page}&sortBy=global_rank"
            )
            logging.info(f"Fetching page {page}: {url}")

            driver.get(url)

            # Wait for the loading spinner to disappear and the table to load
            try:
                wait = WebDriverWait(driver, 30)
                wait.until_not(EC.presence_of_element_located((By.CLASS_NAME, "loadingIcon")))
                time.sleep(2)  # Additional wait for table stability
            except Exception as e:
                logging.warning(f"Wait timeout on page {page}: {e}")
                break

            # Parse the page source
            soup = BeautifulSoup(driver.page_source, "html.parser")

            # Check for "no results" or empty page indicators
            page_text = soup.get_text().lower()
            if "no results" in page_text or "no users" in page_text or "0 results" in page_text:
                logging.info(f"No results found on page {page}")
                break

            # Look for the table with Material-UI DataTable class
            table = soup.find("table", class_=re.compile(r"MuiTable-root.*MUIDataTable-tableRoot"))
            if not table:
                table = soup.find("table")
                if not table:
                    logging.error(f"No table found on page {page}. Page title: {soup.title.get_text() if soup.title else 'No title'}")
                    break

            logging.info(f"Table found on page {page}, extracting rows...")

            rows = table.find_all("tr")
            if len(rows) <= 1:
                logging.warning(f"No data rows found on page {page}")
                break

            page_usernames = set()  # Track for this page only
            for row in rows[1:]:  # Skip header row
                first_td = row.find("td", {"data-colindex": "0"})
                if first_td:
                    link = first_td.find("a", href=re.compile(r"/users/"))
                    if link:
                        username_span = link.find("span", class_="m-username--link")
                        if username_span:
                            username = username_span.get_text(strip=True)
                            page_usernames.add(username)
                        else:
                            title = link.get("title", "")
                            if title:
                                page_usernames.add(title)

            new_users = len(page_usernames - usernames)
            usernames.update(page_usernames)
            logging.info(f"Extracted {len(page_usernames)} users from page {page} ({new_users} new). Total so far: {len(usernames)}")

            # Stop if no new users added (repeats detected) or fewer than expected (last page)
            if new_users == 0:
                logging.info(f"No new users on page {page} (repeats detected), stopping")
                break
            if len(page_usernames) < 50 and page > 1:
                logging.info(f"Partial page {page} ({len(page_usernames)} users < 50), likely last page - checking next")
                # Check next page quickly to confirm
                next_url = url.replace(f"page={page}", f"page={page+1}")
                try:
                    next_response = requests.head(next_url, timeout=10)
                    if next_response.status_code != 200:
                        logging.info(f"Next page {page+1} does not exist (status {next_response.status_code})")
                        break
                except:
                    pass  # Continue if check fails

            # Improved next button check: Look for disabled state, aria-label, or text
            next_button = soup.find("button", {"aria-label": re.compile(r"Go to next page", re.I)}) or \
                          soup.find("button", string=re.compile(r"Next", re.I)) or \
                          soup.find("button", class_=re.compile(r"MuiPaginationItem.*next"))
            if not next_button or ("disabled" in next_button.get("class", []) or next_button.get("disabled") or "false" in next_button.get("aria-disabled", "")):
                logging.info("Next button disabled or not found - no more pages")
                break

            page += 1

    except Exception as e:
        logging.error(f"Error during extraction: {e}")
    finally:
        driver.quit()

    return sorted(list(usernames))  # Return sorted list for consistency

# ------------------ MAIN ------------------ #
if __name__ == "__main__":
    institution = "Sri Eshwar College of Engineering, Kinathukadavu"
    output_file = r"C:\AllOther\Python\CodeChef\profiles.xlsx"
    
    users = get_usernames_from_institution(institution)
    
    if users:
        save_to_excel(users, output_file)
    else:
        logging.warning(f"No users found for {institution}, skipping Excel file creation")
    
    logging.info(f"Found {len(users)} users from {institution}")
    print(f"✅ Found {len(users)} users from {institution}")
    print(users)