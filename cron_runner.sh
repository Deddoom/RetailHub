#!/bin/sh
echo "[cron] Scheduler started..."

while true; do
  now=$(date '+%H:%M')
  dow=$(date '+%u')
  day=$(date '+%d')

  if [ "$now" = "23:00" ]; then
    echo "[$(date)] Running DAILY reset..."
    python /app/manage.py reset_checklists --frequency=DAILY
  fi

  if [ "$now" = "23:00" ] && [ "$dow" = "6" ]; then
    echo "[$(date)] Running WEEKLY reset..."
    python /app/manage.py reset_checklists --frequency=WEEKLY
  fi

  if [ "$now" = "23:00" ] && [ "$day" = "28" ]; then
    echo "[$(date)] Running MONTHLY reset..."
    python /app/manage.py reset_checklists --frequency=MONTHLY
  fi

  sleep 60
done
