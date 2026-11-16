import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By

brain_dir = r"C:\Users\Lenovo\.gemini\antigravity-ide\brain\7bc1c6fd-8c3d-44cd-92a0-194ebf0c23ac"

def capture():
    print("Launching Chrome for F5 Auth screenshots...")
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

        # 1. Capture Header & Main
        driver.save_screenshot(os.path.join(brain_dir, "f5_auth_header.png"))
        print("Saved f5_auth_header.png")

        # 2. Open Auth Modal
        print("Opening Sign In Modal...")
        driver.execute_script("openAuthModal('login');")
        time.sleep(1)
        driver.save_screenshot(os.path.join(brain_dir, "f5_auth_modal_login.png"))
        print("Saved f5_auth_modal_login.png")

        # 3. Switch to Register Tab
        print("Switching to Create Account tab...")
        driver.execute_script("setAuthMode('register');")
        time.sleep(1)
        driver.save_screenshot(os.path.join(brain_dir, "f5_auth_modal_register.png"))
        print("Saved f5_auth_modal_register.png")

    finally:
        driver.quit()
        print("Done capturing F5 Auth views!")

if __name__ == "__main__":
    capture()
