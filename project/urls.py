# -*- coding: utf-8 -*-
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)


urlpatterns = [
    path('admin/', admin.site.urls),
    # OpenAPI Schema (JSON/YAML)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    # Swagger UI (Exact user requested path + aliases)
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui-docs'),
    path('api/swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui-alias'),
    # ReDoc (Exact user requested path + aliases)
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc-alias'),
    # API endpoints
    path('api/', include('core.urls')),
]


from django.urls import re_path
from django.views.static import serve

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]