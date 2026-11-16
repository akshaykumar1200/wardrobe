import time
import os
from selenium import webdriver

brain_dir = r"C:\Users\Lenovo\.gemini\antigravity-ide\brain\7bc1c6fd-8c3d-44cd-92a0-194ebf0c23ac"

def capture():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,1200")
    
    driver = webdriver.Chrome(options=options)
    try:
        driver.get("http://127.0.0.1:8000")
        time.sleep(2)
        driver.execute_script("localStorage.removeItem('ootd_auth_token');")
        driver.get("http://127.0.0.1:8000")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(1)
        driver.save_screenshot(os.path.join(brain_dir, "f5_logged_out_closet_locked.png"))
        print("Saved f5_logged_out_closet_locked.png")
    finally:
        driver.quit()

if __name__ == "__main__":
    capture()
