from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


BASE_URL = "http://127.0.0.1:8000"


def run_demo():
    driver = webdriver.Chrome()
    wait = WebDriverWait(driver, 10)

    try:
        # Open the demo bank
        driver.get(BASE_URL)

        # Enter member ID
        member_input = wait.until(
            EC.presence_of_element_located(
                (By.ID, "member_id")
            )
        )

        member_input.send_keys("12345")

        # Click Search
        search_button = driver.find_element(
            By.CSS_SELECTOR,
            "button[type='submit']"
        )
        search_button.click()

        # Click Open Sub-account
        open_account_button = wait.until(
            EC.element_to_be_clickable(
                (By.ID, "open-account-button")
            )
        )
        open_account_button.click()

        # Select Savings
        savings_radio = wait.until(
            EC.element_to_be_clickable(
                (By.ID, "savings")
            )
        )
        savings_radio.click()

        # Click Continue
        continue_button = driver.find_element(
            By.ID,
            "continue-button"
        )
        continue_button.click()

        # Verify success
        success_message = wait.until(
            EC.presence_of_element_located(
                (By.ID, "success-message")
            )
        )

        assert "Account created successfully" in success_message.text

        print("SUCCESS: Savings sub-account flow completed.")

    finally:
        input("Press Enter to close the browser...")
        driver.quit()

def run_member_not_found():
    driver = webdriver.Chrome()
    wait = WebDriverWait(driver, 10)

    try:
        driver.get(BASE_URL)

        member_input = wait.until(
            EC.presence_of_element_located(
                (By.ID, "member_id")
            )
        )

        member_input.send_keys("99999")

        driver.find_element(
            By.ID,
            "search-button"
        ).click()

        not_found = wait.until(
            EC.presence_of_element_located(
                (By.ID, "member-not-found")
            )
        )

        assert "Member Not Found" in not_found.text

        print("BUSINESS OUTCOME: MEMBER_NOT_FOUND")

    finally:
        input("Press Enter to close the browser...")
        driver.quit()


if __name__ == "__main__":
    run_demo()
    #run_member_not_found()