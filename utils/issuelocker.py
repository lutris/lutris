#!/usr/bin/env python
import json
import os
import subprocess

PROJECT_ROOT = os.path.expanduser("~/Projects/lutris")
OWNER="lutris"
REPO="lutris"

response = subprocess.check_output(
    "gh issue list -L 200 --state closed --json number --search 'is:unlocked'",
    shell=True,
    cwd=PROJECT_ROOT,
)
issues = json.loads(response)
for issue in issues:
    print(f"Locking issue {issue["number"]}")
    subprocess.check_output(
        f"gh api --method PUT /repos/{OWNER}/{REPO}/issues/{issue["number"]}/lock -f lock_reason='resolved'",
        shell=True,
    )
