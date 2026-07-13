# -*- coding: utf-8 -*-
import base64
import json
from django.core.signing import TimestampSigner, SignatureExpired, BadSignature
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from drf_spectacular.extensions import OpenApiAuthenticationExtension

# مدت اعتبار توکن: ۵ سال (به ثانیه)
TOKEN_MAX_AGE = 60 * 60 * 24 * 365 * 5  # 157,680,000 seconds


class StatelessTokenService:
    signer = TimestampSigner()

    @classmethod
    def generate_token(cls, user):
        payload   = {'user_id': str(user.id), 'type': 'access'}
        token_str = base64.b64encode(cls.signer.sign(json.dumps(payload)).encode()).decode()
        return token_str

    @classmethod
    def verify_token(cls, token_b64):
        try:
            raw_token    = base64.b64decode(token_b64.encode()).decode()
            payload_json = cls.signer.unsign(raw_token, max_age=TOKEN_MAX_AGE)
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

        payload = StatelessTokenService.verify_token(token)
        if not payload or payload.get('type') != 'access':
            raise AuthenticationFailed('توکن معتبر نمی‌باشد یا منقضی شده است.')

        # ✅ باگ ۶ رفع شد: import lazy داخل تابع به جای سطح ماژول
        # این از کرش collectstatic و app-loading جلوگیری می‌کند
        from core.models import CustomUser
        try:
            user = CustomUser.objects.get(id=payload['user_id'])
        except CustomUser.DoesNotExist:
            raise AuthenticationFailed('کاربر یافت نشد.')

        if not user.is_active:
            raise AuthenticationFailed('حساب کاربری غیرفعال است.')

        return (user, None)
    
class StatelessTokenAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = 'core.authentication.CustomStatelessAuthentication'
    name = 'BearerAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'http',
            'scheme': 'bearer',
        }