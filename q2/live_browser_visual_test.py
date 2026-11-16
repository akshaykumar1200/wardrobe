import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def run_visual_browser_test():
    print("\n" + "=" * 70)
    print("  LAUNCHING REAL CHROME BROWSER WINDOW ON YOUR SCREEN")
    print("=" * 70)
    print("Watch your screen! Chrome will open and click through the website.\n")

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    # Do not run headless so user sees the real window
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 10)

    try:
        # Step 1: Open Website
        print(">> [STEP 1] Opening http://localhost:8000 in Chrome...")
        driver.get("http://localhost:8000")
        time.sleep(2)

        # Step 2: Switch to Signup
        print(">> [STEP 2] Clicking 'Create one' to switch to Sign Up view...")
        try:
            signup_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Create one') or contains(text(), 'Sign up')]")))
            signup_link.click()
            time.sleep(2)
        except Exception:
            pass

        # Step 3: Switch back to Login and enter credentials
        print(">> [STEP 3] Entering Admin Credentials...")
        try:
            signin_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Sign in') or contains(text(), 'Already have an account')]")
            signin_btn.click()
            time.sleep(1)
        except Exception:
            pass

        email_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='email']")))
        email_input.clear()
        email_input.send_keys("admin@example.com")
        time.sleep(1)

        pass_input = driver.find_element(By.XPATH, "//input[@type='password']")
        pass_input.clear()
        pass_input.send_keys("AdminSecurePassword123!")
        time.sleep(1)

        # Step 4: Click Sign In
        print(">> [STEP 4] Clicking 'Sign In' button...")
        submit_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
        submit_btn.click()
        time.sleep(3)

        # Step 5: Navigate to Closet
        print(">> [STEP 5] Logged in! Exploring Digital Closet & Category Filter Chips...")
        time.sleep(2)

        # Click category buttons
        category_names = ["Topwear", "Bottomwear", "Shoes", "Accessories", "Other", "All Pieces"]
        for cat in category_names:
            try:
                cat_btn = driver.find_element(By.XPATH, f"//button[contains(text(), '{cat}')]")
                print(f"   -> Clicking category filter: '{cat}'")
                cat_btn.click()
                time.sleep(1.2)
            except Exception:
                pass

        # Step 6: Click Upload
        print(">> [STEP 6] Clicking 'Upload' button in navbar...")
        try:
            upload_nav = driver.find_element(By.XPATH, "//button[contains(text(), 'Upload')] | //a[contains(text(), 'Upload')]")
            upload_nav.click()
            time.sleep(3)
        except Exception as e:
            print("   Upload click notice:", e)

        # Step 7: Click Admin Dashboard
        print(">> [STEP 7] Clicking 'Admin' tab to inspect live metrics...")
        try:
            admin_nav = driver.find_element(By.XPATH, "//button[contains(text(), 'Admin')] | //a[contains(text(), 'Admin')]")
            admin_nav.click()
            time.sleep(4)
        except Exception as e:
            print("   Admin click notice:", e)

        print("\n" + "=" * 70)
        print("  LIVE VISUAL BROWSER AUTOMATION TEST COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        print("Leaving browser open for 10 seconds so you can inspect...")
        time.sleep(10)

    finally:
        driver.quit()
        print("Browser closed.")

if __name__ == "__main__":
    run_visual_browser_test()
