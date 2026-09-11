import json

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from artifact import Artifact, ReplayResult
import argparse


LOCATOR_MAP = {
    "id": By.ID,
    "name": By.NAME,
    "css": By.CSS_SELECTOR,
    "xpath": By.XPATH,
}

MAX_RETRIES = 2


def resolve_value(value, inputs):
    if value is None:
        return None

    if value.startswith("{{") and value.endswith("}}"):
        key = value[2:-2].strip()
        return str(inputs[key])

    return value


def get_element(driver, wait, locator):
    by = LOCATOR_MAP[locator.strategy]

    return wait.until(
        EC.presence_of_element_located(
            (by, locator.value)
        )
    )


def execute_step(driver, wait, step, inputs):
    print(f"Running step: {step.id}")

    if step.action == "navigate":
        url = resolve_value(step.value, inputs)
        driver.get(url)

    elif step.action == "fill":
        element = get_element(
            driver,
            wait,
            step.locator
        )

        value = resolve_value(
            step.value,
            inputs
        )

        element.clear()
        element.send_keys(value)

    elif step.action == "click":
        by = LOCATOR_MAP[step.locator.strategy]

        element = wait.until(
            EC.element_to_be_clickable(
                (by, step.locator.value)
            )
        )

        element.click()

    elif step.action == "extract":
        element = get_element(
            driver,
            wait,
            step.locator
        )

        return element.text

def check_business_outcome(driver):
    elements = driver.find_elements(
        By.ID,
        "member-not-found"
    )

    if elements:
        return ReplayResult(
            status="business_outcome",
            message="Member not found.",
            outputs={}
        )

    return None

def execute_step_with_retry(
    driver,
    wait,
    step,
    inputs
):
    for attempt in range(MAX_RETRIES + 1):
        try:
            return execute_step(
                driver,
                wait,
                step,
                inputs
            )

        except TimeoutException:
            business_result = check_business_outcome(
                driver
            )

            if business_result:
                return business_result

            if attempt < MAX_RETRIES:
                print(
                    f"Retrying step {step.id} "
                    f"(attempt {attempt + 2})"
                )
                continue

            return ReplayResult(
                status="recoverable_error",
                message=(
                    f"Step '{step.id}' timed out "
                    f"after {MAX_RETRIES + 1} attempts."
                ),
                outputs={}
            )


def load_artifact(path):
    with open(path, "r") as f:
        data = json.load(f)

    return Artifact.model_validate(data)


def run_replay(artifact_path, inputs):
    artifact = load_artifact(artifact_path)

    driver = webdriver.Chrome()
    wait = WebDriverWait(driver, 10)

    outputs = {}

    try:
        for step in artifact.steps:
            result = execute_step_with_retry(
                driver,
                wait,
                step,
                inputs
            )

            if isinstance(result, ReplayResult):
                print(result.model_dump())
                return result

            if step.action == "extract":
                outputs[step.id] = result

        condition = artifact.success_condition

        element = get_element(
            driver,
            wait,
            condition.locator
        )

        if condition.contains_text:
            assert (
                condition.contains_text
                in element.text
            )

        for output in artifact.outputs:
            element = get_element(
                driver,
                wait,
                output.locator
            )

            outputs[output.name] = element.text


        result = ReplayResult(
            status="success",
            message="Replay completed successfully.",
            outputs=outputs
        )

        print(result.model_dump())

        return result

    except Exception as e:
        result = ReplayResult(
            status="hard_failure",
            message=f"{type(e).__name__}: {str(e)}",
            outputs=outputs
        )

        print(result.model_dump())
        return result

    finally:
        input("Press Enter to close the browser...")
        driver.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--artifact",
        default="artifacts/open_savings_account.json"
    )

    parser.add_argument(
        "--member-id",
        required=True
    )

    args = parser.parse_args()

    run_replay(
        args.artifact,
        {
            "member_id": args.member_id
        }
    )