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
    Claim, ClaimItem, ClaimFollowUp, DamageRegistration, DamageItem,
    ReturnRequest, ReturnItem, ExchangeItem,
    ReportDefinition, ReportSubmission, ReportImage,
    BranchTransfer, TransferItem, TransferLog,
    WasteReport, WasteItem, AdvanceRequest, AdvanceRequestLog
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
    superior_ids = serializers.PrimaryKeyRelatedField(
        many=True, queryset=CustomUser.objects.all(),
        source='superiors', write_only=True, required=False
    )
    superiors_info = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model        = CustomUser
        fields       = [
            'id', 'username', 'first_name', 'last_name',
            'is_profile_completed', 'roles', 'role_ids',
            'branch', 'is_active', 'password',
            'superiors_info', 'superior_ids'
        ]
        read_only_fields = ['is_profile_completed']
        extra_kwargs = {
            'password': {'write_only': True, 'required': False},
        }

    def get_superiors_info(self, obj):
        return [
            {
                "id": sup.id,
                "username": sup.username,
                "name": f"{sup.first_name} {sup.last_name}".strip()
            }
            for sup in obj.superiors.all()
        ]

    def create(self, validated_data):
        roles      = validated_data.pop('roles', [])
        superiors  = validated_data.pop('superiors', [])
        first_name = validated_data.get('first_name', '')
        last_name  = validated_data.get('last_name', '')

        if first_name or last_name:
            validated_data['is_profile_completed'] = True

        user = CustomUser.objects.create_user(**validated_data)

        if roles:
            user.roles.set(roles)
        if superiors:
            user.superiors.set(superiors)

        return user

    def update(self, instance, validated_data):
        roles      = validated_data.pop('roles', None)
        superiors  = validated_data.pop('superiors', None)
        password   = validated_data.pop('password', None)
        first_name = validated_data.get('first_name', instance.first_name)
        last_name  = validated_data.get('last_name', instance.last_name)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        if first_name or last_name:
            instance.is_profile_completed = True

        instance.save()

        if roles is not None:
            instance.roles.set(roles)
        if superiors is not None:
            instance.superiors.set(superiors)

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
    purchase_types = serializers.MultipleChoiceField(
        choices=[
            ('CASH',    'نقدی'),
            ('CARD',    'کارتی'),
            ('ACCOUNT', 'حساب به حساب'),
            ('CHEQUE',  'چکی'),
        ],
        required=False,
    )

    class Meta:
        model            = Customer
        fields           = '__all__'
        read_only_fields = ['last_purchase_date', 'total_purchase_amount']


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

        payments_data      = validated_data.pop('payments', [])
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
                    customer_phone   = cheque_item.pop('customer_phone',
                        sale.customer.phone if sale.customer else None)
                    customer_name    = cheque_item.pop('customer_name',
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

            new_methods = [
                p.get('payment_method') for p in payments_data if p.get('payment_method')
            ]
            customer.purchase_types = list(set(customer.purchase_types + new_methods))
            customer.save()

        return sale


class SaleListSerializer(serializers.ModelSerializer):
    seller_name    = serializers.CharField(source='seller.name',    read_only=True)
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
        if not self.instance:
            total    = Decimal(str(attrs.get('total_amount', 0)))
            discount = Decimal(str(attrs.get('discount_amount', 0)))
            paid     = Decimal(str(attrs.get('deposit_paid', 0)))

            if discount > total:
                raise serializers.ValidationError("تخفیف نمی‌تواند از مبلغ کل بیشتر باشد.")
            if paid > (total - discount):
                raise serializers.ValidationError("مبلغ بیعانه از مبلغ خالص سفارش (پس از تخفیف) بیشتر است.")
            if not attrs.get('items'):
                raise serializers.ValidationError("سفارش باید حداقل یک قلم کالا داشته باشد.")
        else:
            total    = Decimal(str(attrs.get('total_amount', self.instance.total_amount)))
            discount = Decimal(str(attrs.get('discount_amount', self.instance.discount_amount)))
            paid     = Decimal(str(attrs.get('deposit_paid', self.instance.deposit_paid)))

            if discount > total:
                raise serializers.ValidationError("تخفیف نمی‌تواند از مبلغ کل بیشتر باشد.")
            if paid > (total - discount):
                raise serializers.ValidationError("مبلغ بیعانه از مبلغ خالص سفارش (پس از تخفیف) بیشتر است.")

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
    assigned_to_username = serializers.CharField(source='assigned_to.username', read_only=True)
    created_by_username  = serializers.CharField(source='created_by.username',  read_only=True)

    class Meta:
        model            = Mission
        fields           = '__all__'
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
    id = serializers.UUIDField(required=False)

    class Meta:
        model            = Task
        fields           = ['id', 'checklist', 'title', 'is_completed', 'completed_by', 'completed_at', 'completion_note', 'description']
        read_only_fields = ['checklist', 'completed_by', 'completed_at']


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
            raise serializers.ValidationError("کاربر غیرفعال است.")
        if request and request.user:
            user     = request.user
            is_admin = user.is_superuser or any(r.code == 'ADMIN' for r in user.roles.all())
            if not is_admin and not user.is_superior_to(value):
                raise serializers.ValidationError("شما بالادست این کاربر نیستید.")
        return value

    def create(self, validated_data):
        tasks_data = validated_data.pop('tasks', [])
        checklist  = Checklist(**validated_data)

        request = self.context.get('request')
        if request and request.user:
            checklist.created_by = request.user

        checklist.save()

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
            existing_tasks = {str(t.id): t for t in instance.tasks.all()}
            incoming_ids   = {str(t['id']) for t in tasks_data if 'id' in t}

            for tid, task_obj in existing_tasks.items():
                if tid not in incoming_ids:
                    task_obj.delete()

            for task_data in tasks_data:
                tid = str(task_data.get('id', ''))
                if tid and tid in existing_tasks:
                    task_obj = existing_tasks[tid]
                    task_obj.title       = task_data.get('title', task_obj.title)
                    task_obj.description = task_data.get('description', task_obj.description)
                    task_obj.save()
                else:
                    Task.objects.create(
                        checklist=instance,
                        title=task_data.get('title', ''),
                        description=task_data.get('description', '')
                    )

        return instance


class ChecklistLogItemSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ChecklistLogItem
        fields = '__all__'


class ChecklistLogSerializer(serializers.ModelSerializer):
    items = ChecklistLogItemSerializer(many=True, read_only=True)

    class Meta:
        model  = ChecklistLog
        fields = '__all__'


# ── Claim Serializers ─────────────────────────────────────────────────────────

class ClaimItemSerializer(serializers.ModelSerializer):
    id          = serializers.UUIDField(required=False)
    total_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model  = ClaimItem
        fields = ['id', 'item_name', 'quantity', 'unit_price', 'total_price']


class ClaimFollowUpSerializer(serializers.ModelSerializer):
    follower_name = serializers.CharField(source='follower.username', read_only=True)

    class Meta:
        model            = ClaimFollowUp
        fields           = ['id', 'follower', 'follower_name', 'follow_up_type', 'description', 'date']
        read_only_fields = ['follower', 'date']


class ClaimSerializer(serializers.ModelSerializer):
    items            = ClaimItemSerializer(many=True)
    follow_ups       = ClaimFollowUpSerializer(many=True, read_only=True)
    created_by_name  = serializers.CharField(source='created_by.username', read_only=True)
    assigned_to_name = serializers.SerializerMethodField()

    def get_assigned_to_name(self, obj):
        return obj.assigned_to.username if obj.assigned_to else None

    class Meta:
        model  = Claim
        fields = [
            'id', 'customer_name', 'customer_phone', 'total_debt_amount',
            'status', 'taken_date', 'payment_deadline',
            'seller',
            'assigned_to', 'assigned_to_name',
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
            existing = {str(i.id): i for i in instance.items.all()}
            incoming_ids = {str(i['id']) for i in items_data if 'id' in i}

            for iid, item_obj in existing.items():
                if iid not in incoming_ids:
                    item_obj.delete()

            for item_data in items_data:
                iid = str(item_data.get('id', ''))
                if iid and iid in existing:
                    item_obj = existing[iid]
                    for attr, val in item_data.items():
                        setattr(item_obj, attr, val)
                    item_obj.save()
                else:
                    ClaimItem.objects.create(claim=instance, **item_data)

        return instance


# ── Damage Registration Serializers ──────────────────────────────────────────

class DamageItemSerializer(serializers.ModelSerializer):
    id          = serializers.UUIDField(required=False)
    total_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model  = DamageItem
        fields = ['id', 'item_name', 'quantity', 'unit_price', 'total_price']


class DamageRegistrationSerializer(serializers.ModelSerializer):
    items           = DamageItemSerializer(many=True)
    created_by_name = serializers.CharField(source='created_by.first_name', read_only=True)

    class Meta:
        model  = DamageRegistration
        fields = [
            'id', 'date', 'branch', 'reason', 'culprit', 'description',
            'created_by', 'created_by_name', 'items', 'created_at'
        ]
        read_only_fields = ['created_by', 'created_at']

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        validated_data['created_by'] = self.context['request'].user
        registration = DamageRegistration.objects.create(**validated_data)
        for item in items_data:
            DamageItem.objects.create(registration=registration, **item)
        return registration

    @transaction.atomic
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if items_data is not None:
            instance.items.all().delete()
            for item in items_data:
                DamageItem.objects.create(registration=instance, **item)
        return instance


# ── Return Request Serializers ────────────────────────────────────────────────

class ReturnItemSerializer(serializers.ModelSerializer):
    id          = serializers.UUIDField(required=False)
    total_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model  = ReturnItem
        fields = ['id', 'item_name', 'quantity', 'unit_price', 'discount', 'total_price']


class ExchangeItemSerializer(serializers.ModelSerializer):
    id          = serializers.UUIDField(required=False)
    total_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model  = ExchangeItem
        fields = ['id', 'item_name', 'quantity', 'unit_price', 'total_price']


class ReturnRequestSerializer(serializers.ModelSerializer):
    return_items    = ReturnItemSerializer(many=True)
    exchange_items  = ExchangeItemSerializer(many=True, required=False)
    created_by_name = serializers.CharField(source='created_by.first_name', read_only=True)
    seller_name     = serializers.CharField(source='seller.name', read_only=True)

    class Meta:
        model  = ReturnRequest
        fields = [
            'id', 'customer_name', 'customer_phone', 'seller', 'seller_name',
            'action_type', 'refund_amount', 'status', 'is_approved',
            'refund_date', 'refund_method', 'description',
            'created_by', 'created_by_name',
            'return_items', 'exchange_items', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'status', 'is_approved', 'created_at', 'updated_at']

    @transaction.atomic
    def create(self, validated_data):
        return_items_data   = validated_data.pop('return_items', [])
        exchange_items_data = validated_data.pop('exchange_items', [])
        validated_data['created_by'] = self.context['request'].user

        return_request = ReturnRequest.objects.create(**validated_data)

        for item in return_items_data:
            ReturnItem.objects.create(return_request=return_request, **item)
        for item in exchange_items_data:
            ExchangeItem.objects.create(return_request=return_request, **item)

        return return_request

    @transaction.atomic
    def update(self, instance, validated_data):
        return_items_data   = validated_data.pop('return_items', None)
        exchange_items_data = validated_data.pop('exchange_items', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if return_items_data is not None:
            existing = {str(i.id): i for i in instance.return_items.all()}
            incoming_ids = {str(i['id']) for i in return_items_data if 'id' in i}
            for iid, item_obj in existing.items():
                if iid not in incoming_ids:
                    item_obj.delete()
            for item_data in return_items_data:
                iid = str(item_data.get('id', ''))
                if iid and iid in existing:
                    item_obj = existing[iid]
                    for attr, val in item_data.items():
                        setattr(item_obj, attr, val)
                    item_obj.save()
                else:
                    ReturnItem.objects.create(return_request=instance, **item_data)

        if exchange_items_data is not None:
            existing = {str(i.id): i for i in instance.exchange_items.all()}
            incoming_ids = {str(i['id']) for i in exchange_items_data if 'id' in i}
            for iid, item_obj in existing.items():
                if iid not in incoming_ids:
                    item_obj.delete()
            for item_data in exchange_items_data:
                iid = str(item_data.get('id', ''))
                if iid and iid in existing:
                    item_obj = existing[iid]
                    for attr, val in item_data.items():
                        setattr(item_obj, attr, val)
                    item_obj.save()
                else:
                    ExchangeItem.objects.create(return_request=instance, **item_data)

        return instance


# ════════════════════════════════════════════════════════════════════════════
#  سریالایزرهای سیستم گزارش‌دهی
# ════════════════════════════════════════════════════════════════════════════

class ReportImageSerializer(serializers.ModelSerializer):
    class Meta:
        model            = ReportImage
        fields           = ['id', 'image_url', 'caption', 'uploaded_at']
        read_only_fields = ['uploaded_at']


class ReportDefinitionSerializer(serializers.ModelSerializer):
    """
    فیلد questions:
      ورودی و خروجی به صورت لیست آبجکت با ساختار:
      [{"id": "q1", "text": "متن سوال اول"}, {"id": "q2", "text": "متن سوال دوم"}]

    اعتبارسنجی:
      - هر آیتم باید دارای کلید "id" و "text" باشد
      - مقدار "id" در داخل یک definition باید یکتا باشد
    """
    superior_username    = serializers.CharField(source='superior.username',    read_only=True)
    subordinate_username = serializers.CharField(source='subordinate.username', read_only=True)

    class Meta:
        model  = ReportDefinition
        fields = [
            'id', 'title', 'report_type',
            'interval', 'deadline',
            'questions', 'is_active', 'created_at',
            'superior',    'superior_username',
            'subordinate', 'subordinate_username',
        ]
        read_only_fields = ['id', 'superior', 'created_at']

    def validate_questions(self, value):
        """
        اعتبارسنجی ساختار questions:
        باید لیستی از {"id": "...", "text": "..."} باشد.
        """
        if not isinstance(value, list) or len(value) == 0:
            raise serializers.ValidationError(
                "سوالات باید به صورت لیست غیرخالی ارسال شوند."
            )

        seen_ids = set()
        for idx, item in enumerate(value):
            if not isinstance(item, dict):
                raise serializers.ValidationError(
                    f"سوال شماره {idx + 1}: باید آبجکت باشد "
                    f'(مثال: {{"id": "q1", "text": "متن سوال"}}).'
                )
            if 'id' not in item or not str(item['id']).strip():
                raise serializers.ValidationError(
                    f"سوال شماره {idx + 1}: فیلد «id» الزامی است."
                )
            if 'text' not in item or not str(item['text']).strip():
                raise serializers.ValidationError(
                    f"سوال شماره {idx + 1}: فیلد «text» الزامی است."
                )
            q_id = str(item['id']).strip()
            if q_id in seen_ids:
                raise serializers.ValidationError(
                    f"شناسه سوال «{q_id}» تکراری است. هر سوال باید id یکتا داشته باشد."
                )
            seen_ids.add(q_id)

        return value

    def validate(self, data):
        report_type = data.get('report_type') or (self.instance.report_type if self.instance else None)

        if report_type == 'RECURRING' and not data.get('interval'):
            raise serializers.ValidationError(
                {"interval": "برای گزارش‌های تکراری، تعیین دوره (interval) الزامی است."}
            )
        if report_type == 'DEADLINE' and not data.get('deadline'):
            raise serializers.ValidationError(
                {"deadline": "برای گزارش‌های مهلت‌دار، تعیین تاریخ مهلت (deadline) الزامی است."}
            )

        request    = self.context.get('request')
        subordinate = data.get('subordinate')
        if request and subordinate:
            superior = request.user
            is_admin = superior.is_superuser or any(r.code == 'ADMIN' for r in superior.roles.all())
            if not is_admin and not superior.is_superior_to(subordinate):
                raise serializers.ValidationError(
                    {"subordinate": "شما بالادست این کاربر نیستید و نمی‌توانید برایش گزارش تعریف کنید."}
                )
        return data


class ReportSubmissionSerializer(serializers.ModelSerializer):
    """
    سریالایزر ارسال پاسخ و ثبت نهایی گزارش توسط زیردستی.
    این سریالایزر وظیفه ثبت تاریخچه (لاگ) و غیرفعال‌سازی خودکار گزارشات مهلت‌دار را بر عهده دارد.
    """
    images                = ReportImageSerializer(many=True, read_only=True)
    submitted_by_username = serializers.CharField(source='submitted_by.username', read_only=True)
    definition_title      = serializers.CharField(source='definition.title',      read_only=True)

    # فیلد نوشتنی برای ارسال تصاویر به همراه گزارش (نمایش دقیق در Swagger)
    image_urls = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text=(
            'لیستی از تصاویر برای ضمیمه شدن به گزارش.\n\n'
            'نمونه ساختار ارسالی:\n'
            '```json\n'
            '[\n'
            '  {"image_url": "[https://example.com/img1.jpg](https://example.com/img1.jpg)", "caption": "توضیح عکس اول"},\n'
            '  {"image_url": "[https://example.com/img2.jpg](https://example.com/img2.jpg)", "caption": "توضیح عکس دوم"}\n'
            ']\n'
            '```'
        )
    )

    class Meta:
        model  = ReportSubmission
        fields = [
            'id', 'definition', 'definition_title',
            'submitted_by', 'submitted_by_username',
            'answers', 'submitted_at',
            'images', 'image_urls',
        ]
        read_only_fields = ['id', 'submitted_by', 'submitted_at']
        extra_kwargs = {
            'answers': {
                'help_text': (
                    'آرایه‌ای از پاسخ‌ها برای سوالات مشخص شده در تعریف گزارش.\n\n'
                    'نمونه ساختار ارسالی (فرانت‌اند فقط id و answer را می‌فرستد):\n'
                    '```json\n'
                    '[\n'
                    '  {"question_id": "q1", "answer": "پاسخ اول"},\n'
                    '  {"question_id": "q2", "answer": "پاسخ دوم"}\n'
                    ']\n'
                    '```\n'
                    '**نکته لاگ‌گیری:** هنگام ذخیره در دیتابیس، بک‌اند به صورت خودکار متن دقیق سوال (`question_text`) را نیز به این JSON اضافه می‌کند تا تاریخچه گزارش همیشه و بدون وابستگی به سوالات اولیه خوانا بماند.'
                )
            }
        }

    def validate_answers(self, value):
        """
        بررسی اولیه ساختار فیلد answers (آرایه بودن و داشتن کلیدهای ضروری)
        """
        if not isinstance(value, list):
            raise serializers.ValidationError("پاسخ‌ها باید به صورت یک آرایه (لیست) ارسال شوند.")

        for idx, item in enumerate(value):
            if not isinstance(item, dict):
                raise serializers.ValidationError(
                    f"پاسخ شماره {idx + 1}: باید یک آبجکت (JSON) باشد."
                )
            if 'question_id' not in item or not str(item.get('question_id', '')).strip():
                raise serializers.ValidationError(
                    f"پاسخ شماره {idx + 1}: ارسال کلید «question_id» الزامی است."
                )
            if 'answer' not in item:
                raise serializers.ValidationError(
                    f"پاسخ شماره {idx + 1}: ارسال کلید «answer» الزامی است."
                )

        return value

    def validate(self, data):
        """
        بررسی لاجیک تجاری:
        ۱. آیا کاربر دسترسی دارد؟
        ۲. آیا به همه سوالات پاسخ داده شده است؟
        ۳. تزریق متن سوال به پاسخ برای ایجاد لاگ دائمی و غیرقابل تغییر.
        """
        request    = self.context.get('request')
        definition = data.get('definition') or (self.instance.definition if self.instance else None)

        if not definition:
            return data

        # بررسی اینکه آیا کاربر ارسال کننده، همان زیردستی هدف است یا خیر (ادمین مستثنی است)
        if request and definition.subordinate != request.user:
            is_admin = request.user.is_superuser or any(
                r.code == 'ADMIN' for r in request.user.roles.all()
            )
            if not is_admin:
                raise serializers.ValidationError(
                    "شما دسترسی ثبت پاسخ برای این گزارش را ندارید. این گزارش به کاربر دیگری ارجاع داده شده است."
                )

        # اعتبارسنجی تطابق سوالات و پاسخ‌ها
        answers = data.get('answers', [])
        if answers is not None:
            # استخراج آیدی و متن سوالات اصلی برای مقایسه و تزریق
            valid_questions = {str(q['id']): q['text'] for q in definition.questions}
            answered_ids    = {str(a['question_id']) for a in answers}

            # ۱. بررسی question_id هایی که در فرم اصلی وجود ندارند
            invalid_ids = answered_ids - set(valid_questions.keys())
            if invalid_ids:
                raise serializers.ValidationError(
                    {"answers": f"شناسه‌های سوال نامعتبر ارسال شده است: {', '.join(sorted(invalid_ids))}"}
                )

            # ۲. بررسی سوالاتی که زیردستی به آن‌ها پاسخ نداده است
            missing_ids = set(valid_questions.keys()) - answered_ids
            if missing_ids:
                # پیدا کردن متن سوالات بی‌پاسخ برای نمایش بهتر خطای فارسی
                missing_texts = [valid_questions[qid] for qid in missing_ids]
                raise serializers.ValidationError(
                    {"answers": f"شما به این سوالات پاسخ نداده‌اید: {', '.join(missing_texts)}"}
                )

            # 🔥 ۳. پیاده‌سازی لاگ دائمی:
            # تزریق متن دقیق سوال به آبجکت پاسخ‌ها.
            # با این کار اگر در آینده بالادستی نام سوال را در Definition عوض کرد، لاگ این گزارش قدیمی دست‌نخورده می‌ماند.
            for a in answers:
                # کلید جدیدی به نام question_text به JSON پاسخ در دیتابیس اضافه می‌شود
                a['question_text'] = valid_questions[str(a['question_id'])]

        return data

    def _validate_image_urls(self, image_urls_data):
        """اعتبارسنجی ساختار لیست تصاویر"""
        for idx, img in enumerate(image_urls_data):
            if not isinstance(img, dict):
                raise serializers.ValidationError(
                    f"تصویر شماره {idx + 1}: باید یک آبجکت باشد."
                )
            if 'image_url' not in img or not str(img.get('image_url', '')).strip():
                raise serializers.ValidationError(
                    f"تصویر شماره {idx + 1}: فیلد «image_url» الزامی است."
                )

    @transaction.atomic
    def create(self, validated_data):
        image_urls_data = validated_data.pop('image_urls', [])
        validated_data['submitted_by'] = self.context['request'].user

        self._validate_image_urls(image_urls_data)

        # ساخت رکورد گزارش با پاسخ‌هایی که در متد validate دارای question_text شده‌اند
        submission = ReportSubmission.objects.create(**validated_data)

        # ثبت عکس‌های ضمیمه
        for img in image_urls_data:
            ReportImage.objects.create(
                submission=submission,
                image_url=img.get('image_url', ''),
                caption=img.get('caption', '')
            )
            
        # 🔥 بایگانی خودکار (Archiving)
        # اگر گزارش از نوع مهلت‌دار (یک‌بار مصرف) است، پس از ارسال گزارش توسط زیردستی،
        # گزارش اصلی (Definition) به صورت خودکار غیرفعال می‌شود تا از کارتابل زیردستی خارج شود،
        # اما لاگ‌های آن در سیستم باقی می‌مانند.
        if submission.definition.report_type == 'DEADLINE':
            submission.definition.is_active = False
            submission.definition.save()

        return submission

    @transaction.atomic
    def update(self, instance, validated_data):
        image_urls_data = validated_data.pop('image_urls', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # بروزرسانی عکس‌های گزارش
        if image_urls_data is not None:
            self._validate_image_urls(image_urls_data)
            instance.images.all().delete()
            for img in image_urls_data:
                ReportImage.objects.create(
                    submission=instance,
                    image_url=img.get('image_url', ''),
                    caption=img.get('caption', '')
                )

        return instance
    
# ── Transfer Serializers ──────────────────────────────────────────────────────
 
class TransferItemSerializer(serializers.ModelSerializer):
    class Meta:
        model  = TransferItem
        fields = ['id', 'item_name', 'quantity', 'price']
 
 
class TransferLogSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(
        source='created_by.username', read_only=True, default=''
    )
 
    class Meta:
        model  = TransferLog
        fields = ['id', 'message', 'created_by_username', 'created_at']
 
 
class BranchTransferSerializer(serializers.ModelSerializer):
    """سریالایزر کامل برای ایجاد/ویرایش/جزئیات انتقال"""
    items = TransferItemSerializer(many=True)
    logs  = TransferLogSerializer(many=True, read_only=True)
 
    source_cashier_name      = serializers.CharField(
        source='source_cashier.get_full_name', read_only=True
    )
    sender_supervisor_name   = serializers.CharField(
        source='sender_supervisor.get_full_name', read_only=True
    )
    receiver_supervisor_name = serializers.CharField(
        source='receiver_supervisor.get_full_name', read_only=True
    )
 
    class Meta:
        model  = BranchTransfer
        fields = [
            'id',
            'source_cashier',      'source_cashier_name',
            'source_branch',       'destination_branch',
            'sender_supervisor',   'sender_supervisor_name',
            'receiver_supervisor', 'receiver_supervisor_name',
            'transfer_date',       'driver_name',
            'description',
            'status',
            'rejection_reason',
            'sender_note',
            'receiver_note',
            'items',
            'logs',
            'created_at',          'updated_at',
        ]
        read_only_fields = [
            'status', 'rejection_reason',
            'sender_note', 'receiver_note',
            'created_at', 'updated_at',
        ]
 
    def validate(self, data):
        src = data.get('source_branch',      getattr(self.instance, 'source_branch',      None))
        dst = data.get('destination_branch', getattr(self.instance, 'destination_branch', None))
        if src and dst and src == dst:
            raise serializers.ValidationError(
                {"destination_branch": "شعبه مبدا و مقصد نمی‌توانند یکسان باشند."}
            )
        if not data.get('items') and not self.instance:
            raise serializers.ValidationError(
                {"items": "انتقال باید حداقل یک قلم کالا داشته باشد."}
            )
        return data
 
    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        validated_data['source_cashier'] = self.context['request'].user
        transfer   = BranchTransfer.objects.create(**validated_data)
        for item in items_data:
            TransferItem.objects.create(transfer=transfer, **item)
 
        # لاگ اولیه ثبت درخواست
        TransferLog.objects.create(
            transfer=transfer,
            created_by=transfer.source_cashier,
            message=(
                f"درخواست انتقال توسط {transfer.source_cashier.get_full_name() or transfer.source_cashier.username} "
                f"از {transfer.source_branch} به {transfer.destination_branch} ثبت شد و "
                f"در انتظار تایید سرپرست مبدا ({transfer.sender_supervisor.get_full_name() or transfer.sender_supervisor.username}) است."
            ),
        )
        return transfer
 
    @transaction.atomic
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
 
        # اگر قبلاً رد شده بود و الان ویرایش می‌شود، برمی‌گردد به انتظار تایید
        if instance.status == 'REJECTED':
            instance.status          = 'PENDING_SENDER'
            instance.rejection_reason = None
 
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
 
        if items_data is not None:
            instance.items.all().delete()
            for item in items_data:
                TransferItem.objects.create(transfer=instance, **item)
 
        request = self.context.get('request')
        user    = request.user if request else None
        TransferLog.objects.create(
            transfer=instance,
            created_by=user,
            message="اطلاعات انتقال ویرایش شد و مجدداً در انتظار تایید سرپرست مبدا قرار گرفت.",
        )
        return instance
 
 
class BranchTransferListSerializer(serializers.ModelSerializer):
    """سریالایزر سبک برای لیست"""
    source_cashier_name      = serializers.CharField(source='source_cashier.get_full_name',      read_only=True)
    sender_supervisor_name   = serializers.CharField(source='sender_supervisor.get_full_name',   read_only=True)
    receiver_supervisor_name = serializers.CharField(source='receiver_supervisor.get_full_name', read_only=True)
    items_count              = serializers.SerializerMethodField()
 
    def get_items_count(self, obj):
        return obj.items.count()
 
    class Meta:
        model  = BranchTransfer
        fields = [
            'id',
            'source_cashier',      'source_cashier_name',
            'source_branch',       'destination_branch',
            'sender_supervisor',   'sender_supervisor_name',
            'receiver_supervisor', 'receiver_supervisor_name',
            'transfer_date',       'driver_name',
            'status',              'items_count',
            'created_at',
        ]
 
 
# ── Waste Report Serializers ──────────────────────────────────────────────────
 
class WasteItemSerializer(serializers.ModelSerializer):
    class Meta:
        model  = WasteItem
        fields = ['id', 'item_name', 'quantity', 'price']
 
 
class WasteReportSerializer(serializers.ModelSerializer):
    """سریالایزر کامل برای ایجاد/ویرایش/جزئیات گزارش ضایعات"""
    items                  = WasteItemSerializer(many=True)
    reporter_name          = serializers.CharField(
        source='reporter.get_full_name', read_only=True
    )
    warehouse_reviewer_name = serializers.CharField(
        source='warehouse_reviewer.get_full_name', read_only=True, default=None
    )
    admin_reviewer_name    = serializers.CharField(
        source='admin_reviewer.get_full_name', read_only=True, default=None
    )
    involved_users_detail  = serializers.SerializerMethodField(read_only=True)
 
    def get_involved_users_detail(self, obj):
        return [
            {
                "id":       str(u.id),
                "username": u.username,
                "name":     u.get_full_name() or u.username,
            }
            for u in obj.involved_users.all()
        ]
 
    class Meta:
        model  = WasteReport
        fields = [
            'id',
            'reporter',                'reporter_name',
            'waste_date',              'branch',
            'description',
            'involved_users',          'involved_users_detail',
            'status',
            'warehouse_reviewer',      'warehouse_reviewer_name',
            'warehouse_comment',
            'admin_reviewer',          'admin_reviewer_name',
            'admin_instruction',
            'items',
            'created_at',              'updated_at',
        ]
        read_only_fields = [
            'reporter',
            'status',
            'warehouse_reviewer', 'warehouse_comment',
            'admin_reviewer',     'admin_instruction',
            'created_at',         'updated_at',
        ]
 
    @transaction.atomic
    def create(self, validated_data):
        items_data         = validated_data.pop('items')
        involved_users     = validated_data.pop('involved_users', [])
        validated_data['reporter'] = self.context['request'].user
 
        waste_report = WasteReport.objects.create(**validated_data)
        waste_report.involved_users.set(involved_users)
 
        for item in items_data:
            WasteItem.objects.create(waste_report=waste_report, **item)
        return waste_report
 
    @transaction.atomic
    def update(self, instance, validated_data):
        items_data     = validated_data.pop('items', None)
        involved_users = validated_data.pop('involved_users', None)
 
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
 
        if involved_users is not None:
            instance.involved_users.set(involved_users)
 
        if items_data is not None:
            instance.items.all().delete()
            for item in items_data:
                WasteItem.objects.create(waste_report=instance, **item)
        return instance
 
 
class WasteReportListSerializer(serializers.ModelSerializer):
    """سریالایزر سبک برای لیست"""
    reporter_name = serializers.CharField(source='reporter.get_full_name', read_only=True)
    items_count   = serializers.SerializerMethodField()
 
    def get_items_count(self, obj):
        return obj.items.count()
 
    class Meta:
        model  = WasteReport
        fields = [
            'id', 'reporter', 'reporter_name',
            'waste_date', 'branch',
            'status', 'items_count',
            'created_at',
        ]

# ══════════════════════════════════════════════════════════════════════════════
#  سیستم درخواست مساعده (Advance Request)
# ══════════════════════════════════════════════════════════════════════════════

class AdvanceRequestLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.get_full_name', read_only=True)
    actor_username = serializers.CharField(source='actor.username', read_only=True)

    class Meta:
        model = AdvanceRequestLog
        fields = ['id', 'actor_name', 'actor_username', 'action', 'created_at']


class AdvanceRequestSerializer(serializers.ModelSerializer):
    logs = AdvanceRequestLogSerializer(many=True, read_only=True)
    requester_name = serializers.CharField(source='requester.get_full_name', read_only=True)
    superior_reviewer_name = serializers.CharField(source='superior_reviewer.get_full_name', read_only=True)
    admin_reviewer_name = serializers.CharField(source='admin_reviewer.get_full_name', read_only=True)
    finance_reviewer_name = serializers.CharField(source='finance_reviewer.get_full_name', read_only=True)

    class Meta:
        model = AdvanceRequest
        fields = [
            'id', 'requester', 'requester_name', 'amount', 'description', 'status',
            'superior_reviewer', 'superior_reviewer_name', 'superior_note',
            'admin_reviewer', 'admin_reviewer_name', 'admin_note',
            'finance_reviewer', 'finance_reviewer_name', 'payment_date', 'finance_note',
            'logs', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'requester', 'status', 'superior_reviewer', 'superior_note',
            'admin_reviewer', 'admin_note', 'finance_reviewer', 'payment_date', 'finance_note'
        ]


class AdvanceRequestListSerializer(serializers.ModelSerializer):
    requester_name = serializers.CharField(source='requester.get_full_name', read_only=True)
    
    class Meta:
        model = AdvanceRequest
        fields = [
            'id', 'requester', 'requester_name', 'amount', 'status', 'created_at'
        ]