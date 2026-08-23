#!/usr/bin/env bash
set -euo pipefail

printf '=== DEV BREAKDOWN PROJECT CONTEXT ===\n'
printf 'CWD=%s\n' "$(pwd)"

if ! command -v git >/dev/null 2>&1; then
  printf 'ERROR=git-not-found\n'
  exit 1
fi

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$repo_root" ]; then
  printf 'ERROR=not-in-git-repository\n'
  exit 1
fi

printf 'REPO_ROOT=%s\n' "$repo_root"
printf 'BRANCH=%s\n' "$(git -C "$repo_root" branch --show-current 2>/dev/null || true)"

printf '\n=== PROJECT METADATA ===\n'
if [ -f "$repo_root/.hermes/project.yaml" ]; then
  cat "$repo_root/.hermes/project.yaml"
else
  printf '(missing) %s\n' "$repo_root/.hermes/project.yaml"
fi

printf '\n=== GIT STATUS ===\n'
git -C "$repo_root" status --short || true

printf '\n=== TOP LEVEL ===\n'
find "$repo_root" -mindepth 1 -maxdepth 1 \
  ! -name '.git' \
  ! -name '.gradle' \
  ! -name 'build' \
  ! -name 'node_modules' \
  -printf '%f\n' 2>/dev/null | sort | head -n 100

printf '\n=== BUILD FILES ===\n'
for f in \
  build.gradle build.gradle.kts settings.gradle settings.gradle.kts \
  pom.xml gradlew mvnw package.json pnpm-lock.yaml yarn.lock package-lock.json \
  pyproject.toml requirements.txt go.mod Cargo.toml Makefile
do
  if [ -f "$repo_root/$f" ]; then
    printf '%s\n' "$f"
  fi
done

printf '\n=== TEST DIRECTORIES ===\n'
find "$repo_root" -maxdepth 4 -type d \
  \( -name test -o -name tests -o -name __tests__ -o -name integrationTest \) \
  2>/dev/null | sed "s#^$repo_root/##" | head -n 100 || true

printf '\n=== RECENT COMMITS ===\n'
git -C "$repo_root" --no-pager log --oneline --decorate -n 12 || true

printf '\n=== END CONTEXT ===\n'
