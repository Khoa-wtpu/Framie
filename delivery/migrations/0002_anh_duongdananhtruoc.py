# Migration tay cho E2: thêm cột ANH.DuongDanAnhTruoc (cho phép NULL) phục vụ Slider so sánh ảnh trước/sau.
# Sau khi lấy code về, chạy: python manage.py makemigrations --check  (phải báo "No changes detected")

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('delivery', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='anh',
            name='DuongDanAnhTruoc',
            field=models.CharField(blank=True, max_length=500, null=True, verbose_name='đường dẫn ảnh bản trước'),
        ),
    ]
