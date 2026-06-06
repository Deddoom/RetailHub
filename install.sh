#!/bin/bash
# ================================================================
# اسکریپت نصب و راه‌اندازی RetailHub روی سرور Ubuntu
# اجرا: sudo bash install.sh
# ================================================================
set -e

echo "======================================"
echo " RetailHub - Server Setup Script"
echo "======================================"

# ۱. آپدیت سیستم
echo "[1/5] آپدیت سیستم..."
apt-get update -y && apt-get upgrade -y

# ۲. نصب Docker
echo "[2/5] نصب Docker..."
apt-get install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
| tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable docker
systemctl start docker

# ۳. تنظیم Firewall
echo "[3/5] تنظیم Firewall..."
apt-get install -y ufw
ufw allow 22/tcp    # SSH - حتماً باید باز باشد
ufw allow 80/tcp    # HTTP - پورت اصلی Nginx
ufw deny 8000/tcp   # Gunicorn - نباید مستقیم در دسترس باشد
ufw deny 5432/tcp   # PostgreSQL - نباید مستقیم در دسترس باشد
ufw --force enable
echo "وضعیت فایروال:"
ufw status

# ۴. کپی پروژه
echo "[4/5] آماده‌سازی پوشه پروژه..."
mkdir -p /opt/retailhub
echo "لطفاً فایل‌های پروژه را در /opt/retailhub کپی کنید."
echo "سپس دستور زیر را اجرا کنید:"
echo ""
echo "  cd /opt/retailhub"
echo "  docker compose up --build -d"
echo "  docker compose exec web python manage.py seed"
echo ""

echo "[5/5] نصب کامل شد!"
echo "Docker version: $(docker --version)"
echo "Docker Compose version: $(docker compose version)"
