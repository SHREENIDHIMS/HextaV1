#!/usr/bin/env bash
#
# Systemd socket activation starts hexa-backend.service on the
# first connection, but does NOT stop it again automatically. This
# script is run periodically (via hexa-backend-idle.timer) to
# check for active connections and stop the service if it's been
# idle for longer than IDLE_MINUTES.
#
# This, combined with socket activation, is what lets multiple
# projects share 1 GiB RAM: only the projects actually receiving
# traffic hold memory at any given moment.

set -euo pipefail

SERVICE="hexa-backend.service"
PORT=18001
IDLE_MINUTES=10
STATE_FILE="${IDLE_STATE_FILE:-/run/hexa-backend.last_active}"

if ! systemctl is-active --quiet "$SERVICE"; then
    exit 0   # already stopped, nothing to do
fi

# Count active inbound connections to the backend port right now.
# Only count connections whose source is the backend (sport=:PORT),
# so outbound traffic from the box is never mistaken for usage.
ACTIVE_CONNECTIONS=$(ss -tn state established "( sport = :$PORT )" | tail -n +2 | wc -l)

if [ "$ACTIVE_CONNECTIONS" -gt 0 ]; then
    # Traffic is flowing — record "now" as the last active time so the
    # idle window is measured from real usage, not service start (X5).
    touch "$STATE_FILE" 2>/dev/null || true
    exit 0
fi

# No active connections. Measure idle from the last recorded activity, not
# from when the service started (ActiveEnterTimestamp) — a service that
# started at t=0 and served a burst at t=9min must not be killed at t=10min.
if [ -f "$STATE_FILE" ]; then
    LAST_EPOCH=$(stat -c %Y "$STATE_FILE" 2>/dev/null || date -r "$STATE_FILE" +%s 2>/dev/null || echo 0)
else
    LAST_EPOCH=0
fi
NOW_EPOCH=$(date +%s)
IDLE_SECONDS=$(( NOW_EPOCH - LAST_EPOCH ))

if [ "$IDLE_SECONDS" -ge $(( IDLE_MINUTES * 60 )) ]; then
    logger -t idle_stop_watcher "Stopping $SERVICE after ${IDLE_MINUTES}m idle"
    systemctl stop "$SERVICE"
fi
