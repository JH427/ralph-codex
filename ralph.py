import subprocess
import json
import pathlib
import sys
import time
import hashlib

ROOT = pathlib.Path(__file__).parent
PRD_FILE = ROOT / "prd.json"
LEARNINGS_FILE = ROOT / "learnings.md"

MAX_ITERATIONS = 5

CODEX_COMMAND = ["codex.cmd", "exec"]  # adjust if needed
TEST_COMMAND = [sys.executable, "-m", "pytest"]

# ---------------- Git helpers ---------------- #

def git(cmd):
    return subprocess.run(
        ["git"] + cmd,
        capture_output=True,
        text=True
    )

def ensure_clean_repo():
    if git(["status", "--porcelain"]).stdout.strip():
        print("❌ Repo is dirty. Commit or stash changes before running Ralph.")
        sys.exit(1)

def checkout_branch(branch):
    exists = git(["branch", "--list", branch]).stdout.strip()
    if exists:
        git(["checkout", branch])
    else:
        git(["checkout", "-b", branch])

def rollback():
    git(["reset", "--hard", "HEAD"])

def commit_story(story):
    git(["add", "."])
    git(["commit", "-m", f"{story['id']}: {story['title']}"])

# ---------------- Safety: append-only learnings ---------------- #

def hash_file(path):
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()

def validate_append_only(before_hash):
    after_hash = hash_file(LEARNINGS_FILE)
    if before_hash and before_hash != after_hash:
        # allow change, but verify it's append-only
        before = LEARNINGS_FILE.read_text(errors="ignore")
        after = LEARNINGS_FILE.read_text(errors="ignore")
        if not after.startswith(before):
            print("❌ learnings.md was modified non-append-only. Rolling back.")
            rollback()
            sys.exit(1)

# ---------------- Codex + tests ---------------- #

def run_codex(prompt):
    proc = subprocess.Popen(
        CODEX_COMMAND,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    out, err = proc.communicate(prompt)
    print(out)
    if err:
        print("⚠️ Codex stderr:", err)
    return out

def run_tests():
    return subprocess.run(TEST_COMMAND).returncode == 0

# ---------------- Ralph logic ---------------- #

def build_prompt(story, learnings):
    criteria = "\n".join(f"- {c}" for c in story["acceptanceCriteria"])

    return f"""
You are executing ONE atomic user story.

Story ID: {story['id']}
Title: {story['title']}
Description:
{story['description']}

Acceptance Criteria:
{criteria}

Rules:
- Implement ONLY what is required
- Do NOT refactor unrelated code
- Do NOT touch other stories
- You MAY append factual notes to learnings.md
- You MUST NOT edit or delete existing learnings
- If complete, output exactly: DONE

--- EXISTING LEARNINGS (READ-ONLY) ---
{learnings}
"""

def run_story(story):
    print(f"\n🚀 {story['id']} — {story['title']}")

    for attempt in range(1, MAX_ITERATIONS + 1):
        print(f"🔁 Attempt {attempt}/{MAX_ITERATIONS}")

        learnings_before = hash_file(LEARNINGS_FILE)
        learnings_text = LEARNINGS_FILE.read_text() if LEARNINGS_FILE.exists() else ""

        output = run_codex(build_prompt(story, learnings_text))

        validate_append_only(learnings_before)

        if "DONE" not in output:
            rollback()
            continue

        if run_tests():
            commit_story(story)
            return True

        rollback()

    return False

# ---------------- Main ---------------- #

def main():
    ensure_clean_repo()

    prd = json.loads(PRD_FILE.read_text())
    checkout_branch(prd["branchName"])

    stories = sorted(prd["userStories"], key=lambda s: s["priority"])

    for story in stories:
        success = run_story(story)
        if not success:
            print("🛑 Halting Ralph — story failed.")
            break

if __name__ == "__main__":
    main()
