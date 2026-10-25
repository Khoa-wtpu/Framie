# profiles/admin.py - đăng ký models để thêm dữ liệu thử ở http://127.0.0.1:8000/admin/
from django.contrib import admin

from .models import (
    DuyetHoSo, GoiDichVu, HinhAnhProject, KhuVuc, LoaiHinhChup, NhiepAnhGia,
    NhiepAnhGia_KhuVuc, NhiepAnhGia_LoaiHinhChup, NhiepAnhGia_PhongCach, PhongCach, Project,
)

admin.site.register([LoaiHinhChup, PhongCach, KhuVuc, GoiDichVu, DuyetHoSo])


class LoaiHinhInline(admin.TabularInline):
    model = NhiepAnhGia_LoaiHinhChup
    extra = 1


class PhongCachInline(admin.TabularInline):
    model = NhiepAnhGia_PhongCach
    extra = 1


class KhuVucInline(admin.TabularInline):
    model = NhiepAnhGia_KhuVuc
    extra = 1


@admin.register(NhiepAnhGia)
class NhiepAnhGiaAdmin(admin.ModelAdmin):
    # Chọn loại hình / phong cách / khu vực ngay trong trang nhiếp ảnh gia.
    inlines = [LoaiHinhInline, PhongCachInline, KhuVucInline]


class HinhAnhInline(admin.TabularInline):
    model = HinhAnhProject
    extra = 1


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    inlines = [HinhAnhInline]