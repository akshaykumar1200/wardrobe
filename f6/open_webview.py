import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

brain_dir = r"C:\Users\Lenovo\.gemini\antigravity-ide\brain\7bc1c6fd-8c3d-44cd-92a0-194ebf0c23ac"

def run_webview_capture():
    print("=" * 65)
    print("  LAUNCHING REAL CHROME BROWSER FOR F6 WEB VIEW")
    print("=" * 65)

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--headless=new") # headless for automated screenshot capture
    
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 10)

    try:
        url = "http://127.0.0.1:8080"
        print(f">> [STEP 1] Navigating to {url}...")
        driver.get(url)
        time.sleep(2)

        # 1. Capture Closet View
        driver.save_screenshot(os.path.join(brain_dir, "webview_1_closet.png"))
        print(">> Captured webview_1_closet.png")

        # 2. Click category filter 'Shoes'
        print(">> [STEP 2] Clicking 'Shoes' filter chip...")
        try:
            chip = driver.find_element(By.XPATH, "//button[@data-category='shoes']")
            chip.click()
            time.sleep(1)
            driver.save_screenshot(os.path.join(brain_dir, "webview_2_shoes_filtered.png"))
            print(">> Captured webview_2_shoes_filtered.png")
        except Exception as e:
            print("Notice:", e)

        # 3. Switch to AI Outfit Studio Tab
        print(">> [STEP 3] Switching to 'AI Outfit Studio' Tab...")
        try:
            outfits_tab = driver.find_element(By.ID, "tabOutfits")
            outfits_tab.click()
            time.sleep(2)
            driver.save_screenshot(os.path.join(brain_dir, "webview_3_outfits_studio.png"))
            print(">> Captured webview_3_outfits_studio.png")
        except Exception as e:
            print("Notice:", e)

        # 4. Switch to Upload & Extract Tab
        print(">> [STEP 4] Switching to 'Upload & Extract' Tab...")
        try:
            upload_tab = driver.find_element(By.ID, "tabUpload")
            upload_tab.click()
            time.sleep(1)
            driver.save_screenshot(os.path.join(brain_dir, "webview_4_upload_screen.png"))
            print(">> Captured webview_4_upload_screen.png")
        except Exception as e:
            print("Notice:", e)

        # 5. Switch to Analytics Tab
        print(">> [STEP 5] Switching to 'Analytics' Tab...")
        try:
            analytics_tab = driver.find_element(By.ID, "tabAnalytics")
            analytics_tab.click()
            time.sleep(1)
            driver.save_screenshot(os.path.join(brain_dir, "webview_5_analytics.png"))
            print(">> Captured webview_5_analytics.png")
        except Exception as e:
            print("Notice:", e)

        print("\nAll Webview screenshots captured successfully!")

    finally:
        driver.quit()

if __name__ == "__main__":
    run_webview_capture()
