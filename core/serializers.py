# -*- coding: utf-8 -*-
from rest_framework import serializers
from django.db import transaction
from decimal import Decimal
from datetime import date

from core.models import (
    CustomUser, Role, Seller, Customer,
    Sale, Payment, Cheque, DepositItem,
    Expense, DamageReport, ItemExit,
    Checklist, Task, 
    DepositOrder, DepositOrderItem,
    BRANCH_CHOICES, Mission, ChecklistLog, ChecklistLogItem,
    Claim, ClaimItem, ClaimFollowUp,
)


# ── Role  ─────────────────────────────────────────────────────────────────────

class RoleSerializer(serializers.ModelSerializer):
    display = serializers.CharField(source='get_code_display', read_only=True)

    class Meta:
        model  = Role
        fields = ['id', 'code', 'display']


# ── Auth / User ───────────────────────────────────────────────────────────────

class UserSerializer(serializers.ModelSerializer):
    roles    = RoleSerializer(many=True, read_only=True)
    role_ids = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Role.objects.all(),
        source='roles', write_only=True, required=False
    )

    class Meta:
        model        = CustomUser
        fields       = [
            'id', 'username', 'first_name', 'last_name', 
            'is_profile_completed', 'roles', 'role_ids', 
            'branch', 'is_active', 'password'
        ]
        # فیلد تکمیل پروفایل توسط سیستم کنترل می‌شود اما قابل خواندن است
        read_only_fields = ['is_profile_completed']

    def create(self, validated_data):
        roles = validated_data.pop('roles', [])
        first_name = validated_data.get('first_name', '')
        last_name = validated_data.get('last_name', '')
        
        # اگر ادمین از ابتدا نام و فامیل را پر کرده باشد، پروفایل تکمیل‌شده فرض می‌شود
        if first_name or last_name:
            validated_data['is_profile_completed'] = True
            
        user  = CustomUser.objects.create_user(**validated_data)
        if roles:
            user.roles.set(roles)
        return user

    def update(self, instance, validated_data):
        roles    = validated_data.pop('roles', None)
        password = validated_data.pop('password', None)
        first_name = validated_data.get('first_name', instance.first_name)
        last_name = validated_data.get('last_name', instance.last_name)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
            
        if password:
            instance.set_password(password)
            
        # اگر نام یا فامیل ثبت شد، وضعیت تکمیل پروفایل True می‌شود
        if first_name or last_name:
            instance.is_profile_completed = True
            
        instance.save()
        if roles is not None:
            instance.roles.set(roles)
        return instance


# ── Seller ────────────────────────────────────────────────────────────────────

class SellerSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Seller
        fields = '__all__'


class SellerLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Seller
        fields = ['id', 'name', 'phone', 'branch']


# ── Customer ──────────────────────────────────────────────────────────────────

class CustomerSerializer(serializers.ModelSerializer):
    purchase_type = serializers.MultipleChoiceField(
        choices=[('CASH', 'نقدی'), ('CARD', 'کارتی'), ('ACCOUNT', 'حساب به حساب'), ('CHEQUE', 'چکی')]
    )
    class Meta:
        model            = Customer
        fields           = '__all__'
        read_only_fields = ['last_purchase_date', 'total_purchase_amount', 'last_purchase_type']


# ── Cheque ────────────────────────────────────────────────────────────────────

class ChequeSerializer(serializers.ModelSerializer):
    class Meta:
        model        = Cheque
        fields       = '__all__'
        extra_kwargs = {
            'payment':          {'required': False},
            'expense':          {'required': False},
            'cheque_image_url': {'required': False, 'allow_null': True},
        }


# ── Payment ───────────────────────────────────────────────────────────────────

class PaymentSerializer(serializers.ModelSerializer):
    cheques = ChequeSerializer(many=True, required=False)

    class Meta:
        model        = Payment
        fields       = '__all__'
        extra_kwargs = {'sale': {'required': False}}


# ── DepositItem ───────────────────────────────────────────────────────────────

class DepositItemSerializer(serializers.ModelSerializer):
    total_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model        = DepositItem
        fields       = '__all__'
        extra_kwargs = {'sale': {'required': False}}


# ── Sale ──────────────────────────────────────────────────────────────────────

class SaleSerializer(serializers.ModelSerializer):
    payments      = PaymentSerializer(many=True, required=False)
    deposit_items = DepositItemSerializer(many=True, required=False)
    created_by    = serializers.StringRelatedField(read_only=True)
    customer      = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model  = Sale
        fields = '__all__'

    def validate(self, attrs):
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError("کاربر درخواست‌کننده مشخص نیست.")
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get('request')
        user    = request.user

        payments_data = validated_data.pop('payments', [])
        deposit_items_data = validated_data.pop('deposit_items', [])

        total_paid   = sum(Decimal(str(p.get('amount', 0))) for p in payments_data)
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

        if sale.customer_id:
            customer = Customer.objects.select_for_update().get(pk=sale.customer_id)
            customer.last_purchase_date    = date.today()
            customer.total_purchase_amount += total_amount
            customer.last_purchase_type    = (
                'COMBINED' if len(payments_data) > 1
                else (payments_data[0].get('payment_method') if payments_data else 'REMAINING')
            )
            customer.save()

        return sale


class SaleListSerializer(serializers.ModelSerializer):
    seller_name    = serializers.CharField(source='seller.name',  read_only=True)
    customer_name  = serializers.CharField(source='customer.name',  read_only=True, default=None)
    customer_phone = serializers.CharField(source='customer.phone', read_only=True, default=None)
    created_by     = serializers.StringRelatedField(read_only=True)

    class Meta:
        model  = Sale
        fields = [
            'id', 'date_time', 'total_amount', 'remaining_balance',
            'branch', 'description',
            'seller', 'seller_name',
            'customer', 'customer_name', 'customer_phone',
            'created_by',
        ]


# ── Expense ───────────────────────────────────────────────────────────────────

class ExpenseSerializer(serializers.ModelSerializer):
    cheques    = ChequeSerializer(many=True, required=False)
    created_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model  = Expense
        fields = '__all__'

    @transaction.atomic
    def create(self, validated_data):
        request      = self.context.get('request')
        validated_data['created_by'] = request.user
        cheques_data = validated_data.pop('cheques', [])

        expense = Expense.objects.create(**validated_data)

        for ch_data in cheques_data:
            cheque_number    = ch_data.get('cheque_number')
            is_endorsed      = ch_data.pop('is_endorsed', False)
            cheque_image_url = ch_data.pop('cheque_image_url', None)

            if is_endorsed:
                existing = Cheque.objects.filter(cheque_number=cheque_number).first()
                if existing:
                    existing.is_endorsed      = True
                    existing.expense          = expense
                    if cheque_image_url:
                        existing.cheque_image_url = cheque_image_url
                    existing.description = (
                        f"{existing.description or ''} | خرج شده بابت فاکتور هزینه {expense.id}"
                    )
                    existing.save()
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


# ── DamageReport / ItemExit ───────────────────────────────────────────────────

class DamageReportSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model  = DamageReport
        fields = '__all__'


class ItemExitSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model  = ItemExit
        fields = '__all__'


# ── DepositOrder ──────────────────────────────────────────────────────────────

class DepositOrderItemSerializer(serializers.ModelSerializer):
    total_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model  = DepositOrderItem
        fields = ['id', 'item_name', 'quantity', 'unit_price', 'total_price']


class DepositOrderSerializer(serializers.ModelSerializer):
    items          = DepositOrderItemSerializer(many=True)
    created_by     = serializers.StringRelatedField(read_only=True)
    customer_name  = serializers.CharField(source='customer.name',  read_only=True)
    customer_phone = serializers.CharField(source='customer.phone', read_only=True)
    seller_name    = serializers.CharField(source='seller.name',    read_only=True)
    sale           = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model  = DepositOrder
        fields = [
            'id', 'created_at', 'branch',
            'created_by',
            'seller', 'seller_name',
            'customer', 'customer_name', 'customer_phone',
            'delivery_date',
            'total_amount', 'discount_amount',
            'deposit_paid', 'remaining_debt',
            'deposit_payment_method', 'debt_payment_method',
            'status', 'sale', 'description', 'items',
        ]
        read_only_fields = ['created_at', 'created_by', 'remaining_debt', 'sale']

    def validate(self, attrs):
        total    = Decimal(str(attrs.get('total_amount', 0)))
        discount = Decimal(str(attrs.get('discount_amount', 0)))
        paid     = Decimal(str(attrs.get('deposit_paid', 0)))

        if discount > total:
            raise serializers.ValidationError("تخفیف نمی‌تواند از مبلغ کل بیشتر باشد.")
        if paid > (total - discount):
            raise serializers.ValidationError("مبلغ بیعانه از مبلغ خالص سفارش (پس از تخفیف) بیشتر است.")
        if not attrs.get('items'):
            raise serializers.ValidationError("سفارش باید حداقل یک قلم کالا داشته باشد.")
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        validated_data['created_by'] = self.context['request'].user
        order = DepositOrder.objects.create(**validated_data)
        for item in items_data:
            DepositOrderItem.objects.create(order=order, **item)
        return order

    @transaction.atomic
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            instance.items.all().delete()
            for item in items_data:
                DepositOrderItem.objects.create(order=instance, **item)
        return instance


class DepositOrderListSerializer(serializers.ModelSerializer):
    customer_name  = serializers.CharField(source='customer.name',  read_only=True)
    customer_phone = serializers.CharField(source='customer.phone', read_only=True)
    seller_name    = serializers.CharField(source='seller.name',    read_only=True)
    created_by     = serializers.StringRelatedField(read_only=True)

    class Meta:
        model  = DepositOrder
        fields = [
            'id', 'created_at', 'branch',
            'created_by',
            'seller', 'seller_name',
            'customer', 'customer_name', 'customer_phone',
            'delivery_date',
            'total_amount', 'discount_amount',
            'deposit_paid', 'remaining_debt',
            'status', 'sale', 'description',
        ]


# ── Branch choices ────────────────────────────────────────────────────────────

class BranchChoicesSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()


# ── Mission ───────────────────────────────────────────────────────────────────

class MissionSerializer(serializers.ModelSerializer):
    # ─── حل مشکل اصلی: اضافه کردن فیلدهای متنی ریلیشن‌ها به صورت Read Only ───
    assigned_to_username = serializers.CharField(source='assigned_to.username', read_only=True)
    created_by_username  = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model  = Mission
        fields = '__all__'
        #fields = [
        #    'id', 'title',
        #    'assigned_to', 'assigned_to_username',
        #    'created_by',  'created_by_username',
        #    'start_date', 'end_date', 'status',
        #    'description', 'created_at', 'updated_at',
        #]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def validate(self, attrs):
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError("کاربر درخواست‌کننده مشخص نیست.")

        assigned_to_user = attrs.get('assigned_to')
        if assigned_to_user:
            if not assigned_to_user.is_active:
                raise serializers.ValidationError(
                    {"assigned_to": "امکان تخصیص مأموریت به کاربر غیرفعال وجود ندارد."}
                )
            if not request.user.is_superior_to(assigned_to_user):
                raise serializers.ValidationError(
                    {"assigned_to": "شما سطح دسترسی بالادستی برای تخصیص مأموریت به این کاربر را ندارید."}
                )

        if attrs.get('start_date') and attrs.get('end_date'):
            if attrs['start_date'] >= attrs['end_date']:
                raise serializers.ValidationError(
                    {"end_date": "تاریخ پایان مأموریت باید بعد از تاریخ شروع باشد."}
                )
        return attrs


# ── Task ──────────────────────────────────────────────────────────────────────

class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model            = Task
        fields           = ['id', 'checklist', 'title', 'is_completed', 'completed_by', 'completed_at', 'completion_note', 'description']
        read_only_fields = ['id', 'checklist', 'completed_by', 'completed_at']


# ── Checklist ─────────────────────────────────────────────────────────────────

class ChecklistSerializer(serializers.ModelSerializer):
    tasks                = TaskSerializer(many=True, required=False)
    created_by_username  = serializers.ReadOnlyField(source='created_by.username')
    assigned_to_username = serializers.ReadOnlyField(source='assigned_to.username')

    class Meta:
        model            = Checklist
        fields           = [
            'id', 'title', 'frequency',
            'assigned_to', 'assigned_to_username',
            'created_by',  'created_by_username',
            'tasks', 'created_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at']

    def validate_assigned_to(self, value):
        if value is None:
            return value

        request = self.context.get('request')
        if not value.is_active:
            raise serializers.ValidationError(
                "امکان تخصیص چک‌لیست به کاربر غیرفعال وجود ندارد."
            )
        if request and request.user:
            if not request.user.is_superior_to(value):
                raise serializers.ValidationError(
                    "شما بالادست این کاربر نیستید و نمی‌توانید برای او چک‌لیست تعیین کنید."
                )
        return value

    def create(self, validated_data):
        tasks_data = validated_data.pop('tasks', [])
        
        # ۱. ابتدا نمونه چک‌لیست را بدون ذخیره نهایی در دیتابیس می‌سازیم (commit=False)
        checklist = Checklist(**validated_data)
        
        # ۲. کاربر لاگین شده را به صورت مستقیم به ریلیشن مدل متصل می‌کنیم
        request = self.context.get('request')
        if request and request.user:
            checklist.created_by = request.user
        
        # ۳. حالا چک‌لیست را به صورت امن در دیتابیس ذخیره می‌کنیم
        checklist.save()
        
        # ۴. ذخیره تسک‌های متصل به آن
        for task_data in tasks_data:
            Task.objects.create(
                checklist=checklist,
                title=task_data.get('title'),
                description=task_data.get('description', '')
            )
            
        return checklist

    @transaction.atomic
    def update(self, instance, validated_data):
        tasks_data = validated_data.pop('tasks', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if tasks_data is not None:
            instance.tasks.all().delete()
            for task_data in tasks_data:
                Task.objects.create(checklist=instance, **task_data)

        return instance
    
class ChecklistLogItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChecklistLogItem
        fields = '__all__'

class ChecklistLogSerializer(serializers.ModelSerializer):
    items = ChecklistLogItemSerializer(many=True, read_only=True)

    class Meta:
        model = ChecklistLog
        fields = '__all__'

# ── Claim Serializers ─────────────────────────────────────────────────────────

class ClaimItemSerializer(serializers.ModelSerializer):
    total_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model  = ClaimItem
        fields = ['id', 'item_name', 'quantity', 'unit_price', 'total_price']


class ClaimFollowUpSerializer(serializers.ModelSerializer):
    follower_name = serializers.CharField(source='follower.username', read_only=True)

    class Meta:
        model  = ClaimFollowUp
        fields = ['id', 'follower', 'follower_name', 'follow_up_type', 'description', 'date']
        read_only_fields = ['follower', 'date']


class ClaimSerializer(serializers.ModelSerializer):
    items            = ClaimItemSerializer(many=True)
    follow_ups       = ClaimFollowUpSerializer(many=True, read_only=True)
    created_by_name  = serializers.CharField(source='created_by.username', read_only=True)
    seller_name      = serializers.CharField(source='seller.name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.username', read_only=True)

    class Meta:
        model  = Claim
        fields = [
            'id', 'customer_name', 'customer_phone', 'total_debt_amount',
            'status', 'taken_date', 'payment_deadline',
            'seller', 'seller_name', 'assigned_to', 'assigned_to_name',
            'created_by', 'created_by_name', 'description',
            'items', 'follow_ups', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        validated_data['created_by'] = self.context['request'].user
        
        claim = Claim.objects.create(**validated_data)
        for item in items_data:
            ClaimItem.objects.create(claim=claim, **item)
        return claim

    @transaction.atomic
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if items_data is not None:
            instance.items.all().delete()
            for item in items_data:
                ClaimItem.objects.create(claim=instance, **item)
        return instance