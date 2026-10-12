# -*- coding: utf-8 -*-
from django.contrib import admin
from core.models import (
    LiquidityDailyRevenueSetting, LiquidityExpense,
    LiquidityExpensePayment, LiquidityCardTransaction,
    LiquidityDailyCharge, LiquidityCheck
)

class LiquidityExpensePaymentInline(admin.TabularInline):
    model = LiquidityExpensePayment
    extra = 1
    readonly_fields = ['created_by', 'created_at']

@admin.register(LiquidityExpense)
class LiquidityExpenseAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'amount', 'initial_amount', 'has_spent_check', 'due_date', 'allocated_amount', 'remaining_debt', 'is_paid', 'created_at']
    list_filter = ['category', 'is_paid', 'has_spent_check', 'due_date']
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

@admin.register(LiquidityDailyCharge)
class LiquidityDailyChargeAdmin(admin.ModelAdmin):
    list_display = ['date', 'amount', 'branch_sales_total', 'debt_collection', 'passed_checks_amount', 'created_by', 'created_at']
    list_filter = ['date', 'created_at']
    search_fields = ['description']

@admin.register(LiquidityCheck)
class LiquidityCheckAdmin(admin.ModelAdmin):
    list_display = ['customer_name', 'branch', 'amount', 'due_date', 'status', 'spent_on_expense', 'created_at']
    list_filter = ['status', 'branch', 'due_date']
    search_fields = ['customer_name', 'description']
