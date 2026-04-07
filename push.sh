#!/usr/bin/env bash
# One-shot initializer: git init + commit + push to GitHub.
# Run from inside the bio-manim-lab folder:  bash push.sh
set -e

REMOTE="https://github.com/attaboy11/bio-manim-lab.git"

if [ ! -f ".gitignore" ]; then
  echo "Error: run this from the bio-manim-lab folder (no .gitignore found)."
  exit 1
fi

if [ -f ".env" ]; then
  if ! grep -q "^\.env$" .gitignore; then
    echo "Error: .env exists but is not in .gitignore — refusing to push."
    exit 1
  fi
fi

if [ ! -d ".git" ]; then
  git init -b main
fi

git add -A
# sanity: verify .env is not staged
if git ls-files --cached --error-unmatch .env >/dev/null 2>&1; then
  echo "Error: .env is staged. Aborting."
  exit 1
fi

if git diff --cached --quiet; then
  echo "Nothing to commit."
else
  git commit -m "Initial commit: bio-manim-lab + Vercel web wrapper"
fi

if ! git remote | grep -q "^origin$"; then
  git remote add origin "$REMOTE"
fi

git push -u origin main
echo ""
echo "✓ Pushed to $REMOTE"
