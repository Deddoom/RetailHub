# -*- coding: utf-8 -*-
from django.contrib import admin
from core.models import (
    LiquidityDailyRevenueSetting, LiquidityExpense,
    LiquidityExpensePayment, LiquidityCardTransaction
)

class LiquidityExpensePaymentInline(admin.TabularInline):
    model = LiquidityExpensePayment
    extra = 1
    readonly_fields = ['created_by', 'created_at']

@admin.register(LiquidityExpense)
class LiquidityExpenseAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'amount', 'due_date', 'allocated_amount', 'remaining_debt', 'is_paid', 'created_at']
    list_filter = ['category', 'is_paid', 'due_date']
    search_fields = ['title', 'description']
    inlines = [LiquidityExpensePaymentInline]

@admin.register(LiquidityCardTransaction)
class LiquidityCardTransactionAdmin(admin.ModelAdmin):
    list_display = ['card_type', 'transaction_type', 'amount', 'date', 'created_by', 'created_at']
    list_filter = ['card_type', 'transaction_type', 'date']
    search_fields = ['description']

@admin.register(LiquidityDailyRevenueSetting)
class LiquidityDailyRevenueSettingAdmin(admin.ModelAdmin):
    list_display = ['amount', 'updated_by', 'updated_at']
