#!/bin/sh
# Durable backend launcher: respawns node if it ever exits, fully detached via nohup.
cd "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform/backend"
NODE="/Users/lucas.ma/.workbuddy-ai/binaries/node/versions/22.22.2/bin/node"
LOG="/Users/lucas.ma/Downloads/dp learning/ib-dp-platform/backend/backend.log"
while true; do
  echo "[$(date)] starting backend (PORT=3001)" >> "$LOG"
  PORT=3001 "$NODE" src/index.js >> "$LOG" 2>&1
  echo "[$(date)] backend exited (code $?), restarting in 2s" >> "$LOG"
  sleep 2
done
