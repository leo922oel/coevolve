#!/usr/bin/env bash
# A diagram is only as good as the renderer it lands in.
#
# GitHub and GitLab render mermaid with `htmlLabels` disabled, because HTML in a
# node label is an XSS vector. In that mode `<br/>` still becomes a line break
# and every other tag prints literally — so a diagram that looks correct in a
# local preview ships as `<b> ① SENSE </b>` on the site it was written for.
# That is not hypothetical: it is what the first version of the README did, and
# rendering it locally with the default config is what failed to catch it.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"

python3 - "$REPO" <<'PY' || exit 1
import pathlib, re, subprocess, sys

repo = pathlib.Path(sys.argv[1])
try:
    files = subprocess.run(["git", "-C", str(repo), "ls-files", "*.md"],
                           capture_output=True, text=True, check=True).stdout.split()
except Exception:
    files = [str(p.relative_to(repo)) for p in repo.rglob("*.md")
             if ".git" not in p.parts and "eval-runs" not in p.parts]

ALLOWED = {"<br/>"}
bad, blocks = [], 0
for rel in files:
    text = (repo / rel).read_text(encoding="utf-8", errors="replace")
    if text.count("```") % 2:
        bad.append(f"{rel}: unbalanced ``` fences")
    for block in re.findall(r"```mermaid\n(.*?)```", text, re.S):
        blocks += 1
        for tag in sorted(set(re.findall(r"<[^>\n]+>", block))):
            if tag not in ALLOWED:
                bad.append(f"{rel}: mermaid label contains {tag} — "
                           f"prints literally where htmlLabels is off")

if bad:
    print("FAIL: " + "\n       ".join(bad))
    sys.exit(1)
print(f"PASS {blocks} mermaid blocks use no label HTML beyond <br/>")
PY
echo "PASS"
