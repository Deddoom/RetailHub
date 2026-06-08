# -*- coding: utf-8 -*-
from rest_framework import serializers
from django.db import transaction
from decimal import Decimal
from datetime import date
from core.models import CustomUser, Seller, Customer, Sale, Payment, Expense, Cheque, DepositItem, DamageReport, ItemExit, Task, Checklist


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'role', 'branch', 'is_active', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        return CustomUser.objects.create_user(**validated_data)


class SellerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seller
        fields = '__all__'


# تغییر ۱: سریالایزر مختصر فروشنده فقط برای نمایش UUID + نام (مناسب برای dropdown)
class SellerLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seller
        fields = ['id', 'name', 'phone', 'branch']


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = '__all__'
        read_only_fields = ['last_purchase_date', 'total_purchase_amount', 'last_purchase_type']


class ChequeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cheque
        fields = '__all__'
        extra_kwargs = {
            'payment': {'required': False},
            'expense': {'required': False},
            # تغییر ۴: cheque_image_url اختیاری است
            'cheque_image_url': {'required': False, 'allow_null': True},
        }


class PaymentSerializer(serializers.ModelSerializer):
    cheques = ChequeSerializer(many=True, required=False)

    class Meta:
        model = Payment
        fields = '__all__'
        extra_kwargs = {'sale': {'required': False}}


class DepositItemSerializer(serializers.ModelSerializer):
    total_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = DepositItem
        fields = '__all__'
        extra_kwargs = {'sale': {'required': False}}


class SaleSerializer(serializers.ModelSerializer):
    payments = PaymentSerializer(many=True, required=False)
    deposit_items = DepositItemSerializer(many=True, required=False)
    created_by = serializers.StringRelatedField(read_only=True)
    # تغییر ۲: customer اختیاری — allow_null=True
    customer = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Sale
        fields = '__all__'

    def validate(self, attrs):
        payments_data = attrs.get('payments', [])
        deposit_items_data = attrs.get('deposit_items', [])
        total_amount = attrs.get('total_amount', Decimal('0.00'))

        total_paid = sum(Decimal(str(p.get('amount', 0))) for p in payments_data)
        if total_paid > total_amount:
            raise serializers.ValidationError("مجموع پرداخت‌ها از مبلغ کل فاکتور بیشتر است.")

        for payment in payments_data:
            if payment.get('payment_method') == 'DEPOSIT' and not deposit_items_data:
                raise serializers.ValidationError("در نوع پرداخت بیعانه، ثبت اقلام بیعانه اجباری است.")
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user

        payments_data = validated_data.pop('payments', [])
        deposit_items_data = validated_data.pop('deposit_items', [])

        total_paid = sum(Decimal(str(p.get('amount', 0))) for p in payments_data)
        total_amount = Decimal(str(validated_data.get('total_amount', 0)))
        validated_data['remaining_balance'] = max(Decimal('0.00'), total_amount - total_paid)
        validated_data['created_by'] = user

        sale = Sale.objects.create(**validated_data)

        for payment_item in payments_data:
            cheques_for_this_payment = payment_item.pop('cheques', [])
            payment_obj = Payment.objects.create(sale=sale, **payment_item)

            if payment_item.get('payment_method') in ['CHEQUE', 'COMBINED']:
                for cheque_item in cheques_for_this_payment:
                    customer_phone = cheque_item.pop('customer_phone',
                        sale.customer.phone if sale.customer else None)
                    customer_name = cheque_item.pop('customer_name',
                        sale.customer.name if sale.customer else None)
                    # تغییر ۴: cheque_image_url اختیاری — pop با پیش‌فرض None
                    cheque_image_url = cheque_item.pop('cheque_image_url', None)

                    if Cheque.objects.filter(cheque_number=cheque_item.get('cheque_number')).exists():
                        raise serializers.ValidationError("شماره چک قبلاً در سیستم ثبت شده است.")
                    Cheque.objects.create(
                        payment=payment_obj,
                        customer_phone=customer_phone,
                        customer_name=customer_name,
                        cheque_image_url=cheque_image_url,
                        **cheque_item
                    )

        for item_data in deposit_items_data:
            DepositItem.objects.create(sale=sale, **item_data)

        # به‌روزرسانی اطلاعات مشتری — فقط اگر مشتری تعیین شده باشد
        if sale.customer_id:
            customer = Customer.objects.select_for_update().get(pk=sale.customer_id)
            customer.last_purchase_date = date.today()
            customer.total_purchase_amount += total_amount
            customer.last_purchase_type = (
                'COMBINED' if len(payments_data) > 1
                else (payments_data[0].get('payment_method') if payments_data else 'REMAINING')
            )
            customer.save()

        return sale


class ExpenseSerializer(serializers.ModelSerializer):
    cheques = ChequeSerializer(many=True, required=False)
    created_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Expense
        fields = '__all__'

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['created_by'] = request.user
        cheques_data = validated_data.pop('cheques', [])

        expense = Expense.objects.create(**validated_data)

        for ch_data in cheques_data:
            cheque_number = ch_data.get('cheque_number')
            is_endorsed = ch_data.pop('is_endorsed', False)
            # تغییر ۴: cheque_image_url اختیاری
            cheque_image_url = ch_data.pop('cheque_image_url', None)

            if is_endorsed:
                existing_cheque = Cheque.objects.filter(cheque_number=cheque_number).first()
                if existing_cheque:
                    existing_cheque.is_endorsed = True
                    existing_cheque.expense = expense
                    if cheque_image_url:
                        existing_cheque.cheque_image_url = cheque_image_url
                    existing_cheque.description = (
                        f"{existing_cheque.description or ''} | خرج شده بابت فاکتور هزینه {expense.id}"
                    )
                    existing_cheque.save()
                else:
                    Cheque.objects.create(
                        expense=expense, is_endorsed=True,
                        cheque_image_url=cheque_image_url, **ch_data
                    )
            else:
                if Cheque.objects.filter(cheque_number=cheque_number).exists():
                    raise serializers.ValidationError("شماره چک وارد شده تکراری است.")
                Cheque.objects.create(
                    expense=expense, is_endorsed=False,
                    cheque_image_url=cheque_image_url, **ch_data
                )
        return expense


class DamageReportSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)
    class Meta:
        model = DamageReport
        fields = '__all__'


class ItemExitSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)
    class Meta:
        model = ItemExit
        fields = '__all__'


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = '__all__'
        read_only_fields = ['checklist']


class ChecklistSerializer(serializers.ModelSerializer):
    tasks = TaskSerializer(many=True, read_only=True)
    created_by = serializers.StringRelatedField(read_only=True)
    class Meta:
        model = Checklist
        fields = '__all__'


# تغییر ۳: سریالایزر مختصر برای لیست فروش‌ها (سبک‌تر از SaleSerializer کامل)
class SaleListSerializer(serializers.ModelSerializer):
    seller_name = serializers.CharField(source='seller.name', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True, default=None)
    customer_phone = serializers.CharField(source='customer.phone', read_only=True, default=None)
    created_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Sale
        fields = [
            'id', 'date_time', 'total_amount', 'remaining_balance',
            'branch', 'description',
            'seller', 'seller_name',
            'customer', 'customer_name', 'customer_phone',
            'created_by',
        ]