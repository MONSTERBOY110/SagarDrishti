"""Guard the team lead's typography rule: zero em (U+2014) and en (U+2013) dashes.

Why this is a checked-in tool and not a one-off cleanup: the rule was applied
once across 167 instances, and a rule applied once decays the moment anyone
writes another paragraph. Prose is added to this repo constantly, most of it by
an agent that has to be told the same thing every session. A guard in CI tells
it once.

Scope: every file git would consider part of the repository, tracked or not,
minus the exemptions below. Build output, site-packages and downloaded data are
excluded by .gitignore rather than by a skip-list here, which is what keeps this
honest with nothing to maintain.

NOT ONLY TRACKED FILES, and the difference is the whole point. This asked git
for `ls-files` alone until 2026-09-10, so a file that had been WRITTEN but not
yet committed was invisible to the guard. That is exactly backwards: new prose
is where a dash comes from, and on this project nothing is committed until the
team lead commits it, so at any moment a session's entire output sat outside
the check. It passed clean for a whole session over five new files it had never
opened.

    python tools/check_dashes.py            # check, exit 1 on any hit
    python tools/check_dashes.py --list     # one line per hit, no exit code
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

BAD = {0x2013: "en dash", 0x2014: "em dash"}

#: Files exempt, each with the reason. Not a convenience list: an exemption is a
#: statement that someone decided this file keeps its dashes.
#:
#: These nine came from the team lead's own initial commit (d3f6432) and are the
#: project's binding spec. Three of them (PRD, TRD, PRIOR-ART) may be shown to
#: judges, and SUBMISSION-GUIDE feeds the idea PDF. Rewriting the lead's own
#: authored documents on the agent's initiative is the same mistake ADR-0005
#: refuses: quietly editing a document we may put in front of judges is how a
#: team loses track of what it claimed. The lead has been told these files carry
#: 215 dashes and can say the word; until then they are exempt ON PURPOSE, and
#: this comment is the record of why rather than a silent hole in the guard.
EXEMPT: dict[str, str] = {
    "CLAUDE.md": "lead-authored, initial commit, binding rules file",
    "docs/PRD.md": "lead-authored, initial commit, judge-facing",
    "docs/TRD.md": "lead-authored, initial commit, judge-facing",
    "docs/PRIOR-ART.md": "lead-authored, initial commit, judge-facing",
    "docs/HANDOFF.md": "lead-authored, initial commit",
    "docs/ROADMAP.md": "lead-authored, initial commit",
    "docs/TEAM-ROLES.md": "lead-authored, initial commit",
    "docs/SUBMISSION-GUIDE.md": "lead-authored, initial commit, feeds the idea PDF",
    "docs/LAUNCH-PROMPT.md": "lead-authored, initial commit, verbatim record of the brief",
}

#: Binary and vendored extensions. A .nc or .parquet has no prose to police.
SKIP_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".mp4",
    ".nc", ".parquet", ".zip", ".woff", ".woff2", ".ttf", ".pyc",
}


def repo_files(root: pathlib.Path) -> list[str]:
    """Every file git considers part of the repo: committed AND newly written.

    `--cached` is the tracked set. `--others --exclude-standard` adds the
    untracked files that are not gitignored, which is where a brand new
    document lives right up until somebody commits it. `-z` because a path
    with a space in it would otherwise split into two paths that do not exist.
    """
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        capture_output=True, text=True, check=True,
    )
    # A set: a file can be listed by both --cached and --others in edge cases
    # (an assume-unchanged entry, say), and reporting one hit twice would make
    # the count wrong.
    return sorted({line for line in out.stdout.split("\0") if line})


def scan(root: pathlib.Path) -> list[tuple[str, int, str, str]]:
    hits: list[tuple[str, int, str, str]] = []
    for rel in repo_files(root):
        if rel in EXEMPT:
            continue
        path = root / rel
        if path.suffix.lower() in SKIP_EXT or not path.is_file():
            continue
        # Third-party prebuilt assets we serve but do not author.
        if "/cesium/" in f"/{rel}":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for index, char in enumerate(text):
            if ord(char) in BAD:
                line = text.count("\n", 0, index) + 1
                start = text.rfind("\n", 0, index) + 1
                end = text.find("\n", index)
                context = text[start: end if end != -1 else len(text)].strip()
                hits.append((rel, line, BAD[ord(char)], context[:120]))
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="report without failing")
    parser.add_argument("--root", default=None, help="repo root (default: this file's parent)")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    root = pathlib.Path(args.root) if args.root else pathlib.Path(__file__).resolve().parent.parent
    hits = scan(root)

    for rel, line, kind, context in hits:
        print(f"{rel}:{line}: {kind}: {context}")

    if not hits:
        print(
            f"clean: no em or en dash in {len(repo_files(root))} repo files, "
            f"committed and uncommitted ({len(EXEMPT)} exempt, see EXEMPT)"
        )
        return 0

    print(f"\n{len(hits)} em/en dash(es) found in {len({h[0] for h in hits})} file(s).")
    print("The team lead's rule is zero. Use a comma, a colon, brackets, or "
          "'to' for a range; a plain hyphen is fine.")
    return 0 if args.list else 1


if __name__ == "__main__":
    raise SystemExit(main())
