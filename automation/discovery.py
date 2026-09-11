from selenium.webdriver.common.by import By
from selenium import webdriver

from typing import Literal, Optional
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI
import uuid
import json
import os
from datetime import datetime, timezone

from artifact import (
    Artifact,
    InputParameter,
    OutputDefinition,
    Step,
    Locator,
    SuccessCondition
)


load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class AgentAction(BaseModel):
    action: Literal[
        "fill",
        "click",
        "done"
    ]

    target_id: Optional[str] = None
    value: Optional[str] = None
    reason: str


def log_event(log_path, event):
    event["timestamp"] = datetime.now(timezone.utc).isoformat()

    with open(log_path, "a") as f:
        f.write(json.dumps(event) + "\n")


def observe_page(driver):
    observation = {
        "url": driver.current_url,
        "title": driver.title,
        "text": driver.find_element(By.TAG_NAME, "body").text,
        "inputs": [],
        "buttons": [],
        "links": []
    }

    for element in driver.find_elements(By.TAG_NAME, "input"):
        observation["inputs"].append({
            "id": element.get_attribute("id"),
            "name": element.get_attribute("name"),
            "type": element.get_attribute("type"),
            "value": element.get_attribute("value"),
            "checked": element.is_selected()
        })

    for element in driver.find_elements(By.TAG_NAME, "button"):
        observation["buttons"].append({
            "id": element.get_attribute("id"),
            "text": element.text
        })

    for element in driver.find_elements(By.TAG_NAME, "a"):
        observation["links"].append({
            "id": element.get_attribute("id"),
            "text": element.text,
            "href": element.get_attribute("href")
        })

    return observation


def decide_next_action(goal, observation):

    system_prompt = """
        You are a browser automation agent.
        Choose exactly one next action that moves toward the user's goal.
        Only interact with elements visible in the provided observation.
        Use target_id from the observation.

        Rules:
        - Use "fill" only for text-like input fields.
        - Use "click" for buttons, links, radio buttons, and checkboxes.
        - Do not repeat an action if the observation shows it has already been completed.
        - For radio buttons and checkboxes, check the "checked" field before clicking.
        - Return "done" only when the goal has actually been achieved.
        """
    response = client.responses.parse(
        model="gpt-5-nano",
        input=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": (
                    f"Goal:\n{goal}\n\n"
                    f"Current page observation:\n"
                    f"{json.dumps(observation, indent=2)}"
                )
            }
        ],
        text_format=AgentAction
    )

    return response.output_parsed

def execute_agent_action(driver, action):
    if action.action == "fill":
        element = driver.find_element(
            By.ID,
            action.target_id
        )

        element.clear()
        element.send_keys(action.value)

    elif action.action == "click":
        element = driver.find_element(
            By.ID,
            action.target_id
        )

        element.click()

    elif action.action == "done":
        return


def build_artifact(discovered_steps):
    steps = []

    for index, discovered in enumerate(discovered_steps):
        action = discovered["action"]
        target_id = discovered["target_id"]
        value = discovered["value"]

        if action == "fill":
            if target_id == "member_id":
                value = "{{member_id}}"

            steps.append(
                Step(
                    id=f"step_{index + 1}",
                    action="fill",
                    locator=Locator(
                        strategy="id",
                        value=target_id
                    ),
                    value=value
                )
            )

        elif action == "click":
            steps.append(
                Step(
                    id=f"step_{index + 1}",
                    action="click",
                    locator=Locator(
                        strategy="id",
                        value=target_id
                    )
                )
            )

    artifact = Artifact(
        name="open_savings_sub_account",
        version="1.0",
        description="Open a savings sub-account for an existing member.",

        inputs=[
            InputParameter(
                name="member_id",
                type="string",
                required=True
            )
        ],

        steps=[
            Step(
                id="open_member_search",
                action="navigate",
                value="http://127.0.0.1:8000"
            )
        ] + steps,

        outputs=[
            OutputDefinition(
                name="confirmation_message",
                type="string",
                locator=Locator(
                    strategy="id",
                    value="success-message"
                )
            )
        ],

        success_condition=SuccessCondition(
            locator=Locator(
                strategy="id",
                value="success-message"
            ),
            contains_text="Account created successfully"
        )
    )

    return artifact


if __name__ == "__main__":

    run_id = str(uuid.uuid4())

    os.makedirs("evidence", exist_ok=True)
    log_path = "evidence/discovery_log.jsonl"

    driver = webdriver.Chrome()

    goal = """
    Open a savings sub-account for member 12345.
    """

    discovered_steps = []

    log_event(log_path, {
        "run_id": run_id,
        "event": "run_start",
        "goal": goal.strip()
    })

    try:
        driver.get("http://127.0.0.1:8000")
        MAX_STEPS = 10

        for step_number in range(MAX_STEPS):
            observation = observe_page(driver)

            action = decide_next_action(
                goal,
                observation
            )

            print(f"\nSTEP {step_number + 1}")
            print(action.model_dump())

            log_event(log_path, {
                "run_id": run_id,
                "event": "agent_decision",
                "step_number": step_number + 1,
                "action": action.action,
                "target_id": action.target_id,
                "value": action.value,
                "reason": action.reason
            })
            

            if action.action == "done":
                log_event(log_path, {
                    "run_id": run_id,
                    "event": "run_complete",
                    "status": "success",
                    "steps_discovered": len(discovered_steps)
                })
                
                print("\nDISCOVERY COMPLETE")
                break

            execute_agent_action(
                driver,
                action
            )

            log_event(log_path, {
                "run_id": run_id,
                "event": "action_executed",
                "step_number": step_number + 1,
                "action": action.action,
                "target_id": action.target_id
            })

            discovered_steps.append({
                "action": action.action,
                "target_id": action.target_id,
                "value": action.value
            })

        artifact = build_artifact(discovered_steps)
        print("\nGENERATED ARTIFACT:")
        print(
            artifact.model_dump_json(
                indent=2
            )
        )

        # Save generated artifact as JSON
        output_path = "artifacts/discovered_open_savings_account.json"
        with open(output_path, "w") as f:
            f.write(
                artifact.model_dump_json(
                    indent=2
                )
            )

        print(f"\nArtifact saved to: {output_path}")

    finally:
        input("Press Enter to close...")
        driver.quit()