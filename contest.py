import urllib.parse
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import logging
import random
import pandas as pd
from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def setup_selenium_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--log-level=3")
    return webdriver.Chrome(options=chrome_options)

def get_usernames_and_contest_data(contest_code, institution, max_pages_limit=20, max_retries=3):
    users_data = []
    seen_usernames = set()  # Track unique usernames to prevent duplicates
    institution_encoded = urllib.parse.quote(institution)
    page = 1
    driver = setup_selenium_driver()
    problem_columns = []

    try:
        while page <= max_pages_limit:
            url = (
                f"https://www.codechef.com/rankings/{contest_code}"
                f"?filterBy=Institution%3D{institution_encoded}"
                f"&itemsPerPage=100&order=asc&page={page}&sortBy=rank"
            )
            logging.info(f"Fetching page {page}: {url}")

            for attempt in range(max_retries):
                try:
                    driver.get(url)
                    wait = WebDriverWait(driver, 30)
                    wait.until_not(EC.presence_of_element_located((By.CLASS_NAME, "loadingIcon")))
                    time.sleep(2)
                    break
                except Exception as e:
                    logging.warning(f"Attempt {attempt + 1}/{max_retries} failed for page {page}: {e}")
                    if attempt + 1 == max_retries:
                        logging.error(f"Max retries reached for page {page}, skipping")
                        return users_data
                    time.sleep(2 ** attempt + random.uniform(2.0, 5.0))

            soup = BeautifulSoup(driver.page_source, "html.parser")
            page_text = soup.get_text().lower()
            if "no results" in page_text or "no users" in page_text or "0 results" in page_text:
                logging.info(f"No results found on page {page}")
                break

            table = soup.find("table", class_=re.compile(r"MuiTable-root.*MUIDataTable-tableRoot"))
            if not table:
                logging.error(f"No table found on page {page}. Page title: {soup.title.get_text() if soup.title else 'No title'}")
                break

            # Extract problem numbers from table headers
            if not problem_columns:  # Only extract headers once
                header_row = table.find("tr", class_=re.compile(r"MuiTableRow-root.*MuiTableRow-head"))
                if header_row:
                    headers = header_row.find_all("th")
                    for index, header in enumerate(headers):
                        problem_label = header.find("a", class_=re.compile(r"_problems__link"))
                        if problem_label and re.match(r"P\d+", problem_label.get_text(strip=True)):
                            problem_columns.append((problem_label.get_text(strip=True), index))
                # Ensure P1–P8 are included, even if not in headers
                existing_problems = {p[0] for p in problem_columns}
                for i in range(1, 9):  # P1 to P8
                    problem = f"P{i}"
                    if problem not in existing_problems:
                        problem_columns.append((problem, None))

            rows = table.find_all("tr", class_=re.compile(r"MuiTableRow-root.*MUIDataTableBodyRow-root"))
            if len(rows) <= 0:
                logging.warning(f"No data rows found on page {page}")
                break

            page_usernames = set()
            for row in rows:
                username_cell = row.find("td", {"data-colindex": "1"})
                if username_cell:
                    username_link = username_cell.find("a", href=re.compile(r"/users/"))
                    if username_link:
                        username = username_link.find("span", class_="m-username--link").get_text(strip=True) if username_link.find("span", class_="m-username--link") else username_link.get("title", "")
                        if username and username not in seen_usernames:  # Check for duplicates
                            seen_usernames.add(username)
                            user_data = {
                                "Username": username,
                                "Rank": row.find("td", {"data-colindex": "0"}).find("p").get_text(strip=True) if row.find("td", {"data-colindex": "0"}) else "N/A",
                                "Total Score": row.find("td", {"data-colindex": "2"}).find("div", recursive=False).get_text(strip=True) if row.find("td", {"data-colindex": "2"}) else "N/A",
                                "Last AC": row.find("td", {"data-colindex": "3"}).find("p").get_text(strip=True) if row.find("td", {"data-colindex": "3"}) else "N/A"
                            }
                            # Extract scores for each problem
                            problem_scores = []
                            for problem, col_index in problem_columns:
                                if col_index is not None:
                                    cell = row.find("td", {"data-colindex": str(col_index)})
                                    score = cell.find("a").get_text(strip=True) if cell and cell.find("a") else "-"
                                else:
                                    score = "-"  # For P5–P8 if not in table
                                user_data[problem] = score
                                problem_scores.append(score)
                            # Count problems solved (only for actual problems in table)
                            user_data["Problems Solved"] = sum(1 for score in problem_scores[:len([p for p, idx in problem_columns if idx is not None])] if score != "-")
                            users_data.append(user_data)
                            page_usernames.add(username)

            new_users = len(page_usernames)
            logging.info(f"Extracted {new_users} users from page {page}. Total so far: {len(users_data)}")

            if new_users == 0:
                logging.info(f"No new users on page {page}, stopping")
                break
            if len(page_usernames) < 100 and page > 1:
                logging.info(f"Partial page {page} ({len(page_usernames)} users < 100), likely last page")
                break

            next_button = soup.find("button", {"aria-label": re.compile(r"Go to next page", re.I)}) or \
                          soup.find("button", string=re.compile(r"Next", re.I)) or \
                          soup.find("button", class_=re.compile(r"MuiPaginationItem.*next"))
            if not next_button or ("disabled" in next_button.get("class", []) or next_button.get("disabled") or "true" in next_button.get("aria-disabled", "")):
                logging.info("Next button disabled or not found - no more pages")
                break

            page += 1
            time.sleep(random.uniform(2.0, 5.0))

    except Exception as e:
        logging.error(f"Error during extraction: {e}")
    finally:
        driver.quit()

    return users_data, [p[0] for p in problem_columns]

def print_and_save_contest_data(users_data, contest_code, problem_columns):
    if not users_data:
        print(f"No users found for contest {contest_code}")
        return

    print(f"\n✅ Found {len(users_data)} users in contest {contest_code}")
    for user in users_data:
        print(f"\nUser: {user['Username']}")
        print(f"Rank: {user['Rank']}")
        print(f"Total Score: {user['Total Score']}")
        print(f"Last AC: {user['Last AC']}")
        print(f"Problems Solved: {user['Problems Solved']}")
        for problem in problem_columns:
            print(f"{problem}: {user[problem]}")

    # Save to Excel
    df = pd.DataFrame(users_data)
    excel_filename = f"codechef_{contest_code}_contest_data.xlsx"
    df.to_excel(excel_filename, index=False, engine='openpyxl')
    logging.info(f"Contest data saved to {excel_filename}")
    print(f"\nData saved to {excel_filename}")

# ------------------ MAIN ------------------ #
if __name__ == "__main__":
    contest_code = "START202D"
    institution = "Sri Eshwar College of Engineering, Kinathukadavu"
    
    users_data, problem_columns = get_usernames_and_contest_data(contest_code, institution)
    print_and_save_contest_data(users_data, contest_code, problem_columns)