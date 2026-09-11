# Computer-Use Automation System

A prototype computer-use automation system that discovers and replays workflows against a web UI.

The system is designed around two execution modes:

1. **Discovery** — an LLM-driven agent observes a UI, decides what action to take, and executes actions until the goal is reached.
2. **Replay** — a successful workflow is stored as a typed, versioned artifact and replayed deterministically without requiring LLM decisions.

> **Project Status:** Work in progress. Deterministic replay is implemented. LLM-driven discovery, observability, safety controls, and human-in-the-loop handoff are currently being added.

---

## Current Demo

The project includes a local Django banking application used as the target UI.

The current workflow is:

```text
Search Member
    ↓
Member Details
    ↓
Open Sub-account
    ↓
Select Savings
    ↓
Continue
    ↓
Confirmation
```

For example:

```text
Member ID: 12345
```

produces a successful account-opening workflow.

An invalid member such as:

```text
Member ID: 99999
```

produces a known business outcome:

```text
Member Not Found
```

This is treated differently from a technical automation failure.

---

## Architecture

The current deterministic replay architecture is:

```text
                 Runtime Inputs
                {"member_id": ...}
                        │
                        ▼
              Workflow Artifact
                    (JSON)
                        │
                        ▼
               Pydantic Validation
                        │
                        ▼
               Generic Replay Engine
                        │
                        ▼
                    Selenium
                        │
                        ▼
                  Django Web UI
                        │
                        ▼
             Success / Business Outcome
```

The workflow definition is intentionally separated from the execution engine.

The replay engine does not contain application-specific workflow decisions. Instead, it interprets actions defined in the saved artifact.

For example:

```json
{
  "id": "search_member",
  "action": "click",
  "locator": {
    "strategy": "id",
    "value": "search-button"
  }
}
```

is interpreted by the generic replay engine and executed through Selenium.

---

## Structured Workflow Artifact

A reusable workflow is stored as a typed, versioned JSON artifact.

Example:

```text
artifacts/open_savings_account.json
```

The artifact contains:

- Workflow name and version
- Typed input parameters
- Ordered actions
- Element locators
- Runtime parameter references
- Typed outputs
- Success conditions

Runtime values are parameterized instead of hard-coded.

For example:

```json
{
  "id": "enter_member_id",
  "action": "fill",
  "locator": {
    "strategy": "id",
    "value": "member_id"
  },
  "value": "{{member_id}}"
}
```

This allows the same workflow artifact to be reused with different members.

---

## Artifact Validation

Artifacts are validated with Pydantic before replay.

For example, supported actions are currently:

```text
navigate
fill
click
extract
```

An invalid action such as:

```json
{
  "action": "dance"
}
```

is rejected during schema validation rather than being passed to the browser automation layer.

This provides a validation boundary between generated workflow definitions and deterministic execution.

---

## Replay Outcomes

The replay system distinguishes between different execution outcomes.

### Success

The workflow reaches its expected success condition.

```text
status = success
```

### Business Outcome

The application returns a valid business result that prevents the requested workflow from continuing.

Example:

```text
Member Not Found
```

returns:

```text
status = business_outcome
```

This is not considered an automation failure.

### Recoverable Error

A temporary technical condition prevents a step from completing, such as an element timeout or slow page load.

The replay engine retries eligible operations before returning:

```text
status = recoverable_error
```

### Hard Failure

Unexpected or non-recoverable execution problems are classified separately:

```text
status = hard_failure
```

---

## Tech Stack

- Python
- Django
- Selenium
- Pydantic
- Bootstrap

---

## Project Structure

```text
computer-use-automation/
│
├── automation/
│   ├── artifact.py
│   ├── replay.py
│   └── selenium_demo.py
│
├── artifacts/
│   └── open_savings_account.json
│
├── bank/
│   ├── templates/
│   │   └── bank/
│   ├── urls.py
│   └── views.py
│
├── demo_bank/
│
├── evidence/
│
├── manage.py
├── requirements.txt
├── .gitignore
└── README.md
```

Additional discovery and evidence components will be added as the implementation progresses.

---

## Setup

### 1. Clone the Repository

```bash
git clone <https://github.com/fiona-oc/computer-use-automation.git>
cd computer-use-automation
```

### 2. Create a Virtual Environment

macOS/Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

Windows:

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Run the Demo Application

Start the Django development server:

```bash
python manage.py runserver
```

The demo application will be available at:

```text
http://127.0.0.1:8000
```

Keep this terminal running while executing the automation.

---

## Run Deterministic Replay

Open another terminal and activate the virtual environment:

```bash
source venv/bin/activate
```

Run the saved workflow:

```bash
python automation/replay.py --member-id 12345
```

The replay engine will:

```text
Load workflow artifact
        ↓
Validate artifact
        ↓
Resolve runtime parameters
        ↓
Execute Selenium actions
        ↓
Verify success condition
        ↓
Extract outputs
        ↓
Return structured ReplayResult
```

A successful run should produce output similar to:

```text
Running step: open_member_search
Running step: enter_member_id
Running step: search_member
Running step: open_sub_account
Running step: select_savings
Running step: continue

{
    'status': 'success',
    'message': 'Replay completed successfully.',
    'outputs': {
        'confirmation_message': 'Account created successfully'
    }
}
```

---

## Test Members

The demo application currently includes the following test members:

| Member ID | Expected Result |
|---|---|
| `12345` | Valid member |
| `67890` | Valid member |
| `99999` | Member Not Found |

For example:

```bash
python automation/replay.py --member-id 67890
```

should replay the same saved capability using a different runtime input.

To test the business-outcome path:

```bash
python automation/replay.py --member-id 99999
```

The system should classify the result as:

```text
business_outcome
```

rather than treating it as an unexpected automation failure.

---

## Design Principles

### Artifact / Runtime Separation

Workflow knowledge lives in the artifact rather than being hard-coded into the replay engine.

```text
Artifact
"What should be done?"

        ↓

Replay Engine
"How do I execute these instructions?"

        ↓

Selenium
"Perform the browser interaction."
```

### Parameterized Capabilities

Runtime values such as member IDs are supplied separately from the saved workflow:

```text
Artifact:
{{member_id}}

Runtime:
12345
```

This allows one discovered capability to be reused across multiple executions.

### Deterministic Replay

Once a workflow has been discovered and saved, replay follows the artifact directly.

The replay engine does not require an LLM to decide the next UI action.

### Explicit Outcome Classification

Business outcomes are separated from technical failures so that expected application behavior is not incorrectly reported as an automation failure.

---

## Roadmap

### Completed

- [x] Django target application
- [x] Selenium browser automation
- [x] Stable UI element identifiers
- [x] Typed workflow schema
- [x] Pydantic artifact validation
- [x] Versioned JSON workflow artifact
- [x] Parameterized runtime inputs
- [x] Generic deterministic replay engine
- [x] Success-condition verification
- [x] Typed replay results
- [x] Business-outcome handling
- [x] Basic retry/error classification

### In Progress

- [ ] LLM-driven workflow discovery
- [ ] Observe → decide → act agent loop
- [ ] Automatic artifact generation from successful discovery
- [ ] Structured execution logs
- [ ] Failure screenshots and evidence
- [ ] Domain/action allowlists
- [ ] Sensitive-data redaction
- [ ] Human-in-the-loop pause and resume
- [ ] Discovery and replay evidence
- [ ] Final project report

---

## Planned Discovery Architecture

The completed system will extend the current replay architecture with an LLM-driven discovery phase:

```text
                 User Goal
                    │
                    ▼
              Discovery Agent
                    │
          ┌─────────┴─────────┐
          │                   │
       Observe              Decide
          │                   │
          └─────────┬─────────┘
                    ▼
                   Act
                    │
                    ▼
                 Selenium
                    │
                    ▼
                  Web UI
                    │
                    ▼
              Goal Reached?
               │         │
              No        Yes
               │         │
               └── loop  ▼
                   Generate
                    Artifact
                       │
                       ▼
                Pydantic Validate
                       │
                       ▼
                Save Capability
                       │
                       ▼
             Deterministic Replay
```

The LLM is responsible for discovering a workflow.

Once the workflow has been successfully discovered and converted into a validated artifact, future executions use deterministic replay rather than asking the LLM to make the same decisions again.

---

## Evidence

Discovery and replay evidence will be stored under:

```text
evidence/
```

Planned evidence includes:

```text
evidence/
├── discovery_log.jsonl
├── replay_log.jsonl
├── discovery_screenshot.png
├── replay_screenshot.png
└── open_savings_account.json
```

This will make successful discovery and deterministic replay independently inspectable.

---

## Development Status

This repository is being developed as a focused vertical slice of a computer-use automation system.

The current implementation demonstrates the structured artifact and deterministic replay path. The next major component is LLM-driven discovery, followed by safety controls, observability, and human-in-the-loop recovery.