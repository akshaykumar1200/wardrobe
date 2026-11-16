import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By

brain_dir = r"C:\Users\Lenovo\.gemini\antigravity-ide\brain\7bc1c6fd-8c3d-44cd-92a0-194ebf0c23ac"

def capture():
    print("Launching Chrome for screenshots...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1440,900")
    
    driver = webdriver.Chrome(options=options)
    try:
        print("Loading http://127.0.0.1:8080...")
        driver.get("http://127.0.0.1:8080")
        time.sleep(2)
        driver.save_screenshot(os.path.join(brain_dir, "f6_webview_closet.png"))
        print("Saved f6_webview_closet.png")

        # Click tabOutfits
        btn_outfits = driver.find_element(By.ID, "tabOutfits")
        btn_outfits.click()
        time.sleep(2)
        driver.save_screenshot(os.path.join(brain_dir, "f6_webview_outfits.png"))
        print("Saved f6_webview_outfits.png")

        # Click tabUpload
        btn_upload = driver.find_element(By.ID, "tabUpload")
        btn_upload.click()
        time.sleep(1)
        driver.save_screenshot(os.path.join(brain_dir, "f6_webview_upload.png"))
        print("Saved f6_webview_upload.png")

        # Click tabAnalytics
        btn_analytics = driver.find_element(By.ID, "tabAnalytics")
        btn_analytics.click()
        time.sleep(1)
        driver.save_screenshot(os.path.join(brain_dir, "f6_webview_analytics.png"))
        print("Saved f6_webview_analytics.png")

    finally:
        driver.quit()
        print("Done!")

if __name__ == "__main__":
    capture()
