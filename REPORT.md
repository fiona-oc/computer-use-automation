# Computer-Use Automation System

## 1. Architecture

I implemented a two-phase computer-use automation system: **LLM-driven discovery** followed by **deterministic replay**.

During discovery, an LLM agent interacts with a live browser through an observe → decide → act loop. Selenium collects a structured observation of the current page, including the URL, visible text, inputs, buttons, links, and selected states. The LLM chooses one structured action at a time (`fill`, `click`, or `done`), and Selenium executes it.

After a successful discovery run, the recorded actions are converted into a typed, versioned Pydantic artifact. The artifact is independent of the LLM transcript and represents the reusable capability learned during discovery.

During replay, the artifact is loaded and validated, then executed directly with Selenium. The LLM is not called during replay.

The prototype uses a local Django "Demo Bank" application with the workflow:

`Search Member → Open Sub-account → Select Savings → Continue → Verify Confirmation`

The main architectural boundary is:

`Goal → LLM Discovery → Typed Artifact → Deterministic Replay`

Safety, observability, and human escalation surround the execution layer rather than being delegated to the LLM.

I chose Django because it provided a small, controllable target application, Selenium because it clearly separates browser execution from LLM reasoning, and Pydantic because artifacts generated from dynamic discovery should be validated before they are trusted or replayed.

---

## 2. Artifact schema

The artifact is a typed, serializable JSON contract defined using Pydantic.

It contains:

- `name`, `version`, and `description`
- typed runtime `inputs`
- ordered `steps`
- element `locator` definitions
- typed `outputs`
- a final `success_condition`

Each step has an explicit action such as `navigate`, `fill`, `click`, or `extract`. Element targets are represented separately through a `Locator` containing a strategy and value.

An important design decision is separating runtime parameters from values observed during discovery. For example, discovery may use member `12345`, but the generated artifact stores:

`{{member_id}}`

rather than permanently recording `12345`.

This allowed me to discover the workflow using one member and deterministically replay the same artifact using member `67890`.

The artifact is deliberately decoupled from the LLM transcript. LLM reasoning is useful during discovery but is not required to reproduce the workflow. This makes the artifact the contract between probabilistic discovery and deterministic execution.

The current implementation primarily uses stable element IDs because the target application is controlled. In a production system, I would extend `Locator` to support ranked fallback targets such as accessibility attributes, text anchors, relative DOM relationships, and application-specific selectors.

---

## 3. Determinism & error handling

Replay never asks an LLM what action to perform. It loads a previously generated artifact, substitutes runtime inputs, and executes the ordered steps directly.

The executor uses Selenium explicit waits rather than fixed sleeps and verifies an explicit success condition at the end of the workflow. It also extracts defined outputs, such as the account-creation confirmation message.

Runtime results are classified as:

- `success`
- `business_outcome`
- `recoverable_error`
- `hard_failure`

This distinction is intentional. For example, "Member Not Found" means the application worked correctly but produced a negative business result, so it is a `business_outcome`, not an automation failure.

If an expected UI element is temporarily unavailable, the executor retries the step a bounded number of times. If retries are exhausted, the condition becomes eligible for human escalation. If the operator cannot resolve it, the executor returns a `recoverable_error`.

Unexpected program-level exceptions are treated as `hard_failure`.

Each run and step is recorded in structured JSONL logs using a unique `run_id` and timestamps. Failures also capture the current URL and a browser screenshot, providing evidence for debugging without depending only on console output.

The current locator strategy handles a controlled application well but has limited UI-drift tolerance. Ranked fallback locators and post-action checkpoints would be the next improvements for replay robustness.

---

## 4. Heterogeneity & multi-tenant

The prototype executes against a modern web application through Selenium, but the recorded workflow is conceptually separate from the mechanism used to perceive and control the UI.

The artifact describes actions, targets, parameters, outputs, and checkpoints. A future execution backend could translate those targets into different surface-specific operations.

For a legacy web application, target resolution could use accessibility attributes, text anchors, DOM relationships, or visual fallback strategies when stable IDs are unavailable.

For desktop applications, the same workflow model could be extended with target types backed by accessibility APIs, window/control identifiers, screen regions, or visual anchors. The replay engine would delegate execution to a surface adapter rather than assuming every target is a Selenium DOM element.

For multi-tenant reuse, artifacts should represent the shared vendor workflow separately from institution-specific configuration. Runtime values, credentials, host configuration, and tenant-specific locator overrides should not require recording an entirely new workflow.

A production artifact could therefore have a shared base definition plus versioned tenant/application overrides. Replay telemetry and checkpoint failures could be used to detect drift. If a vendor release changes a locator for many tenants, the shared artifact could be updated; if only one tenant has customized its application, a scoped override could be applied.

I did not implement desktop or multi-tenant infrastructure in this prototype, but the separation between discovery, artifact representation, and replay provides a seam for adding these capabilities.

---

## 5. Escalation & handoff

The executor detects a stuck state when an automation step continues to fail after bounded retries.

At that point, execution pauses rather than immediately terminating the workflow. The system records the current step, reason, current browser URL, and handoff status. A minimal Django Operator Console displays this information to the human operator.

Most importantly, the Selenium browser remains open. The human therefore takes control of the **same live browser session**, rather than restarting the workflow in a separate browser.

I tested this by intentionally replacing the locator for the "Open Sub-account" button with an invalid locator. After the retries failed, the automation paused. I manually clicked "Open Sub-account" in the existing Chrome session and confirmed that the intervention was successful. Automation then resumed with the following artifact step and completed the Savings workflow.

Handoff events are also written to the structured replay log.

If the operator reports that the step could not be resolved, the workflow returns a `recoverable_error` instead of assuming that manual intervention succeeded.

The Operator Console is intentionally minimal. A production implementation would provide authenticated controls for resume, retry, abort, operator notes, and a durable queue of pending interventions.

---

## 6. Safety

Safety enforcement is kept outside of LLM reasoning wherever possible.

The replay engine uses an allowlist for permitted actions and navigation targets. A saved artifact therefore cannot arbitrarily navigate the browser to an unapproved external host simply because the artifact requests it.

The discovery agent also has a restricted action space. It can only issue supported structured actions rather than arbitrary browser or system commands.

Sensitive runtime values are redacted before being persisted to structured logs. For example, a member ID is replaced with `[REDACTED]`. I also redact occurrences inside LLM-generated reasoning text and the logged goal, because masking only the structured `value` field could still leak the same information through natural-language reasoning.

The prototype does not implement real financial transactions or irreversible operations. In production, I would classify actions by risk level and require stronger policies or explicit human approval before executing actions such as transfers, account closure, credential changes, or other irreversible operations.

The current safety model is therefore intentionally narrow: it demonstrates enforcement boundaries, allowlisting, and data redaction without claiming to provide a complete production authorization system.

---

## 7. Cuts

I deliberately optimized for a complete end-to-end vertical slice rather than production infrastructure.

I did not implement:

- desktop computer-use execution
- screenshot-based or multimodal target detection
- full multi-tenant storage and configuration
- distributed/asynchronous workers
- production authentication and authorization
- encrypted credential management
- sophisticated artifact migrations
- a full operator operations platform
- ranked/fallback locator resolution

The local Django application was intentional. It gave me a deterministic environment in which I could demonstrate the entire lifecycle:

`goal → LLM discovery → artifact generation → deterministic replay → error detection → human takeover → resume`

With more time, my first priorities would be stronger locator resolution and checkpoints, persistent execution state, richer operator controls, artifact version/migration support, and a surface-adapter abstraction for legacy web and desktop execution.

I would also add integration tests covering successful replay, expected business outcomes, injected UI failures, safety-policy rejection, and human handoff.

The goal of the prototype is not to simulate production scale, but to make the boundaries between probabilistic discovery, reusable capability representation, deterministic execution, safety enforcement, observability, and human control explicit and independently evolvable.