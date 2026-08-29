#!/bin/bash
# Supervised, resumable figure uploader.
# Loops the pro uploader; breaks only when a run exits 0 (all uploaded, 0 failed).
# On any failure it waits and retries. Each run re-snapshots the store, so it is
# safe to kill and relaunch at any time.
cd "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform"
export UPLOAD_LOG=/tmp/upload_pro.log
NODE=/Users/lucas.ma/.workbuddy/binaries/node/versions/22.22.2/bin/node
CONC=${CONC:-200}
while true; do
  $NODE scripts/upload-figures-pro.mjs "$CONC"
  rc=$?
  echo "$(date +%H:%M:%S) run exited rc=$rc" >> /tmp/upload_supervisor.log
  if [ "$rc" -eq 0 ]; then
    echo "$(date +%H:%M:%S) ALL DONE" >> /tmp/upload_supervisor.log
    break
  fi
  sleep 8
done
