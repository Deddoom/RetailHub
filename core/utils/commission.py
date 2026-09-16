# -*- coding: utf-8 -*-
"""
موتور محاسباتی سیستم پورسانت و پاداش فروشندگان RetailHub
پشتیبانی از:
۱. مدل کف و درصد مازاد (Threshold & Surplus Percentage)
۲. مدل پلکانی از کف (Tiered Marginal Commission)
۳. سیستم پاداش تارگت‌ها (Bonus Milestones - بالاترین تارگت یا تجمعی)
"""
from decimal import Decimal


def calculate_threshold_surplus(total_sales: Decimal, threshold: Decimal, percentage: Decimal) -> tuple[Decimal, dict]:
    """
    محاسبه سیستم کف و درصد مازاد:
    اگر فروش <= کف باشد: پورسانت = ۰
    اگر فروش > کف باشد: پورسانت = (فروش - کف) * درصد
    """
    total = Decimal(str(total_sales or 0))
    thresh = Decimal(str(threshold or 0))
    pct = Decimal(str(percentage or 0))

    if total <= thresh:
        surplus = Decimal('0.00')
        commission = Decimal('0.00')
    else:
        surplus = total - thresh
        commission = (surplus * pct) / Decimal('100')

    breakdown = {
        "model": "THRESHOLD_SURPLUS",
        "total_sales": float(total),
        "threshold": float(thresh),
        "surplus": float(surplus),
        "percentage": float(pct),
        "formula": f"({total:,.0f} - {thresh:,.0f}) × {pct}% = {commission:,.0f}" if total > thresh else "فروش به کف تعیین‌شده نرسیده است."
    }
    return commission, breakdown


def calculate_tiered_marginal(total_sales: Decimal, tiers: list[dict]) -> tuple[Decimal, list[dict]]:
    """
    محاسبه سیستم پورسانت پلکانی از کف (مارجینال - استاندارد حسابداری):
    tiers: لیستی از دیکشنری‌های بازه:
    [
        {"from_amount": 0, "to_amount": 100000000, "percentage": 0.0},
        {"from_amount": 100000000, "to_amount": 200000000, "percentage": 0.5},
        {"from_amount": 200000000, "to_amount": 300000000, "percentage": 1.0},
        {"from_amount": 300000000, "to_amount": None, "percentage": 1.5}
    ]
    """
    total = Decimal(str(total_sales or 0))
    total_commission = Decimal('0.00')
    breakdown = []

    if not tiers:
        return Decimal('0.00'), []

    # مرتب‌سازی پلکان‌ها بر اساس حداقل بازه
    sorted_tiers = sorted(tiers, key=lambda x: Decimal(str(x.get('from_amount', 0))))

    for tier in sorted_tiers:
        t_from = Decimal(str(tier.get('from_amount', 0)))
        t_to_raw = tier.get('to_amount')
        t_to = Decimal(str(t_to_raw)) if t_to_raw is not None else None
        t_pct = Decimal(str(tier.get('percentage', 0)))

        t_to_label = f"{t_to:,.0f}" if t_to is not None else "نامحدود"
        tier_label = f"{t_from:,.0f} تا {t_to_label}"

        if total <= t_from:
            # فروش به شروع این پله نرسیده است
            breakdown.append({
                "tier": tier_label,
                "percentage": float(t_pct),
                "applicable_amount": 0.0,
                "commission": 0.0,
                "status": "نرسیده"
            })
            continue

        if t_to is not None:
            applicable_amount = min(total, t_to) - t_from
        else:
            applicable_amount = total - t_from

        tier_comm = (applicable_amount * t_pct) / Decimal('100')
        total_commission += tier_comm

        breakdown.append({
            "tier": tier_label,
            "percentage": float(t_pct),
            "applicable_amount": float(applicable_amount),
            "commission": float(tier_comm),
            "status": "اعمال‌شده"
        })

    return total_commission, breakdown


def calculate_reward(total_sales: Decimal, milestones: list[dict], mode: str = "HIGHEST_ONLY") -> tuple[Decimal, list[dict]]:
    """
    محاسبه سیستم پاداش:
    milestones: لیستی از تارگت‌ها:
    [
        {"target_amount": 200000000, "reward_amount": 2000000},
        {"target_amount": 300000000, "reward_amount": 4000000},
        {"target_amount": 400000000, "reward_amount": 8000000}
    ]
    mode: 'HIGHEST_ONLY' (فقط بالاترین تارگت فتح‌شده) یا 'CUMULATIVE' (تجمعی)
    """
    total = Decimal(str(total_sales or 0))
    if not milestones:
        return Decimal('0.00'), []

    sorted_ms = sorted(milestones, key=lambda x: Decimal(str(x.get('target_amount', 0))))
    achieved = []
    unachieved = []

    for m in sorted_ms:
        target = Decimal(str(m.get('target_amount', 0)))
        reward = Decimal(str(m.get('reward_amount', 0)))
        item = {
            "target_amount": float(target),
            "reward_amount": float(reward),
            "achieved": total >= target
        }
        if total >= target:
            achieved.append(item)
        else:
            unachieved.append(item)

    if not achieved:
        return Decimal('0.00'), achieved + unachieved

    if mode == "CUMULATIVE":
        total_reward = sum(Decimal(str(m['reward_amount'])) for m in achieved)
        for m in achieved:
            m['awarded'] = True
    else:  # HIGHEST_ONLY
        highest = achieved[-1]
        total_reward = Decimal(str(highest['reward_amount']))
        for m in achieved:
            m['awarded'] = (m == highest)

    for m in unachieved:
        m['awarded'] = False

    return total_reward, achieved + unachieved


def calculate_seller_commission(config, total_sales: Decimal) -> dict:
    """
    اجرای کامل محاسبه پورسانت و پاداش برای یک پیکربندی داده‌شده و جمع کل فروش
    """
    if not config or not getattr(config, 'is_active', True):
        return {
            "is_configured": False,
            "total_sales": float(total_sales),
            "commission_amount": 0.0,
            "reward_amount": 0.0,
            "total_earnings": 0.0,
            "breakdown": {"message": "پلن پورسانت برای این فروشنده فعال نیست."}
        }

    total_sales = Decimal(str(total_sales or 0))
    model_type = getattr(config, 'model_type', 'THRESHOLD_SURPLUS')

    if model_type == 'THRESHOLD_SURPLUS':
        thresh = getattr(config, 'threshold_amount', Decimal('0.00')) or Decimal('0.00')
        pct = getattr(config, 'surplus_percentage', Decimal('0.00')) or Decimal('0.00')
        commission, comm_breakdown = calculate_threshold_surplus(total_sales, thresh, pct)
    elif model_type == 'TIERED_FROM_BASE':
        tiers = getattr(config, 'tiers', []) or []
        commission, comm_breakdown = calculate_tiered_marginal(total_sales, tiers)
    else:
        commission = Decimal('0.00')
        comm_breakdown = {}

    reward_active = getattr(config, 'reward_active', False)
    reward_mode = getattr(config, 'reward_mode', 'HIGHEST_ONLY')
    reward_milestones = getattr(config, 'reward_milestones', []) or []

    if reward_active and reward_milestones:
        reward_amount, reward_breakdown = calculate_reward(total_sales, reward_milestones, reward_mode)
    else:
        reward_amount = Decimal('0.00')
        reward_breakdown = []

    total_earnings = commission + reward_amount

    return {
        "is_configured": True,
        "model_type": model_type,
        "model_display": "کف و درصد مازاد" if model_type == 'THRESHOLD_SURPLUS' else "پلکانی از کف",
        "total_sales": float(total_sales),
        "commission_amount": float(commission),
        "reward_active": reward_active,
        "reward_amount": float(reward_amount),
        "total_earnings": float(total_earnings),
        "commission_breakdown": comm_breakdown,
        "reward_breakdown": reward_breakdown,
    }
