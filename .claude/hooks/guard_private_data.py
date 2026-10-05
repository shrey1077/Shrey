#!/usr/bin/env python3
"""PreToolUse hook: stop Shrey's personal data and secrets from reaching this public repository.

Blocks a Bash command (exit code 2) when it would:
- force-add anything under finance/private/ (the CA's files) or secretary/private/ (Donna's),
- commit files under those folders, credential files (.env, keys, OAuth client secrets), or the
  widget's local config and character art, or
- commit added lines that look like a PAN, an Aadhaar number, an API token or a private key.
"""

import json
import re
import shlex
import subprocess
import sys

PRIVATE_DIRS = ("finance/private/", "secretary/private/")
ALLOWED_PRIVATE = {d + "README.md" for d in PRIVATE_DIRS}
PAN = re.compile(r"\b[A-Z]{3}[PCHFATBLJG][A-Z][0-9]{4}[A-Z]\b")
AADHAAR = re.compile(r"\b[2-9][0-9]{3}[ -]?[0-9]{4}[ -]?[0-9]{4}\b")
SECRETS = [
    (re.compile(r"\bEAA[A-Za-z0-9]{30,}"), "a Meta (WhatsApp/Facebook/Instagram) access token"),
    (re.compile(r"\bAQ[A-Za-z0-9_-]{80,}"), "a LinkedIn access token"),
    (re.compile(r"\bA{20,}[A-Za-z0-9%]{30,}"), "an X (Twitter) bearer token"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), "a Google API key"),
    (re.compile(r"\bya29\.[0-9A-Za-z_-]{20,}"), "a Google OAuth token"),
    (re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})"), "a GitHub token"),
    (re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{32,}"), "an AI API key"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "an AWS access key"),
    (re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}"), "a Slack token"),
    (re.compile(r"\b\d{8,10}:AA[A-Za-z0-9_-]{33}\b"), "a Telegram bot token"),
    (re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"), "a private key"),
    (re.compile(r"""(?i)\b(?:api[_-]?key|secret|access[_-]?token|auth[_-]?token|password|passwd)\b["']?\s*[:=]\s*["'][^"'\s]{12,}["']"""),
     "a hard-coded secret"),
]
SECRET_FILES = re.compile(
    r"(^|/)(\.env(\..*)?|.*\.(pem|key|p12|pfx|keystore)|id_(rsa|ed25519|ecdsa)|"
    r"(client_secret|credentials|service[-_]account|token)[^/]*\.json)$"
)
SECRET_FILE_ALLOWED = {".env.example"}
WIDGET_PRIVATE = re.compile(r"^widget/(config\.json|assets/(?!README\.md$).+)$")


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
            for pattern, what in SECRETS:
                if pattern.search(line):
                    found.append(f"{current}: looks like {what}")
    return found


def check(command: str) -> list[str]:
    problems = []
    for args in git_invocations(command):
        while args and args[0].startswith("-"):  # global options such as -C <dir>
            args = args[2:] if args[0] in ("-C", "-c") else args[1:]
        if not args:
            continue
        sub, rest = args[0], args[1:]
        if sub == "add" and ({"-f", "--force"} & set(rest)):
            for d in PRIVATE_DIRS:
                if any(d.rstrip("/") in a for a in rest):
                    problems.append(f"force-adding {d} (personal data stays out of git)")
        if sub == "commit":
            staged = set(git("diff", "--cached", "--name-only").split())
            diff = git("diff", "--cached")
            if any(a == "--all" or re.fullmatch(r"-[a-zA-Z]*a[a-zA-Z]*", a) for a in rest):
                staged |= set(git("diff", "--name-only").split())
                diff += git("diff")
            private = sorted(p for p in staged if p.startswith(PRIVATE_DIRS) and p not in ALLOWED_PRIVATE)
            problems += [f"{p}: personal data folder" for p in private]
            problems += [f"{p}: credentials file" for p in sorted(staged)
                         if SECRET_FILES.search(p) and p.rsplit("/", 1)[-1] not in SECRET_FILE_ALLOWED]
            problems += [f"{p}: widget's local config or character art" for p in sorted(staged)
                         if WIDGET_PRIVATE.match(p)]
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
        "Blocked: this repository is public and the change would publish personal data or a secret:\n- "
        + "\n- ".join(dict.fromkeys(problems))
        + "\nUnstage or mask it (e.g. XXXXX1234X). A leaked token must be revoked, not just removed."
        + "\nIf this is a false positive, ask Shrey to commit it themselves.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
