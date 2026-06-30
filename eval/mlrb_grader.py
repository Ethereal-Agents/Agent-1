import re
from eval.models import MLRBGradeResult


def parse_pytest_output(output: str) -> tuple[int, int, int]:
    """Parse pytest summary line to extract pass/fail counts.
    
    Example outputs:
    - "=========================== 5 passed in 0.12s ==========================="
    - "===================== 2 failed, 3 passed in 0.55s ====================="
    - "=========================== 5 failed in 0.12s ==========================="
    """
    passed = 0
    failed = 0
    
    # Try to find the summary line which usually starts and ends with ===
    # Look for "X passed" and "Y failed"
    passed_match = re.search(r"(\d+)\s+passed", output)
    if passed_match:
        passed = int(passed_match.group(1))
        
    failed_match = re.search(r"(\d+)\s+failed", output)
    if failed_match:
        failed = int(failed_match.group(1))
        
    # Also check for errors
    error_match = re.search(r"(\d+)\s+error", output)
    if error_match:
        failed += int(error_match.group(1))
        
    total = passed + failed
    return passed, failed, total

