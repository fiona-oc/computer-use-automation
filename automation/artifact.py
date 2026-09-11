from typing import Literal, Optional
from pydantic import BaseModel
import json


class Locator(BaseModel):
    strategy: Literal["id", "name", "css", "xpath"]
    value: str


class InputParameter(BaseModel):
    name: str
    type: Literal["string", "integer", "boolean"]
    required: bool = True


class OutputDefinition(BaseModel):
    name: str
    type: Literal["string", "integer", "boolean"]
    locator: Locator


class Step(BaseModel):
    id: str
    action: Literal["navigate", "fill", "click", "extract"]
    locator: Optional[Locator] = None
    value: Optional[str] = None


class SuccessCondition(BaseModel):
    locator: Locator
    contains_text: Optional[str] = None


class Artifact(BaseModel):
    name: str
    version: str
    description: str

    inputs: list[InputParameter]
    steps: list[Step]
    outputs: list[OutputDefinition]

    success_condition: SuccessCondition


class ReplayResult(BaseModel):
    status: Literal[
        "success",
        "business_outcome",
        "recoverable_error",
        "hard_failure"
    ]

    message: str

    outputs: dict = {}


if __name__ == "__main__":
    with open("artifacts/open_savings_account.json", "r") as f:
        data = json.load(f)

    artifact = Artifact.model_validate(data)

    print("Artifact is valid!")
    print(artifact)