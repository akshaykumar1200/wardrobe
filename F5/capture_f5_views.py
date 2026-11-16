import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By

brain_dir = r"C:\Users\Lenovo\.gemini\antigravity-ide\brain\7bc1c6fd-8c3d-44cd-92a0-194ebf0c23ac"

def capture():
    print("Launching Chrome for F5 screenshots...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,900")
    
    driver = webdriver.Chrome(options=options)
    try:
        print("Loading http://127.0.0.1:8000...")
        driver.get("http://127.0.0.1:8000")
        time.sleep(2)
        driver.save_screenshot(os.path.join(brain_dir, "f5_webview_main.png"))
        print("Saved f5_webview_main.png")

        # Click Outfit Generator button
        print("Clicking Outfit Generator button...")
        btn_suggest = driver.find_element(By.XPATH, "//button[contains(text(), 'Outfit Generator')]")
        btn_suggest.click()
        time.sleep(2)
        driver.save_screenshot(os.path.join(brain_dir, "f5_webview_outfit_modal.png"))
        print("Saved f5_webview_outfit_modal.png")

    finally:
        driver.quit()
        print("Done capturing F5!")

if __name__ == "__main__":
    capture()
