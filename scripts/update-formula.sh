#!/bin/sh
# Points the Homebrew formula in harsh-gulhane/homebrew-tap at agentmemdb <version> on PyPI and refreshes its
# Python resources, then opens a pull request in the tap and merges it once the tap's formulae workflow has
# audited, installed and tested it on macOS and Linux. Run by scripts/release.sh. Uses your gh login.
set -eu

version=${1:?usage: scripts/update-formula.sh <version>}
tap=harsh-gulhane/tap
tap_repo=harsh-gulhane/homebrew-tap
formula=$tap/agentmemdb
branch=agentmemdb-$version

fail() { echo "update-formula: $*" >&2; exit 1; }

# PyPI can take a moment to list a new upload
sdist=""
for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do
  sdist=$(curl -fsS "https://pypi.org/pypi/agentmemdb/$version/json" 2>/dev/null | python3 -c '
import json, sys
url = next(u for u in json.load(sys.stdin)["urls"] if u["packagetype"] == "sdist")
print(url["url"], url["digests"]["sha256"])' 2>/dev/null) && break
  sleep 10
done
[ -n "$sdist" ] || fail "agentmemdb $version has no sdist on PyPI"
url=${sdist% *}
sha=${sdist#* }

brew tap "$tap" >/dev/null
dir=$(brew --repo "$tap")
file="$dir/Formula/agentmemdb.rb"
[ -z "$(git -C "$dir" status --porcelain)" ] || fail "$dir has uncommitted changes"
git -C "$dir" checkout -q main
git -C "$dir" pull -q --ff-only
[ -f "$file" ] || fail "$file does not exist"

# Maintainer commands like update-python-resources only load formulae from trusted taps
brew trust --quiet --formula "$formula"
sed -i '' -e "s|^  url \".*\"|  url \"$url\"|" -e "s|^  sha256 \".*\"|  sha256 \"$sha\"|" "$file"
brew update-python-resources --ignore-main-package-cooldown "$formula"
brew style "$formula"

if [ -z "$(git -C "$dir" status --porcelain Formula/agentmemdb.rb)" ]; then
  echo "formula already at $version"
  exit 0
fi

git -C "$dir" checkout -q -b "$branch"
git -C "$dir" commit -qam "agentmemdb $version"
git -C "$dir" push -q -u origin "$branch"
git -C "$dir" checkout -q main
gh pr create -R "$tap_repo" --base main --head "$branch" --title "agentmemdb $version" \
  --body "Updates agentmemdb to [$version](https://github.com/harsh-gulhane/agentmemdb/releases/tag/v$version)."

echo "waiting for the formulae workflow…"
checks=0
for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do
  checks=$(gh pr checks "$branch" -R "$tap_repo" --json name --jq length 2>/dev/null || echo 0)
  [ "$checks" -gt 0 ] && break
  sleep 5
done
[ "$checks" -gt 0 ] || fail "the formulae workflow did not start"
gh pr checks "$branch" -R "$tap_repo" --watch --fail-fast || fail "formula checks failed: $branch is left open"
gh pr merge "$branch" -R "$tap_repo" --squash --delete-branch

git -C "$dir" pull -q --ff-only
git -C "$dir" branch -q -D "$branch"
echo "agentmemdb $version is in $tap; upgrade with: brew upgrade agentmemdb"
