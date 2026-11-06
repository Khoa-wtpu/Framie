# Generated for FRAMIE: chuẩn hóa nhãn trạng thái thanh toán theo Data Dictionary.
from django.db import migrations, models
from django.db.models import Q


def chuan_hoa_nhan_trang_thai(apps, schema_editor):
    ThanhToan = apps.get_model('payments', 'ThanhToan')
    ThanhToan.objects.filter(
        TrangThai='Chờ xác nhận thanh toán cọc (40%)'
    ).update(TrangThai='Chờ xác nhận thanh toán cọc')
    ThanhToan.objects.filter(
        TrangThai='Chờ xác nhận thanh toán (60%)'
    ).update(TrangThai='Chờ xác nhận thanh toán')


def khoi_phuc_nhan_cu(apps, schema_editor):
    ThanhToan = apps.get_model('payments', 'ThanhToan')
    ThanhToan.objects.filter(
        TrangThai='Chờ xác nhận thanh toán cọc'
    ).update(TrangThai='Chờ xác nhận thanh toán cọc (40%)')
    ThanhToan.objects.filter(
        TrangThai='Chờ xác nhận thanh toán'
    ).update(TrangThai='Chờ xác nhận thanh toán (60%)')


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0001_initial'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='thanhtoan',
            name='ck_thanhtoan_trangthai_theo_loai',
        ),
        migrations.RunPython(chuan_hoa_nhan_trang_thai, khoi_phuc_nhan_cu),
        migrations.AlterField(
            model_name='thanhtoan',
            name='TrangThai',
            field=models.CharField(
                choices=[
                    ('Chờ xác nhận thanh toán cọc', 'Chờ xác nhận thanh toán cọc'),
                    ('Đã đặt cọc', 'Đã đặt cọc'),
                    ('Chờ xác nhận thanh toán', 'Chờ xác nhận thanh toán'),
                    ('Quá hạn thanh toán', 'Quá hạn thanh toán'),
                    ('Đã thanh toán', 'Đã thanh toán'),
                ],
                max_length=50,
                verbose_name='trạng thái',
            ),
        ),
        migrations.AddConstraint(
            model_name='thanhtoan',
            constraint=models.CheckConstraint(
                condition=(
                    Q(LoaiThanhToan='Tiền cọc', TrangThai__in=[
                        'Chờ xác nhận thanh toán cọc', 'Đã đặt cọc'
                    ])
                    | Q(LoaiThanhToan='Phần còn lại', TrangThai__in=[
                        'Chờ xác nhận thanh toán', 'Quá hạn thanh toán', 'Đã thanh toán'
                    ])
                ),
                name='ck_thanhtoan_trangthai_theo_loai',
            ),
        ),
    ]
