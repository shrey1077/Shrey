#!/usr/bin/env python3
"""PreToolUse hook: stop personal financial data from reaching this public repository.

Blocks a Bash command (exit code 2) when it would:
- force-add anything under finance/private/, or
- commit files under finance/private/, or added lines that look like a PAN or Aadhaar number.
"""

import json
import re
import shlex
import subprocess
import sys

PRIVATE_DIR = "finance/private/"
ALLOWED_PRIVATE = {"finance/private/README.md"}
PAN = re.compile(r"\b[A-Z]{3}[PCHFATBLJG][A-Z][0-9]{4}[A-Z]\b")
AADHAAR = re.compile(r"\b[2-9][0-9]{3}[ -]?[0-9]{4}[ -]?[0-9]{4}\b")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout


def git_invocations(command: str):
    """Yield the argument list after `git` for each git call in a shell command."""
    for segment in re.split(r"&&|\|\||;|\|", command):
        try:
            words = shlex.split(segment)
        except ValueError:
            words = segment.split()
        if "git" in words:
            yield words[words.index("git") + 1:]


def problems_in_diff(diff: str) -> list[str]:
    found, current = [], None
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            if PAN.search(line):
                found.append(f"{current}: looks like a PAN")
            if AADHAAR.search(line):
                found.append(f"{current}: looks like an Aadhaar number")
    return found


def check(command: str) -> list[str]:
    problems = []
    for args in git_invocations(command):
        while args and args[0].startswith("-"):  # global options such as -C <dir>
            args = args[2:] if args[0] in ("-C", "-c") else args[1:]
        if not args:
            continue
        sub, rest = args[0], args[1:]
        if sub == "add" and ({"-f", "--force"} & set(rest)) and any(PRIVATE_DIR.rstrip("/") in a for a in rest):
            problems.append("force-adding finance/private/ (personal data stays out of git)")
        if sub == "commit":
            staged = set(git("diff", "--cached", "--name-only").split())
            diff = git("diff", "--cached")
            if any(a == "--all" or re.fullmatch(r"-[a-zA-Z]*a[a-zA-Z]*", a) for a in rest):
                staged |= set(git("diff", "--name-only").split())
                diff += git("diff")
            private = sorted(p for p in staged if p.startswith(PRIVATE_DIR) and p not in ALLOWED_PRIVATE)
            problems += [f"{p}: personal data folder" for p in private]
            problems += problems_in_diff(diff)
    return problems


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    problems = check(payload.get("tool_input", {}).get("command", ""))
    if not problems:
        return 0
    print(
        "Blocked: this repository is public and the change would publish personal financial data:\n- "
        + "\n- ".join(dict.fromkeys(problems))
        + "\nUnstage or mask it (e.g. XXXXX1234X). If this is a false positive, ask Shrey to commit it themselves.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
