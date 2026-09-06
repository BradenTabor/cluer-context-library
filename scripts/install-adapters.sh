#!/usr/bin/env bash
# Symlink adapters/agent-skills/* into Cursor and Claude skill homes.
#
# Default is dry-run: print what would be linked, make no changes.
# Pass --apply to create links.
#
# Never replaces a real directory or a symlink that does not already point
# into this repository. ~/.cursor/skills/<name>/ may already hold the original
# extraction sources; clobbering them would destroy those originals.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${ROOT}/adapters/agent-skills"
CURSOR_HOME="${HOME}/.cursor/skills"
CLAUDE_HOME="${HOME}/.claude/skills"

APPLY=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) APPLY=0 ;;
    --apply) APPLY=1 ;;
    -h|--help)
      cat <<'EOF'
Usage: scripts/install-adapters.sh [--dry-run|--apply]

  --dry-run   print planned links, change nothing (default)
  --apply     create the symlinks

Refuses to replace a directory that is not already a symlink into this repo.
EOF
      exit 0
      ;;
    *)
      echo "unknown argument: $arg" >&2
      echo "Usage: scripts/install-adapters.sh [--dry-run|--apply]" >&2
      exit 2
      ;;
  esac
done

if [[ ! -d "$SRC" ]]; then
  echo "missing adapter directory: ${SRC}" >&2
  exit 1
fi

if [[ "$APPLY" -eq 1 ]]; then
  echo "install-adapters: apply"
else
  echo "install-adapters: dry-run (pass --apply to link)"
fi
echo "source: ${SRC}"

resolve() {
  python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$1"
}

failures=0
would=0
already=0

handle() {
  local dest_root="$1"
  local name="$2"
  local dest="${dest_root}/${name}"
  local target="${SRC}/${name}"

  echo "  ${dest}"
  echo "    -> ${target}"

  if [[ ! -d "$target" ]]; then
    echo "    error: adapter directory does not exist" >&2
    failures=$((failures + 1))
    return 0
  fi

  if [[ -L "$dest" ]]; then
    local current expected
    current="$(resolve "$dest")"
    expected="$(resolve "$target")"
    if [[ "$current" == "$expected" ]]; then
      echo "    already a symlink to this repo (ok)"
      already=$((already + 1))
      return 0
    fi
    echo "    exists as a symlink to:" >&2
    echo "      ${current}" >&2
    echo "    not this repo. Refusing." >&2
    failures=$((failures + 1))
    return 0
  fi

  if [[ -e "$dest" ]]; then
    echo "    exists and is not a symlink. Refusing to clobber." >&2
    echo "    found: $(ls -ld "$dest")" >&2
    failures=$((failures + 1))
    return 0
  fi

  if [[ "$APPLY" -eq 1 ]]; then
    mkdir -p "$dest_root"
    ln -s "$target" "$dest"
    echo "    linked"
  else
    echo "    would link"
  fi
  would=$((would + 1))
}

names=()
for d in "${SRC}"/*; do
  [[ -d "$d" ]] || continue
  names+=("$(basename "$d")")
done

if [[ ${#names[@]} -eq 0 ]]; then
  echo "no adapters found under ${SRC}" >&2
  exit 1
fi

echo
echo "Cursor (${CURSOR_HOME}):"
for n in "${names[@]}"; do
  handle "$CURSOR_HOME" "$n"
done

echo
echo "Claude (${CLAUDE_HOME}):"
for n in "${names[@]}"; do
  handle "$CLAUDE_HOME" "$n"
done

echo
echo "would-or-linked=${would} already-ok=${already} refused=${failures}"
if [[ "$failures" -gt 0 ]]; then
  exit 1
fi
