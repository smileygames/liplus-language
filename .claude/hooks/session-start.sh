#!/bin/bash
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# Install gh CLI to ~/.local/bin/gh if not already present
if [ -f "$HOME/.local/bin/gh" ]; then
  echo "gh CLI already installed: $("$HOME/.local/bin/gh" --version | head -1)"
  exit 0
fi

echo "Installing gh CLI to ~/.local/bin/ ..."

mkdir -p "$HOME/.local/bin"

# Detect architecture
ARCH=$(uname -m)
case "$ARCH" in
  x86_64)  GH_ARCH="amd64" ;;
  aarch64) GH_ARCH="arm64" ;;
  *)       echo "Unsupported architecture: $ARCH"; exit 1 ;;
esac

# Fetch latest release version
GH_VERSION=$(curl -fsSL https://api.github.com/repos/cli/cli/releases/latest \
  | grep '"tag_name"' | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | head -1)
GH_VERSION="${GH_VERSION:-v2.67.0}"

TARBALL_URL="https://github.com/cli/cli/releases/download/${GH_VERSION}/gh_${GH_VERSION#v}_linux_${GH_ARCH}.tar.gz"
WORK_DIR="$HOME/.local/gh-install-$$"
mkdir -p "$WORK_DIR"

curl -fsSL "$TARBALL_URL" -o "$WORK_DIR/gh.tar.gz"
tar -xzf "$WORK_DIR/gh.tar.gz" -C "$WORK_DIR" --strip-components=2 \
  "gh_${GH_VERSION#v}_linux_${GH_ARCH}/bin/gh"
mv "$WORK_DIR/gh" "$HOME/.local/bin/gh"
chmod +x "$HOME/.local/bin/gh"
rm -rf "$WORK_DIR"

echo "gh CLI installed: $("$HOME/.local/bin/gh" --version | head -1)"
