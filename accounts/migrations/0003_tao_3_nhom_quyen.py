from django.db import migrations  # công cụ viết migration của Django
from core.constants import VaiTro  # lấy tên 3 vai trò từ core/constants.py


def tao_nhom(apps, schema_editor):  # hàm chạy khi migrate: tạo 3 nhóm quyền
    Group = apps.get_model('auth', 'Group')  # lấy bảng Group có sẵn của Django
    for ten in (VaiTro.KHACH_HANG, VaiTro.NHIEP_ANH_GIA, VaiTro.QUAN_TRI_VIEN):  # lặp qua 3 tên vai trò
        Group.objects.get_or_create(name=ten)  # tạo nhóm nếu chưa có (chạy lại không bị trùng)


class Migration(migrations.Migration):  # khai báo một migration

    dependencies = [  # migration này phải chạy SAU migration nào
        ('accounts', '0002_alter_user_so_dien_thoai_yeucaudatlaimatkhau'),  # chạy sau 0002 (bảng yêu cầu đặt lại mật khẩu)
    ]  # hết danh sách phụ thuộc

    operations = [migrations.RunPython(tao_nhom, migrations.RunPython.noop)]  # chạy tao_nhom khi migrate; noop = không làm gì khi lùi migration
