from django.conf import settings  # để đọc AUTH_USER_MODEL (tên model User của project) từ settings.py
from django.db import models  # các kiểu cột dữ liệu của Django
from django.db.models import Q  # Q: điều kiện cho ràng buộc CHECK
from core import constants  # file hằng số trạng thái chung (dùng dạng constants.TenLop để tránh trùng tên với tên cột)


class ThongBao(models.Model):  # bảng THONGBAO: mỗi dòng là một thông báo gửi tới một người
    MaThongBao = models.AutoField(primary_key=True)  # khóa chính INTEGER tự tăng
    MaNguoiNhan = models.ForeignKey(  # khóa ngoại: thông báo này gửi cho User nào
        settings.AUTH_USER_MODEL,  # trỏ tới bảng User của FRAMIE (accounts.User)
        on_delete=models.PROTECT,  # ON DELETE RESTRICT: không cho xóa User nếu còn thông báo
        db_column='MaNguoiNhan',  # tên cột trong DB đúng như Dictionary
        related_name='thong_bao',  # từ một User gọi ngược: user.thong_bao.all()
    )  # hết khai báo MaNguoiNhan
    MaBooking = models.ForeignKey(  # khóa ngoại: thông báo phát sinh từ Booking nào
        'bookings.Booking',  # trỏ tới model Booking của Tuyền (viết dạng chuỗi)
        on_delete=models.PROTECT,  # ON DELETE RESTRICT
        null=True,  # cho phép NULL: thông báo không gắn với Booking thì để trống (đúng Dictionary)
        blank=True,  # cho phép để trống khi nhập ở form/admin
        db_column='MaBooking',  # tên cột đúng như Dictionary
        related_name='thong_bao',  # từ Booking gọi ngược ra các thông báo của nó
    )  # hết khai báo MaBooking
    TieuDe = models.CharField(max_length=255)  # tiêu đề thông báo, VARCHAR(255), bắt buộc
    NoiDung = models.TextField()  # nội dung chi tiết, TEXT, bắt buộc
    NgayTao = models.DateTimeField(auto_now_add=True)  # thời điểm tạo, Django tự điền
    TrangThaiDoc = models.CharField(  # đã đọc hay chưa đọc
        max_length=10,  # VARCHAR(10)
        choices=constants.TrangThaiDoc.CHOICES,  # chỉ nhận 'Chưa đọc' hoặc 'Đã đọc'
        default=constants.TrangThaiDoc.CHUA_DOC,  # mặc định 'Chưa đọc' khi mới tạo
    )  # hết khai báo TrangThaiDoc
    DanhDauSao = models.CharField(  # người dùng có đánh dấu sao thông báo hay không
        max_length=20,  # VARCHAR(20)
        choices=constants.DanhDauSao.CHOICES,  # chỉ nhận 'Đã đánh dấu sao' hoặc 'Chưa đánh dấu sao'
        default=constants.DanhDauSao.CHUA_DANH_DAU,  # mặc định chưa đánh dấu
    )  # hết khai báo DanhDauSao
    TrangThaiGuiEmail = models.CharField(  # kết quả gửi email kèm theo thông báo
        max_length=20,  # VARCHAR(20)
        choices=constants.TrangThaiGuiEmail.CHOICES,  # chỉ nhận 'Gửi thành công' hoặc 'Gửi thất bại'
        null=True,  # cho phép NULL ở cơ sở dữ liệu: thông báo không gửi email thì để trống
        blank=True,  # cho phép để trống khi nhập ở form/admin
    )  # hết khai báo TrangThaiGuiEmail

    class Meta:  # tùy chọn thêm cho bảng
        db_table = 'THONGBAO'  # tên bảng đúng như Data Dictionary (nếu bỏ dòng này Django tự đặt notifications_thongbao)
        verbose_name = 'thông báo'
        verbose_name_plural = 'thông báo'
        ordering = ['-NgayTao']  # mặc định xếp thông báo mới nhất lên đầu (dấu - là giảm dần)
        constraints = [  # CHECK ở mức cơ sở dữ liệu, giống Data Dictionary
            models.CheckConstraint(  # TrangThaiDoc chỉ nhận 2 giá trị
                condition=Q(TrangThaiDoc__in=[c[0] for c in constants.TrangThaiDoc.CHOICES]),
                name='thongbao_trang_thai_doc_hop_le',  # tên ràng buộc
            ),  # hết ràng buộc TrangThaiDoc
            models.CheckConstraint(  # DanhDauSao chỉ nhận 2 giá trị
                condition=Q(DanhDauSao__in=[c[0] for c in constants.DanhDauSao.CHOICES]),
                name='thongbao_danh_dau_sao_hop_le',  # tên ràng buộc
            ),  # hết ràng buộc DanhDauSao
            models.CheckConstraint(  # TrangThaiGuiEmail để trống (NULL) hoặc một trong 2 giá trị
                condition=(Q(TrangThaiGuiEmail__isnull=True)
                           | Q(TrangThaiGuiEmail__in=[c[0] for c in constants.TrangThaiGuiEmail.CHOICES])),
                name='thongbao_trang_thai_gui_email_hop_le',  # tên ràng buộc
            ),  # hết ràng buộc TrangThaiGuiEmail
        ]  # hết danh sách ràng buộc

    def __str__(self):  # chữ hiển thị của một dòng trong trang admin
        return f'{self.TieuDe} -> {self.MaNguoiNhan}'  # ví dụ: "Booking mới -> khach01"