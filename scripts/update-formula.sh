#!/bin/sh
# Points the Homebrew formula in harsh-gulhane/homebrew-tap at agentmemdb <version> on PyPI, refreshes its
# Python resources, installs and tests it with brew, then pushes the change. Run by scripts/release.sh.
set -eu

version=${1:?usage: scripts/update-formula.sh <version>}
tap=harsh-gulhane/tap
formula=$tap/agentmemdb

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
git -C "$dir" pull -q --ff-only
file="$dir/Formula/agentmemdb.rb"
[ -f "$file" ] || fail "$file does not exist"
sed -i '' -e "s|^  url \".*\"|  url \"$url\"|" -e "s|^  sha256 \".*\"|  sha256 \"$sha\"|" "$file"

brew update-python-resources --ignore-main-package-cooldown "$formula"
brew audit --strict --online "$formula"
if brew list --formula agentmemdb >/dev/null 2>&1; then brew reinstall "$formula"; else brew install "$formula"; fi
brew test "$formula"

if git -C "$dir" diff --quiet; then
  echo "formula already at $version"
else
  git -C "$dir" commit -qam "agentmemdb $version"
  git -C "$dir" push -q
  echo "pushed agentmemdb $version to $tap"
fi
