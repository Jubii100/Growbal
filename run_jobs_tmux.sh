#!/usr/bin/env bash
# -------------------------------------------------------------------------
# Launch TWO parallel crawl.py jobs in one tmux window, split into panes.
#
#   ./run_jobs_tmux.sh .env_A list_A.txt  .env_B list_B.txt
#
# Each *list_X.txt* is newline-separated: one service per line.
# -------------------------------------------------------------------------

set -euo pipefail

if [[ $# -ne 4 ]]; then
  echo "Usage: $0 <env_A> <services_A.txt> <env_B> <services_B.txt>"
  exit 1
fi

ENV1=$1
LIST1=$2
ENV2=$3
LIST2=$4

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

PY_FILE="crawl.py"
SESSION="crawl_session_$RANDOM"

# ── start session & pane 0 ────────────────────────────────────────────────
tmux new-session  -d -s "$SESSION" -n "crawl" \
  "set -a; source \"$ENV1\"; set +a; \
   python $PY_FILE \"$ENV1\" \"$LIST1\"; \
   echo '[pane-A finished]'; read"

# ── split into pane 1 (right side) ───────────────────────────────────────
tmux split-window -h -t "$SESSION:0" \
  "set -a; source \"$ENV2\"; set +a; \
   python $PY_FILE \"$ENV2\" \"$LIST2\"; \
   echo '[pane-B finished]'; read"

# ── tidy layout & attach ─────────────────────────────────────────────────
tmux select-layout -t "$SESSION:0" even-horizontal
tmux attach-session -t "$SESSION"

