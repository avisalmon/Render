"""The plain safety checks on a skill, without AI (REQ-G.52, first half).

These run first, cost nothing, and their findings go to the AI reader in the
skill chat (SPR-G.6) as hints, not verdicts: a skill about cleaning a disk may
say `rm -rf` and be honest, and a dangerous skill may say nothing these
patterns know. What they are good at is what a reader's eye misses: invisible
characters, text that turns itself around, and long encoded blobs.
"""

import re
from dataclasses import dataclass

HIGH, MEDIUM = "high", "medium"


@dataclass
class Finding:
    path: str
    line: int
    kind: str      # a key in gallery/strings.py, "scan.<kind>"
    severity: str
    excerpt: str

    def as_text(self):
        return f"{self.path}:{self.line} [{self.severity}] {self.kind}: {self.excerpt}"


# Characters nobody needs in a skill and attackers like: zero-width ones, the
# bidi overrides that make text read in a different order than it runs, and the
# "tag" block that hides whole instructions inside an invisible string.
INVISIBLE = re.compile("[​‌‍⁠﻿­]")
BIDI = re.compile("[‪-‮⁦-⁩]")
TAGS = re.compile("[\U000e0000-\U000e007f]")
BLOB = re.compile(r"[A-Za-z0-9+/]{200,}={0,2}|(?:[0-9a-fA-F]{2}){120,}")

PATTERNS = [
    # Destroying files
    ("wipe", HIGH, r"\brm\s+-[a-z]*r[a-z]*f?[a-z]*\s+(?:--no-preserve-root\s+)?(?:/|~|\$HOME|\*|\.\.?/?\s|/\*)"),
    ("wipe", HIGH, r"\b(?:del|erase)\s+/[sq].*?(?:[a-z]:\\|%userprofile%|\\\*)"),
    ("wipe", HIGH, r"\bRemove-Item\b[^\n]*-Recurse[^\n]*(?:[A-Za-z]:\\|\$env:USERPROFILE|\$HOME|~)"),
    ("wipe", HIGH, r"\b(?:format\s+[a-z]:|mkfs(?:\.\w+)?\s|dd\s+if=\S+\s+of=/dev/|diskpart|cipher\s+/w)"),
    ("wipe", HIGH, r"\bshutil\.rmtree\(\s*(?:['\"]/|['\"]~|os\.path\.expanduser|Path\.home)"),
    # Download and run
    ("download_run", HIGH, r"\b(?:curl|wget)\b[^\n|]*\|\s*(?:sudo\s+)?(?:ba|z)?sh\b"),
    ("download_run", HIGH, r"\b(?:iwr|irm|Invoke-WebRequest|Invoke-RestMethod)\b[^\n|]*\|\s*(?:iex|Invoke-Expression)\b"),
    ("download_run", HIGH, r"\b(?:iex|Invoke-Expression)\s*\(?\s*\(?\s*(?:New-Object\s+Net\.WebClient|iwr|irm)"),
    ("download_run", HIGH, r"\bpowershell(?:\.exe)?\b[^\n]*\s-(?:e|enc|encodedcommand)\s+[A-Za-z0-9+/=]{20,}"),
    ("download_run", HIGH, r"\bbase64\s+(?:-d|--decode)\b[^\n|]*\|\s*(?:ba|z)?sh\b"),
    ("download_run", MEDIUM, r"\b(?:eval|exec)\s*\(\s*(?:base64|codecs\.decode|bytes\.fromhex|requests\.get|urllib)"),
    # Secrets and private files
    ("secrets", HIGH, r"(?:~|\$HOME|%USERPROFILE%|\$env:USERPROFILE)[/\\]\.(?:ssh|aws|gnupg|kube|docker)\b"),
    ("secrets", HIGH, r"\bid_(?:rsa|ed25519|ecdsa)\b"),
    ("secrets", MEDIUM, r"(?:Login Data|Cookies|Local State)\b[^\n]*(?:Chrome|Edge|Firefox|Brave)|(?:Chrome|Edge|Firefox|Brave)[^\n]*(?:Login Data|Cookies)"),
    ("secrets", MEDIUM, r"\b(?:cat|type|Get-Content|read)\b[^\n]*\.env\b"),
    ("secrets", MEDIUM, r"\b(?:printenv|env\s*\||Get-ChildItem\s+env:|os\.environ\b(?!\.get\(\s*['\"][A-Z_]+['\"]\s*,))"),
    # Sending things out
    ("exfiltrate", HIGH, r"\b(?:curl|wget|iwr|Invoke-WebRequest|requests\.post|fetch)\b[^\n]*(?:-d\s*@|--data(?:-binary)?\s*@|-F\s*\S+=@|-InFile|files=)"),
    ("exfiltrate", MEDIUM, r"\b(?:webhook\.site|requestbin|pipedream\.net|ngrok\.io|ngrok-free\.app|burpcollaborator|interact\.sh|discord(?:app)?\.com/api/webhooks|api\.telegram\.org/bot)"),
    # Staying and spreading
    ("persist", HIGH, r"\b(?:crontab\s+-|schtasks\s+/create|HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run|HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run|launchctl\s+load|systemctl\s+enable)"),
    ("persist", MEDIUM, r"(?:>>?|Add-Content|Set-Content)[^\n]*(?:\.bashrc|\.zshrc|\.profile|Microsoft\.PowerShell_profile|authorized_keys)"),
    ("weaken", HIGH, r"\b(?:Set-MpPreference\s+-Disable|Add-MpPreference\s+-ExclusionPath|netsh\s+advfirewall\s+set\s+\w+\s+state\s+off|setenforce\s+0|chmod\s+-R\s+777\s+/|ufw\s+disable)"),
    ("weaken", MEDIUM, r"--dangerously-skip-permissions|--no-verify\b|git\s+push\s+--force\b[^\n]*\b(?:main|master)\b"),
    # Talking to the AI behind the reader's back
    ("hijack", HIGH, r"\b(?:ignore|disregard|forget)\s+(?:all\s+|any\s+)?(?:the\s+)?(?:previous|prior|above|earlier|your)\s+(?:instructions|rules|guidelines|system prompt)"),
    ("hijack", HIGH, r"\b(?:do not|don't|never)\s+(?:tell|mention|reveal|show|inform)\s+(?:the\s+)?(?:user|human|owner)\b"),
    ("hijack", MEDIUM, r"\b(?:without|don't|do not)\s+(?:asking|ask|confirm(?:ing)?|telling)\s+(?:the\s+)?(?:user|for (?:permission|confirmation))"),
    ("hijack", MEDIUM, r"<!--[^>]{0,400}?\b(?:instruction|assistant|claude|copilot|ai)\b[^>]{0,400}?-->"),
]
COMPILED = [(kind, sev, re.compile(rx, re.I)) for kind, sev, rx in PATTERNS]


def _excerpt(line, start=0, end=None):
    end = len(line) if end is None else end
    lo, hi = max(0, start - 40), min(len(line), end + 40)
    shown = line[lo:hi].strip()
    shown = shown.encode("unicode_escape").decode("ascii") if INVISIBLE.search(shown) or BIDI.search(shown) or TAGS.search(shown) else shown
    return shown[:160]


def scan_text(path, text):
    found = []
    for n, line in enumerate(text.splitlines(), start=1):
        for rx, kind in ((INVISIBLE, "invisible"), (BIDI, "bidi"), (TAGS, "tags")):
            m = rx.search(line)
            if m:
                found.append(Finding(path, n, kind, HIGH, _excerpt(line, m.start(), m.end())))
        m = BLOB.search(line)
        if m:
            found.append(Finding(path, n, "blob", MEDIUM, line[m.start():m.start() + 60] + "..."))
        for kind, sev, rx in COMPILED:
            m = rx.search(line)
            if m:
                found.append(Finding(path, n, kind, sev, _excerpt(line, m.start(), m.end())))
    return found


def scan(bundle):
    """Every file, every line. Returns a list of Findings, highest first."""
    found = []
    for path, data in bundle.files:
        found += scan_text(path, data.decode("utf-8"))
    return sorted(found, key=lambda f: (f.severity != HIGH, f.path, f.line))
