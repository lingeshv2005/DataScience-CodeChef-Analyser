from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def setup_driver(headless=False):
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    service = Service()
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def close_joyride(driver):
    try:
        wait = WebDriverWait(driver, 5)
        ok_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[title='Close'][data-action='close']"))
        )
        ok_button.click()
        time.sleep(0.5)
    except:
        pass

def play_replay(driver):
    try:
        wait = WebDriverWait(driver, 15)
        # Locate the button wrapping the play icon
        play_button = wait.until(
            EC.presence_of_element_located((By.XPATH, "//div[@role='dialog']//button[.//svg[@data-icon='play']]"))
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", play_button)
        time.sleep(0.3)
        # Click using JS to bypass potential overlay issues
        driver.execute_script("arguments[0].click();", play_button)
        print("Replay started")
    except Exception as e:
        print("Could not click play button:", e)

def wait_for_replay_finish(driver):
    try:
        dialog = driver.find_element(By.CSS_SELECTOR, "div[role='dialog']")
        timeline = dialog.find_element(By.CSS_SELECTOR, "div[class*='group'][class*='timeline']")
        dots = timeline.find_elements(By.CSS_SELECTOR, "div.event-dot")
        if not dots:
            print("No timeline dots found; replay may not have started.")
            return

        last_dot = dots[-1]
        max_wait = 120
        elapsed = 0
        while elapsed < max_wait:
            style = last_dot.get_attribute("style") or ""
            if "100%" in style or "left: 100%" in style:
                break
            time.sleep(0.5)
            elapsed += 0.5
        time.sleep(1)
        print("Replay finished")
    except Exception as e:
        print("Error waiting for replay finish:", e)

def get_code_from_dialog(driver):
    try:
        code_container = driver.find_element(By.CSS_SELECTOR, "div.cm-content")
        code_lines = code_container.find_elements(By.CSS_SELECTOR, "div.cm-line")
        code_text = "\n".join([line.text for line in code_lines])
        return code_text
    except Exception as e:
        print("Error extracting code:", e)
        return ""

def main():
    url = "https://leetcode.com/contest/weekly-contest-468/ranking/400/?region=global_v2"
    driver = setup_driver(headless=False)
    driver.get(url)
    wait = WebDriverWait(driver, 30)

    wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.ranking-guide-anchor")))

    close_joyride(driver)

    replay_buttons = driver.find_elements(By.CSS_SELECTOR, "div.ranking-guide-anchor")
    if not replay_buttons:
        print("No replay buttons found!")
        driver.quit()
        return

    target_button = replay_buttons[0]
    driver.execute_script("arguments[0].scrollIntoView(true);", target_button)
    time.sleep(0.5)
    target_button.click()

    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='dialog']")))

    play_replay(driver)
    wait_for_replay_finish(driver)

    code_text = get_code_from_dialog(driver)
    print("----- CODE AT END -----")
    print(code_text)
    print("----------------------")

    with open("leetcode_code_end.txt", "w", encoding="utf-8") as f:
        f.write(code_text)

    driver.quit()

if __name__ == "__main__":
    main()
