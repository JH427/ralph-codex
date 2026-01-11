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
TEST_COMMAND = [sys.executable, "verify.py"]
MISSING = object()

# ---------------- Git helpers ---------------- #

def git(cmd):
    return subprocess.run(
        ["git"] + cmd,
        cwd=ROOT,
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
    git(["clean", "-fd"])

def commit_story(story):
    git(["add", "."])
    return git(["commit", "-m", f"{story['id']}: {story['title']}"]).returncode == 0

# ---------------- Safety: append-only learnings ---------------- #

def hash_file(path):
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()

def validate_append_only(before_hash, before_text, before_exists):
    after_exists = LEARNINGS_FILE.exists()
    if before_exists and not after_exists:
        print("❌ learnings.md was deleted. Rolling back.")
        rollback()
        sys.exit(1)
    after_hash = hash_file(LEARNINGS_FILE)
    if before_hash and before_hash != after_hash:
        # allow change, but verify it's append-only
        after = LEARNINGS_FILE.read_text(errors="ignore")
        if not after.startswith(before_text):
            print("❌ learnings.md was modified non-append-only. Rolling back.")
            rollback()
            sys.exit(1)

# ---------------- Codex + tests ---------------- #

def run_codex(prompt):
    if sys.platform.startswith("win"):
        cmd = ["cmd.exe", "/c"] + CODEX_COMMAND
    else:
        cmd = CODEX_COMMAND
    proc = subprocess.Popen(
        cmd,
        cwd=ROOT,
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
    return subprocess.run(TEST_COMMAND, cwd=ROOT).returncode == 0

# ---------------- Ralph logic ---------------- #

def load_prd():
    return json.loads(PRD_FILE.read_text())

def build_prompt(prd, learnings):
    prd_text = json.dumps(prd, indent=2, ensure_ascii=True)
    return f"""
You are executing ONE atomic user story chosen from the PRD.

Rules:
- Read the PRD and pick ONE story where passes == false
- Prefer the lowest priority number; you may pick a different story if it unblocks progress
- Implement ONLY what is required for that one story
- Do NOT refactor unrelated code
- Do NOT touch other stories
- You MAY append factual notes to learnings.md
- You MUST NOT edit or delete existing learnings
- You MAY update prd.json ONLY by:
  - setting that story's passes from false to true
  - updating that story's notes
- Do NOT modify any other PRD fields or stories
- If complete, output exactly: DONE

--- PRD (READ-ONLY except allowed passes/notes for one story) ---
{prd_text}

--- EXISTING LEARNINGS (READ-ONLY) ---
{learnings}
"""

def validate_prd_changes(before_prd, after_prd):
    if before_prd.keys() != after_prd.keys():
        raise ValueError("prd.json top-level keys changed.")

    for key in before_prd:
        if key == "userStories":
            continue
        if before_prd[key] != after_prd[key]:
            raise ValueError(f"prd.json field changed: {key}")

    before_stories = before_prd.get("userStories", [])
    after_stories = after_prd.get("userStories", [])
    if len(before_stories) != len(after_stories):
        raise ValueError("prd.json userStories length changed.")

    changed_story = None

    for before_story, after_story in zip(before_stories, after_stories):
        if before_story.get("id") != after_story.get("id"):
            raise ValueError("prd.json userStories were reordered or IDs changed.")

        stripped_before = {k: v for k, v in before_story.items() if k not in ("passes", "notes")}
        stripped_after = {k: v for k, v in after_story.items() if k not in ("passes", "notes")}
        if stripped_before != stripped_after:
            raise ValueError(f"prd.json story fields changed for {before_story.get('id')}.")

        story_changed = False

        passes_before = before_story.get("passes", MISSING)
        passes_after = after_story.get("passes", MISSING)

        if passes_after is not MISSING and not isinstance(passes_after, bool):
            raise ValueError(f"prd.json passes is not boolean for {before_story.get('id')}.")

        if passes_before is MISSING and passes_after is MISSING:
            pass
        elif passes_before is MISSING and passes_after is True:
            story_changed = True
        elif passes_before is False and passes_after is True:
            story_changed = True
        elif passes_before == passes_after:
            pass
        else:
            raise ValueError(f"prd.json passes changed illegally for {before_story.get('id')}.")

        notes_before = before_story.get("notes", MISSING)
        notes_after = after_story.get("notes", MISSING)

        if notes_before is MISSING and notes_after is MISSING:
            pass
        elif notes_before is MISSING and notes_after is not MISSING:
            story_changed = True
        elif notes_before is not MISSING and notes_after is MISSING:
            raise ValueError(f"prd.json notes removed for {before_story.get('id')}.")
        elif notes_before != notes_after:
            story_changed = True

        if story_changed:
            if passes_before not in (False, MISSING):
                raise ValueError(f"Selected story must have passes == false for {before_story.get('id')}.")
            if changed_story is not None and changed_story.get("id") != after_story.get("id"):
                raise ValueError("Multiple stories modified in prd.json.")
            changed_story = after_story

    return changed_story

def run_story():
    print("\nStarting story selection")

    for attempt in range(1, MAX_ITERATIONS + 1):
        print(f"Attempt {attempt}/{MAX_ITERATIONS}")

        prd_before = load_prd()
        learnings_before_hash = hash_file(LEARNINGS_FILE)
        learnings_before_exists = LEARNINGS_FILE.exists()
        learnings_text = LEARNINGS_FILE.read_text(errors="ignore") if learnings_before_exists else ""

        output = run_codex(build_prompt(prd_before, learnings_text))

        validate_append_only(learnings_before_hash, learnings_text, learnings_before_exists)

        prd_after = load_prd()
        try:
            selected_story = validate_prd_changes(prd_before, prd_after)
        except ValueError as exc:
            print(f"Invalid prd.json modification: {exc}")
            rollback()
            sys.exit(1)

        done = any(line.strip() == "DONE" for line in output.splitlines())
        if not done:
            rollback()
            continue

        if run_tests():
            if selected_story is None:
                print("No PRD story was updated. Rolling back.")
                rollback()
                continue
            if selected_story.get("passes") is not True:
                print("Selected story not marked passes == true. Rolling back.")
                rollback()
                continue
            if commit_story(selected_story):
                return True
            rollback()
            return False

        rollback()

    return False

# ---------------- Main ---------------- #

def main():
    ensure_clean_repo()

    prd = load_prd()
    checkout_branch(prd["branchName"])

    while True:
        prd = load_prd()
        pending = [s for s in prd.get("userStories", []) if not s.get("passes", False)]
        if not pending:
            print("All stories passed.")
            break
        success = run_story()
        if not success:
            print("Halting Ralph: story failed.")
            break

if __name__ == "__main__":

    main()
