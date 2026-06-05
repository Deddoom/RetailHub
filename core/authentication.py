# -*- coding: utf-8 -*-
import base64
import json
from django.contrib.auth import get_user_model
from django.core.signing import TimestampSigner, SignatureExpired, BadSignature
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

User = get_user_model()

class StatelessTokenService:
    signer = TimestampSigner()

    @classmethod
    def generate_tokens(cls, user):
        access_payload = {'user_id': str(user.id), 'type': 'access'}
        refresh_payload = {'user_id': str(user.id), 'type': 'refresh'}
        
        access_str = base64.b64encode(cls.signer.sign(json.dumps(access_payload)).encode()).decode()
        refresh_str = base64.b64encode(cls.signer.sign(json.dumps(refresh_payload)).encode()).decode()
        return access_str, refresh_str

    @classmethod
    def verify_token(cls, token_b64, max_age):
        try:
            raw_token = base64.b64decode(token_b64.encode()).decode()
            payload_json = cls.signer.unsign(raw_token, max_age=max_age)
            return json.loads(payload_json)
        except (SignatureExpired, BadSignature, Exception):
            return None


class CustomStatelessAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if not auth_header:
            return None

        try:
            prefix, token = auth_header.split(' ')
            if prefix.lower() != 'bearer':
                return None
        except ValueError:
            return None

        payload = StatelessTokenService.verify_token(token, max_age=900)
        if not payload or payload.get('type') != 'access':
            raise AuthenticationFailed('توکن معتبر نمی‌باشد یا منقضی شده است.')

        try:
            # رفع باگ امنیتی شماره ۵: استعلام مجدد وضعیت و نقش زنده کاربر از دیتابیس
            user = User.objects.get(id=payload['user_id'])
        except User.DoesNotExist:
            raise AuthenticationFailed('کاربر یافت نشد.')

        if not user.is_active:
            raise AuthenticationFailed('حساب کاربری غیرفعال است.')

        return (user, None)