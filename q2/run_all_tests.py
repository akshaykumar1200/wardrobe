import sys
import subprocess
from pathlib import Path

def main():
    q2_dir = Path(__file__).resolve().parent
    wardrobe_dir = q2_dir.parent / "wardrobe"
    pytest_bin = wardrobe_dir / "venv" / "Scripts" / "pytest.exe"

    if not pytest_bin.exists():
        print(f"Error: pytest binary not found at {pytest_bin}")
        sys.exit(1)

    print("=" * 70)
    print("  DIGITAL WARDROBE FULL-STACK TEST SUITE (Q2)")
    print("=" * 70)
    print(f"Running test modules in: {q2_dir}\n")

    cmd = [
        str(pytest_bin),
        "-v",
        str(q2_dir / "test_auth.py"),
        str(q2_dir / "test_idor_security.py"),
        str(q2_dir / "test_items_crud.py"),
        str(q2_dir / "test_storage_exif.py"),
        str(q2_dir / "test_admin.py"),
        str(q2_dir / "test_ai_segmentation.py"),
    ]

    import os
    env = os.environ.copy()
    env["PYTHONPATH"] = str(wardrobe_dir)

    result = subprocess.run(cmd, env=env)
    print("\n" + "=" * 70)
    if result.returncode == 0:
        print("  ALL TEST CASES PASSED SUCCESSFULLY (100%)")
    else:
        print("  TEST SUITE COMPLETED WITH FAILURES")
    print("=" * 70)
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
