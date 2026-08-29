# استفاده از نسخه پایدار و سبک پایتون
FROM python:3.11-slim

# تنظیم متغیرهای محیطی برای پایتون
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# تعیین پوشه کاری درون کانتینر
WORKDIR /app

# کپی کردن ابزارهای مورد نیاز لینوکس بدون آپدیت مجدد (استفاده از کش محلی ایمیج)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    netcat-openbsd \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# کپی کردن نیازمندی‌ها و فایل‌های دانلود شده به داخل کانتینر
COPY requirements.txt /app/
COPY ./wheels /app/wheels

# نصب پکیج‌ها (استفاده از کش محلی wheels و دانلود پکیج‌های مکمل در صورت نیاز)
RUN pip install --no-cache-dir --find-links=/app/wheels -r requirements.txt

# کپی کردن کل کدهای پروژه به درون کانتینر
COPY . /app/

# جمع‌آوری فایل‌های استاتیک
RUN python manage.py collectstatic --noinput

# پورت پیش‌فرض برای وب‌سرور Gunicorn
EXPOSE 8000

# دستور استاندارد اعمال مایگریشن‌ها و اجرای gunicorn
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn project.wsgi:application --bind 0.0.0.0:8000 --workers 3"]