"""Check that the track record has only ever been appended to.

    python verify_track_record.py [--ref origin/track-record] [--new PATH]

Walks every commit on REF that touched the CSV, oldest first, and fails if any
version is not the previous version plus new rows at the end (an edited,
deleted or reordered row), or if data dates are not strictly increasing.
With --new, also checks that PATH (the file about to be committed) extends the
latest version on REF.

What this cannot catch: a force-push that rewrites the whole history
consistently. Branch protection on `track-record` (no force-push, no deletion)
is what prevents that; GitHub's Actions run history is an independent record
of when each run happened.
"""
import argparse
import subprocess
import sys

CSV = "backend/track_record/recommendations.csv"


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def lines_at(commit):
    return git("show", f"{commit}:{CSV}").splitlines()


def check_extends(old, new, label):
    if new[:len(old)] != old:
        sys.exit(f"FAIL: {label} does not extend the previous version (a past row was changed or removed).")


def check_dates(lines, label):
    dates = [ln.split(",", 1)[0] for ln in lines[1:]]
    if any(b <= a for a, b in zip(dates, dates[1:])):
        sys.exit(f"FAIL: {label} has data dates that are not strictly increasing.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="origin/track-record")
    ap.add_argument("--new", help="file about to be committed")
    args = ap.parse_args()

    commits = git("log", "--reverse", "--format=%H", args.ref, "--", CSV).split()
    prev = []
    for c in commits:
        cur = lines_at(c)
        check_extends(prev, cur, f"commit {c[:7]}")
        check_dates(cur, f"commit {c[:7]}")
        prev = cur
    if args.new:
        with open(args.new) as f:
            new = f.read().splitlines()
        check_extends(prev, new, args.new)
        check_dates(new, args.new)
    print(f"OK: {len(commits)} commit(s), {max(len(prev) - 1, 0)} row(s) on {args.ref}, append-only.")


if __name__ == "__main__":
    main()
