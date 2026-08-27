#!/usr/bin/env bash
set -euo pipefail

SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/hermes-java"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

make_repo() {
  local path="$1"
  mkdir -p "$path/.hermes" "$path/fake-jdk/bin"
  git init -b main "$path" >/dev/null 2>&1
  printf '#!/usr/bin/env sh\nexit 0\n' > "$path/fake-jdk/bin/java"
  chmod +x "$path/fake-jdk/bin/java"
  printf 'JAVA_HOME=%s\n' "$path/fake-jdk" > "$path/.hermes/toolchain.env"
  cat > "$path/gradlew" <<'WRAPPER'
#!/usr/bin/env sh
printf '%s\n' "$@" > "$HERMES_JAVA_CAPTURE"
WRAPPER
  cat > "$path/mvnw" <<'WRAPPER'
#!/usr/bin/env sh
printf '%s\n' "$@" > "$HERMES_JAVA_CAPTURE"
WRAPPER
  chmod +x "$path/gradlew" "$path/mvnw"
}

repo_a="$tmp/a/repo"
repo_b="$tmp/b/repo"
cache_root="$tmp/cache"
capture="$tmp/args.txt"
make_repo "$repo_a"
make_repo "$repo_b"

run_launcher() {
  local repo="$1"
  shift
  (
    cd "$repo"
    HERMES_GRADLE_PROJECT_CACHE_ROOT="$cache_root" \
    HERMES_JAVA_CAPTURE="$capture" \
      "$SCRIPT" "$@"
  )
}

run_launcher "$repo_a" ./gradlew test
mapfile -t args < "$capture"
[ "${args[0]}" = "--project-cache-dir" ]
[ "${args[2]}" = "test" ]
cache_a="${args[1]}"
[ -d "$cache_a" ]
case "$cache_a" in
  "$cache_root"/*) ;;
  *) echo "Gradle cache escaped configured root: $cache_a" >&2; exit 1 ;;
esac

run_launcher "$repo_a" ./gradlew test
mapfile -t args < "$capture"
[ "${args[1]}" = "$cache_a" ]

run_launcher "$repo_b" ./gradlew test
mapfile -t args < "$capture"
[ "${args[1]}" != "$cache_a" ]

custom_cache="$tmp/custom-cache"
run_launcher "$repo_a" ./gradlew --project-cache-dir "$custom_cache" test
mapfile -t args < "$capture"
[ "${#args[@]}" -eq 3 ]
[ "${args[0]}" = "--project-cache-dir" ]
[ "${args[1]}" = "$custom_cache" ]
[ "${args[2]}" = "test" ]

run_launcher "$repo_a" ./mvnw test
mapfile -t args < "$capture"
[ "${#args[@]}" -eq 1 ]
[ "${args[0]}" = "test" ]

printf 'hermes-java Gradle project-cache isolation tests passed\n'
