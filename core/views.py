# -*- coding: utf-8 -*-
from rest_framework import viewsets, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from core.models import CustomUser, Seller, Customer, Sale, Expense, DamageReport, ItemExit, Checklist, Task
from core.serializers import UserSerializer, SellerSerializer, CustomerSerializer, SaleSerializer, ExpenseSerializer, DamageReportSerializer, ItemExitSerializer, ChecklistSerializer, TaskSerializer
from core.authentication import StatelessTokenService
from core.permissions import IsAdminUser, IsOwnerOrAdminOnly

class AuthTokenView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not username or not password:
            return Response({"error": "نام کاربری و رمز عبور الزامی است."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = CustomUser.objects.get(username=username)
        except CustomUser.DoesNotExist:
            return Response({"error": "مشخصات نامعتبر است."}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.check_password(password):
            return Response({"error": "مشخصات نامعتبر است."}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response({"error": "حساب کاربری غیرفعال است."}, status=status.HTTP_403_FORBIDDEN)

        access_token, refresh_token = StatelessTokenService.generate_tokens(user)
        response = Response({"access_token": access_token, "role": user.role, "branch": user.branch}, status=status.HTTP_200_OK)
        response.set_cookie(key='refresh_token', value=refresh_token, httponly=True, secure=True, samesite='Strict')
        return response


class AuthTokenRefreshView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        refresh_token = request.COOKIES.get('refresh_token') or request.data.get('refresh_token')
        if not refresh_token:
            return Response({"error": "توکن یافت نشد."}, status=status.HTTP_400_BAD_REQUEST)

        payload = StatelessTokenService.verify_token(refresh_token, max_age=604800)
        if not payload or payload.get('type') != 'refresh':
            return Response({"error": "توکن نامعتبر است."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            user = CustomUser.objects.get(id=payload['user_id'])
        except CustomUser.DoesNotExist:
            return Response({"error": "کاربر یافت نشد."}, status=status.HTTP_401_UNAUTHORIZED)

        access_token, new_refresh_token = StatelessTokenService.generate_tokens(user)
        response = Response({"access_token": access_token}, status=status.HTTP_200_OK)
        response.set_cookie(key='refresh_token', value=new_refresh_token, httponly=True, secure=True, samesite='Strict')
        return response


class UserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]


class SellerViewSet(viewsets.ModelViewSet):
    queryset = Seller.objects.all()
    serializer_class = SellerSerializer
    def get_permissions(self):
        return [permissions.IsAuthenticated()] if self.action in ['list', 'retrieve'] else [IsAdminUser()]


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]


class SaleViewSet(viewsets.ModelViewSet):
    serializer_class = SaleSerializer
    permission_classes = [IsOwnerOrAdminOnly]

    def get_queryset(self):
        qs = Sale.objects.select_related('seller', 'customer', 'created_by').prefetch_related('payments', 'deposit_items')
        return qs if self.request.user.role == 'ADMIN' else qs.filter(created_by=self.request.user)


class ExpenseViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseSerializer
    permission_classes = [IsOwnerOrAdminOnly]

    def get_queryset(self):
        qs = Expense.objects.select_related('created_by').prefetch_related('cheques')
        return qs if self.request.user.role == 'ADMIN' else qs.filter(created_by=self.request.user)


class DamageReportViewSet(viewsets.ModelViewSet):
    queryset = DamageReport.objects.all()
    serializer_class = DamageReportSerializer
    permission_classes = [IsOwnerOrAdminOnly]
    def perform_create(self, serializer): serializer.save(created_by=self.request.user)


class ItemExitViewSet(viewsets.ModelViewSet):
    queryset = ItemExit.objects.all()
    serializer_class = ItemExitSerializer
    permission_classes = [IsOwnerOrAdminOnly]
    def perform_create(self, serializer): serializer.save(created_by=self.request.user)


class ChecklistViewSet(viewsets.ModelViewSet):
    queryset = Checklist.objects.all().prefetch_related('tasks')
    serializer_class = ChecklistSerializer
    def get_permissions(self): return [permissions.IsAuthenticated()] if self.action in ['list', 'retrieve'] else [IsAdminUser()]
    def perform_create(self, serializer): serializer.save(created_by=self.request.user)


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if request.user.role == 'USER':
            is_completed_val = request.data.get('is_completed', instance.is_completed)
            if isinstance(is_completed_val, str):
                is_completed_val = is_completed_val.lower() in ['true', '1', 'yes']
                
            instance.is_completed = bool(is_completed_val)
            instance.description = request.data.get('description', instance.description)
            
            if instance.is_completed:
                instance.completed_by = request.user
                instance.completed_at = timezone.now()
            else:
                instance.completed_by = None
                instance.completed_at = None
                
            instance.save()
            return Response(self.get_serializer(instance).data)
        return super().update(request, *args, **kwargs)