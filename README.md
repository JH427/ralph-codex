# ralph-codex

`ralph-codex` is a **spec-driven execution controller** for AI coding agents (such as Codex).

It lets you run agents **safely and unattended** by enforcing:
- immutable product specs
- fresh context on every run
- git-backed rollback and isolation
- append-only learnings
- test-verified commits

This is not a chat loop.  
This is an **execution system**.

---

## Why ralph-codex exists

AI coding agents are good at:
- making local code changes
- following explicit instructions
- iterating quickly

They are bad at:
- long-term memory
- scope control
- knowing when they are wrong
- stopping safely

`ralph-codex` fixes this by **externalizing everything an LLM is bad at** and enforcing it in code.

---

## Core principles

### 1. Immutable spec (PRD is law)
The PRD defines truth.
It is **read-only** to the agent except for limited execution metadata:
- the selected story's `passes` may move from `false` to `true`
- the selected story's `notes` may be updated

All other PRD fields are immutable and controller-enforced.
If the spec is wrong, a human fixes it.

---

### 2. Fresh context every iteration
Each attempt runs in a **new Codex process**.
No chat history. No accumulated confusion.

This prevents:
- assumption drift
- prompt rot
- false confidence

---

### 3. Git is the safety harness
All agent changes:
- are isolated to a branch
- can be inspected
- can be rolled back instantly
- are only committed after tests pass

Without git, this system is unsafe.

---

### 4. Append-only learnings
The agent may **append factual observations** to a learnings file.
It may never edit or delete existing content.

This allows knowledge to accumulate **without corrupting context**.

---

### 5. Tests decide reality
The agent does not decide whether it succeeded.
The test suite does.

All acceptance criteria are validated by running the VERIFY command (`python verify.py`).

---

## Repository structure

```
repo/
├── prd.json # Immutable product spec & user stories
├── learnings.md # Append-only execution learnings
├── ralph.py # Execution controller
verify.py # Canonical verification command
├── src/ # Your application code
├── tests/ # Your test suite
└── .git/ # Ground truth
```


---

## `prd.json`

`prd.json` contains:
- project metadata
- execution branch name
- ordered atomic user stories
- acceptance criteria
- optional execution metadata: `passes` and `notes`

Example:

```json
{
  "project": "MyApp",
  "branchName": "ralph/task-priority",
  "userStories": [
    {
      "id": "US-001",
      "title": "Add priority field",
      "description": "Store task priority",
      "acceptanceCriteria": [
        "Migration runs",
        "Typecheck passes"
      ],
      "priority": 1
    }
  ]
}
```

Only one story may be updated per iteration, and only its `passes` and `notes`.

---

## Verification

Run `python verify.py` to validate all acceptance criteria.

Layers (fixed order):
1. Build/compile: Python syntax check via `python -m py_compile ralph.py`
2. Unit/integration tests: `python -m pytest`
3. Minimal E2E: not applicable for this controller-only repo

## Windows setup (Codex trust required)

On **Windows**, Codex may run in **read-only mode by default** until the working directory is explicitly trusted.

Before running `ralph.py` for the first time, do this **once per repository**:

```powershell
cd path\to\your\repo
codex --yolo
```
