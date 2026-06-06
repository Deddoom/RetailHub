# استفاده از نسخه پایدار و سبک پایتون
FROM python:3.11-slim

# تنظیم متغیرهای محیطی برای پایتون (جلوگیری از تولید فایل‌های pyc و بافر شدن لاگ‌ها)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# تعیین پوشه کاری درون کانتینر
WORKDIR /app

# نصب ابزارهای مورد نیاز لینوکس برای کامپایل psycopg2 و دسترسی به شبکه
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    netcat-openbsd \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# کپی کردن فایل نیازمندی‌ها و نصب آن‌ها
# استفاده از میرور آروان برای دسترسی بدون محدودیت به PyPI
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip \
        --index-url https://mirror.arvancloud.ir/pypi/simple/ \
        --trusted-host mirror.arvancloud.ir && \
    pip install --no-cache-dir -r requirements.txt \
        --index-url https://mirror.arvancloud.ir/pypi/simple/ \
        --trusted-host mirror.arvancloud.ir

# کپی کردن کل کدهای پروژه به درون کانتینر
COPY . /app/

# جمع‌آوری فایل‌های استاتیک برای سرویس‌دهی توسط Nginx
RUN python manage.py collectstatic --noinput

# پورت پیش‌فرض برای وب‌سرور Gunicorn
EXPOSE 8000

# اجرای migration و سپس راه‌اندازی Gunicorn
CMD ["sh", "-c", "python manage.py migrate --run-syncdb --noinput && gunicorn project.wsgi:application --bind 0.0.0.0:8000 --workers 3"]