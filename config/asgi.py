"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_asgi_application()

# Xử lý quá hạn nền (giữ chỗ 5 phút, đặt cọc 1 ngày...): mở khi web server khởi động, xem bookings/nen_qua_han.py
from bookings import nen_qua_han  # noqa: E402  (phải import sau khi Django đã nạp xong)

nen_qua_han.bat_dau()