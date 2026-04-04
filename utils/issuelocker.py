#!/usr/bin/env python
import json
import os
import subprocess

PROJECT_ROOT = os.path.expanduser("~/Projects/lutris")
OWNER = "lutris"
REPO = "lutris"

response = subprocess.check_output(
    [
        "gh",
        "issue",
        "list",
        "-L",
        "200",
        "--state",
        "closed",
        "--json",
        "number",
        "--search",
        "is:unlocked",
    ],
    cwd=PROJECT_ROOT,
)
issues = json.loads(response)
for issue in issues:
    issue_number = issue.get("number")
    if isinstance(issue_number, int):
        issue_number = str(issue_number)
    elif isinstance(issue_number, str) and issue_number.isdigit():
        pass
    else:
        continue
    print(f"Locking issue {issue_number}")
    subprocess.check_output(
        [
            "gh",
            "api",
            "--method",
            "PUT",
            f"/repos/{OWNER}/{REPO}/issues/{issue_number}/lock",
            "-f",
            "lock_reason=resolved",
        ]
    )
