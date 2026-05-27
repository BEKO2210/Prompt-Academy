#!/usr/bin/env bash
# Auto-commit + push for prompt-forge.
# Runs from cron every 15 min. Idempotent: no-ops when nothing changed.

set -uo pipefail

REPO_DIR="/home/belkis/Schreibtisch/prompt-forge"
LOG="$REPO_DIR/.git/auto-push.log"
LOCK="$REPO_DIR/.git/auto-push.lock"

cd "$REPO_DIR" || { echo "[$(date -Is)] cd failed" >>"$LOG"; exit 1; }

# Single-instance guard (flock blocks concurrent runs from cron + manual).
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "[$(date -Is)] another run holds the lock; skipping" >>"$LOG"
  exit 0
fi

{
  echo "------ $(date -Is) ------"

  # Pull remote changes first so we never force-push.
  git pull --rebase --autostash origin main 2>&1 || {
    echo "rebase failed; aborting"; git rebase --abort 2>/dev/null; exit 1;
  }

  git add -A

  if git diff --cached --quiet; then
    echo "no changes — nothing to commit"
    exit 0
  fi

  # Build commit summary: count of prompts + categories covered (if jsonl exists)
  STATS=""
  if [ -s output/prompts.jsonl ]; then
    N=$(wc -l < output/prompts.jsonl)
    STATS=" [$N prompts]"
  fi

  git commit -m "auto: progress snapshot$STATS @ $(date -Is)" 2>&1
  git push origin main 2>&1
} >>"$LOG" 2>&1
