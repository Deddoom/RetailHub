# -*- coding: utf-8 -*-
"""
ماژول تبدیل و مدیریت تاریخ‌های شمسی (جلالی)
مبتنی بر کتابخانه استاندارد jdatetime
"""
import datetime
try:
    import jdatetime
except ImportError:
    jdatetime = None

SHAMSI_MONTH_NAMES = [
    '',
    'فروردین',
    'اردیبهشت',
    'خرداد',
    'تیر',
    'مرداد',
    'شهریور',
    'مهر',
    'آبان',
    'آذر',
    'دی',
    'بهمن',
    'اسفند'
]


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    """تبدیل تاریخ میلادی به شمسی"""
    if jdatetime:
        jd = jdatetime.date.fromgregorian(year=gy, month=gm, day=gd)
        return jd.year, jd.month, jd.day
    # Fallback if jdatetime is not present
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy if gm > 2 else gy - 1
    days = 355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1]
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd_day = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd_day = 1 + ((days - 186) % 30)
    return jy, jm, jd_day


def jalali_to_gregorian(jy: int, jm: int, jd: int) -> tuple[int, int, int]:
    """تبدیل تاریخ شمسی به میلادی"""
    if jdatetime:
        gd = jdatetime.date(jy, jm, jd).togregorian()
        return gd.year, gd.month, gd.day
    # Fallback
    jy_calc = jy + 1595
    days = -355668 + (365 * jy_calc) + ((jy_calc // 33) * 8) + (((jy_calc % 33) + 3) // 4) + jd
    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += ((jm - 7) * 30) + 186
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd_day = days + 1
    sal_a = [0, 31, 29 if ((gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    while gm < 13 and gd_day > sal_a[gm]:
        gd_day -= sal_a[gm]
        gm += 1
    return gy, gm, gd_day


def is_jalali_leap_year(jy: int) -> bool:
    """بررسی کبیسه بودن سال شمسی"""
    if jdatetime:
        return jdatetime.date(jy, 1, 1).isleap()
    r = (jy - (474 if jy > 0 else 473)) % 2820 % 33
    return r in [1, 5, 9, 13, 17, 22, 26, 30]


def get_days_in_shamsi_month(jy: int, jm: int) -> int:
    """تعداد روزهای یک ماه شمسی"""
    if 1 <= jm <= 6:
        return 31
    elif 7 <= jm <= 11:
        return 30
    elif jm == 12:
        return 30 if is_jalali_leap_year(jy) else 29
    raise ValueError(f"ماه نامعتبر است: {jm}")


def get_shamsi_month_name(jm: int) -> str:
    """دریافت نام فارسی ماه شمسی"""
    if 1 <= jm <= 12:
        return SHAMSI_MONTH_NAMES[jm]
    return f"ماه {jm}"


def get_current_shamsi() -> tuple[int, int, int]:
    """دریافت سال، ماه و روز شمسی امروز"""
    if jdatetime:
        today = jdatetime.date.today()
        return today.year, today.month, today.day
    today = datetime.date.today()
    return gregorian_to_jalali(today.year, today.month, today.day)


def format_jalali_date(jy: int, jm: int, jd: int) -> str:
    """فرمت‌دهی تاریخ شمسی به صورت YYYY/MM/DD"""
    return f"{jy:04d}/{jm:02d}/{jd:02d}"


def get_gregorian_date(jy: int, jm: int, jd: int) -> datetime.date:
    """تبدیل به آبجکت date استاندارد پایتون"""
    gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
    return datetime.date(gy, gm, gd)
