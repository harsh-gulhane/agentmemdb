#!/bin/sh
# Publishes a release: tags v<version>, waits for the release workflow to upload it to PyPI and create
# the GitHub release, then updates the Homebrew formula. Uses your gh login.
#
#   1. Set __version__ in src/agentmemdb/__init__.py, move the Unreleased entries in CHANGELOG.md under
#      "## [<version>] - <date>", and merge that to main.
#   2. On an up-to-date main: scripts/release.sh <version>
set -eu

version=${1:?usage: scripts/release.sh <version>}
root=$(cd "$(dirname "$0")/.." && pwd)
repo=harsh-gulhane/agentmemdb
cd "$root"

fail() { echo "release: $*" >&2; exit 1; }
current=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' src/agentmemdb/__init__.py)
[ "$current" = "$version" ] || fail "__version__ is $current, not $version"
grep -q "^## \[$version\]" CHANGELOG.md || fail "CHANGELOG.md has no ## [$version] section"
[ "$(git rev-parse --abbrev-ref HEAD)" = main ] || fail "not on main"
if ! git diff --quiet || ! git diff --cached --quiet; then fail "commit your changes first"; fi
git fetch -q origin
[ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] || fail "local main differs from origin/main: merge the release changes, then git pull"
git rev-parse -q --verify "refs/tags/v$version" >/dev/null && fail "tag v$version already exists"

git tag -a "v$version" -m "agentmemdb $version"
git push origin "v$version"

echo "waiting for the release workflow…"
run=""
for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do
  run=$(gh run list -R "$repo" --workflow release --branch "v$version" --limit 1 --json databaseId --jq '.[0].databaseId // empty')
  [ -n "$run" ] && break
  sleep 5
done
[ -n "$run" ] || fail "the release workflow did not start"
gh run watch "$run" -R "$repo" --exit-status

"$root/scripts/update-formula.sh" "$version"
echo "released $version: https://github.com/$repo/releases/tag/v$version"
