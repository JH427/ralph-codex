import subprocess
import sys


def run(cmd, cwd=None):
    print(f"> { ' '.join(cmd) }")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        sys.exit(result.returncode)


def main():
    # Layer 1: build/compile (Python syntax check).
    run([sys.executable, "-m", "py_compile", "ralph.py"])
    # Layer 2: unit/integration tests.
    run([sys.executable, "-m", "pytest"])
    # Layer 3: minimal E2E not applicable for this controller-only repo.
    print("VERIFY PASSED")


if __name__ == "__main__":
    main()
