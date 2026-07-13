#!/bin/sh
echo "[cron] Scheduler started..."

while true; do
  # ✅ باگ ۷ رفع شد: استفاده از ساعت تهران (UTC+3:30) به جای UTC
  # کانتینر به UTC کار می‌کند؛ ساعت 23:00 تهران = 19:30 UTC
  now=$(TZ="Asia/Tehran" date '+%H:%M')
  dow=$(TZ="Asia/Tehran" date '+%u')   # روز هفته (1=دوشنبه، 6=شنبه، 7=یکشنبه)
  day=$(TZ="Asia/Tehran" date '+%d')   # روز ماه

  if [ "$now" = "23:00" ]; then
    echo "[$(date)] Running DAILY reset (Tehran time: $now)..."
    python /app/manage.py reset_checklists --frequency=DAILY
  fi

  # شنبه = روز ۶ در استاندارد ISO (1=دوشنبه ... 6=شنبه)
  if [ "$now" = "23:00" ] && [ "$dow" = "6" ]; then
    echo "[$(date)] Running WEEKLY reset (Tehran time: $now)..."
    python /app/manage.py reset_checklists --frequency=WEEKLY
  fi

  if [ "$now" = "23:00" ] && [ "$day" = "28" ]; then
    echo "[$(date)] Running MONTHLY reset (Tehran time: $now)..."
    python /app/manage.py reset_checklists --frequency=MONTHLY
  fi

  sleep 60
done