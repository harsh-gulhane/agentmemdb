#!/bin/sh
# Points the Homebrew formula in harsh-gulhane/homebrew-tap at agentmemdb <version> on PyPI, refreshes its
# Python resources, installs and tests it with brew, then pushes the change. Creates the formula on the first
# release. Run by scripts/release.sh.
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
if [ ! -f "$file" ]; then
  mkdir -p "$dir/Formula"
  # Native dependencies come from Homebrew's bottles; update-python-resources adds the rest
  cat > "$file" <<'RUBY'
class Agentmemdb < Formula
  include Language::Python::Virtualenv

  desc "Local-first, shared long-term memory for AI agents over MCP"
  homepage "https://github.com/harsh-gulhane/agentmemdb"
  url "URL"
  sha256 "SHA256"
  license "MIT"

  depends_on "certifi" => :no_linkage
  depends_on "cryptography" => :no_linkage
  depends_on "pydantic" => :no_linkage
  depends_on "python@3.15"
  depends_on "rpds-py" => :no_linkage

  pypi_packages exclude_packages: %w[certifi cryptography pydantic rpds-py]

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/agentmemdb --version")

    ENV["AGENTMEMDB_DB_PATH"] = testpath/"memory.db"
    assert_match testpath.to_s, shell_output("#{bin}/agentmemdb --check")

    request = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18",' \
              '"capabilities":{},"clientInfo":{"name":"brew","version":"1"}}}'
    assert_match '"name":"agentmemdb"', pipe_output(bin/"agentmemdb", "#{request}\n", 0)
  end
end
RUBY
fi
# Maintainer commands like update-python-resources only load formulae from trusted taps
brew trust --quiet --formula "$formula"
sed -i '' -e "s|^  url \".*\"|  url \"$url\"|" -e "s|^  sha256 \".*\"|  sha256 \"$sha\"|" "$file"

brew update-python-resources --ignore-main-package-cooldown "$formula"
brew audit --strict --online "$formula"
if brew list --formula agentmemdb >/dev/null 2>&1; then brew reinstall "$formula"; else brew install "$formula"; fi
brew test "$formula"

if [ -z "$(git -C "$dir" status --porcelain Formula/agentmemdb.rb)" ]; then
  echo "formula already at $version"
else
  git -C "$dir" add Formula/agentmemdb.rb
  git -C "$dir" commit -qm "agentmemdb $version"
  git -C "$dir" push -q
  echo "pushed agentmemdb $version to $tap"
fi
