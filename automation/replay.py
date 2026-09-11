import json
import argparse
import os
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from artifact import Artifact, ReplayResult
from handoff_state import write_handoff_state



LOCATOR_MAP = {
    "id": By.ID,
    "name": By.NAME,
    "css": By.CSS_SELECTOR,
    "xpath": By.XPATH,
}

MAX_RETRIES = 2

# Safety Allowlist
ALLOWED_HOSTS = {
    "127.0.0.1:8000"
}

ALLOWED_ACTIONS = {
    "navigate",
    "fill",
    "click",
    "extract"
}


def log_event(log_path, event):
    event["timestamp"] = datetime.now(timezone.utc).isoformat()

    with open(log_path, "a") as f:
        f.write(json.dumps(event) + "\n")


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

    validate_step_safety(step)

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
    inputs,
    log_path,
    run_id
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

            print(
                f"Step '{step.id}' failed after "
                f"{MAX_RETRIES + 1} attempts."
            )

            # human handoff first
            resolved = request_human_handoff(
                driver,
                step,
                log_path,
                run_id
            )

            if resolved:
                return None

            return ReplayResult(
                status="recoverable_error",
                message=(
                    f"Step '{step.id}' could not be completed "
                    "after retries and human handoff."
                ),
                outputs={}
            )


def load_artifact(path):
    with open(path, "r") as f:
        data = json.load(f)

    return Artifact.model_validate(data)


def run_replay(artifact_path, inputs):

    run_id = str(uuid.uuid4())

    os.makedirs("evidence", exist_ok=True)
    os.makedirs("evidence/failures", exist_ok=True)
    log_path = "evidence/replay_log.jsonl"

    log_event(log_path, {
        "run_id": run_id,
        "event": "run_start",
        "artifact": artifact_path,
        "inputs": {
                key: "[REDACTED]"
                for key in inputs
            }
    })

    artifact = load_artifact(artifact_path)

    driver = webdriver.Chrome()
    wait = WebDriverWait(driver, 10)

    outputs = {}

    try:
        for step in artifact.steps:
            log_event(log_path, {
                "run_id": run_id,
                "event": "step_start",
                "step_id": step.id,
                "action": step.action
            })
            
            result = execute_step_with_retry(
                driver,
                wait,
                step,
                inputs,
                log_path,
                run_id
            )

            if isinstance(result, ReplayResult):

                screenshot_path = (
                    f"evidence/failures/"
                    f"{run_id}_{step.id}.png"
                )
                driver.save_screenshot(screenshot_path)

                log_event(log_path, {
                    "run_id": run_id,
                    "event": "step_failed",
                    "step_id": step.id,
                    "status": result.status,
                    "message": result.message,
                    "current_url": driver.current_url,
                    "screenshot": screenshot_path
                })
                
                print(result.model_dump())
                return result

            log_event(log_path, {
                "run_id": run_id,
                "event": "step_success",
                "step_id": step.id
            })

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

        log_event(log_path, {
            "run_id": run_id,
            "event": "run_complete",
            "status": result.status,
            "outputs": result.outputs
        })

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


def validate_step_safety(step):
    if step.action not in ALLOWED_ACTIONS:
        raise ValueError(
            f"Action '{step.action}' is not allowed."
        )

    if step.action == "navigate":
        parsed_url = urlparse(step.value)

        if parsed_url.netloc not in ALLOWED_HOSTS:
            raise ValueError(
                f"Navigation to '{parsed_url.netloc}' is not allowed."
            )


def request_human_handoff(driver, step, log_path, run_id):
    reason = (
        "Automation could not complete "
        "this step after retries."
    )

    write_handoff_state(
        step_id=step.id,
        reason=reason,
        current_url=driver.current_url
    )

    log_event(log_path, {
        "run_id": run_id,
        "event": "human_handoff_started",
        "step_id": step.id,
        "reason": reason,
        "current_url": driver.current_url
    })

    print("\n" + "=" * 50)
    print("AUTOMATION PAUSED")
    print(f"Current step: {step.id}")
    print(f"Reason: {reason}")
    print()
    print("Open the Operator Console:")
    print("http://127.0.0.1:8000/operator/")
    print()
    print("Complete this step manually in the browser.")
    print("Then return here and press ENTER.")
    print("=" * 50)

    response = input(
        "Was the step completed successfully? (y/n): "
        ).strip().lower()

    if response == "y":
        log_event(log_path, {
            "run_id": run_id,
            "event": "human_handoff_completed",
            "step_id": step.id
        })

        print("Human handoff complete. Resuming automation...\n")
        return True

    log_event(log_path, {
        "run_id": run_id,
        "event": "human_handoff_failed",
        "step_id": step.id
    })

    return False


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