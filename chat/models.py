from django.conf import settings  # để đọc AUTH_USER_MODEL từ settings.py
from django.core.exceptions import ValidationError  # báo lỗi nhập liệu bằng tiếng Việt
from django.db import models  # các kiểu cột dữ liệu của Django

from core.constants import VaiTro  # tên vai trò (nhóm quyền) từ core/constants.py


class CuocTroChuyen(models.Model):  # bảng CUOCTROCHUYEN: mỗi dòng là một cuộc trò chuyện giữa 1 Khách hàng và 1 Nhiếp ảnh gia
    MaCuocTroChuyen = models.AutoField(primary_key=True)  # khóa chính INTEGER tự tăng
    MaKhachHang = models.ForeignKey(  # khóa ngoại: Khách hàng khởi tạo cuộc trò chuyện
        settings.AUTH_USER_MODEL,  # trỏ tới bảng User
        on_delete=models.PROTECT,  # ON DELETE RESTRICT: không cho xóa User nếu còn cuộc trò chuyện
        db_column='MaKhachHang',  # tên cột đúng như Dictionary
        related_name='cuoc_tro_chuyen_khach',  # từ User gọi ngược ra các cuộc trò chuyện họ khởi tạo
    )  # hết khai báo MaKhachHang
    MaNhiepAnhGia = models.ForeignKey(  # khóa ngoại: Nhiếp ảnh gia tham gia cuộc trò chuyện
        'profiles.NhiepAnhGia',  # trỏ tới model NhiepAnhGia của Khoa (viết dạng chuỗi để tránh import vòng)
        on_delete=models.PROTECT,  # ON DELETE RESTRICT
        db_column='MaNhiepAnhGia',  # tên cột đúng như Dictionary
        related_name='cuoc_tro_chuyen',  # từ NhiepAnhGia gọi ngược ra các cuộc trò chuyện
    )  # hết khai báo MaNhiepAnhGia
    NgayTao = models.DateTimeField(auto_now_add=True)  # thời điểm khởi tạo cuộc trò chuyện, Django tự điền

    class Meta:  # tùy chọn thêm cho bảng
        db_table = 'CUOCTROCHUYEN'  # tên bảng đúng như Data Dictionary (nếu bỏ dòng này Django tự đặt chat_cuoctrochuyen)
        constraints = [  # danh sách ràng buộc
            models.UniqueConstraint(  # mỗi cặp (Khách hàng, Nhiếp ảnh gia) chỉ được có MỘT cuộc trò chuyện
                fields=['MaKhachHang', 'MaNhiepAnhGia'],  # hai cột cùng nhau không được trùng
                name='mot_cuoc_tro_chuyen_moi_cap',  # tên ràng buộc
            ),  # hết ràng buộc UNIQUE
        ]  # hết danh sách ràng buộc

    def clean(self):  # kiểm tra nghiệp vụ khi lưu qua form hoặc trang quản trị
        super().clean()
        # Ràng buộc "kiểm tra ở tầng ứng dụng": người khởi tạo phải thuộc nhóm Khách hàng.
        # View tạo cuộc trò chuyện bằng .save() thẳng thì phải gọi full_clean() trước.
        if self.MaKhachHang_id and not self.MaKhachHang.groups.filter(
                name=VaiTro.KHACH_HANG).exists():
            raise ValidationError(
                {'MaKhachHang': 'Người khởi tạo cuộc trò chuyện phải thuộc nhóm Khách hàng.'})

    def __str__(self):  # chữ hiển thị trong trang admin
        return f'{self.MaKhachHang} <-> {self.MaNhiepAnhGia}'  # ví dụ: "khach01 <-> nag02"


class TinNhan(models.Model):  # bảng TINNHAN: mỗi dòng là một tin nhắn
    MaTinNhan = models.AutoField(primary_key=True)  # khóa chính INTEGER tự tăng
    MaCuocTroChuyen = models.ForeignKey(  # khóa ngoại: tin nhắn thuộc cuộc trò chuyện nào
        CuocTroChuyen,  # trỏ tới class CuocTroChuyen ngay phía trên
        on_delete=models.PROTECT,  # ON DELETE RESTRICT: không xóa cuộc trò chuyện nếu còn tin nhắn
        db_column='MaCuocTroChuyen',  # tên cột đúng như Dictionary
        related_name='tin_nhan',  # từ cuộc trò chuyện gọi ngược: cuoc.tin_nhan.all()
    )  # hết khai báo MaCuocTroChuyen
    MaNguoiGui = models.ForeignKey(  # khóa ngoại: ai gửi tin nhắn này
        settings.AUTH_USER_MODEL,  # trỏ tới bảng User
        on_delete=models.PROTECT,  # ON DELETE RESTRICT
        db_column='MaNguoiGui',  # tên cột đúng như Dictionary
        related_name='tin_nhan_da_gui',  # từ User gọi ngược ra các tin họ đã gửi
    )  # hết khai báo MaNguoiGui
    NoiDung = models.TextField()  # nội dung tin nhắn, TEXT, bắt buộc
    ThoiGianGui = models.DateTimeField(auto_now_add=True)  # thời điểm gửi, Django tự điền

    class Meta:  # tùy chọn thêm cho bảng
        db_table = 'TINNHAN'  # tên bảng đúng như Data Dictionary (nếu bỏ dòng này Django tự đặt chat_tinnhan)
        ordering = ['ThoiGianGui']  # mặc định xếp tin cũ trước, mới sau (đúng thứ tự đọc)

    def clean(self):  # kiểm tra nghiệp vụ khi lưu qua form hoặc trang quản trị
        super().clean()
        # Ràng buộc "kiểm tra ở tầng ứng dụng": người gửi phải là Khách hàng của cuộc trò chuyện
        # hoặc tài khoản của Nhiếp ảnh gia trong cuộc trò chuyện đó (người ngoài không được gửi).
        # View gửi tin cũng phải chặn người ngoài cuộc trò chuyện (không chỉ dựa vào đây).
        if self.MaCuocTroChuyen_id and self.MaNguoiGui_id:
            cuoc = self.MaCuocTroChuyen  # cuộc trò chuyện chứa tin nhắn này
            nguoi_hop_le = {cuoc.MaKhachHang_id, cuoc.MaNhiepAnhGia.MaTaiKhoan_id}  # hai id User được phép gửi
            if self.MaNguoiGui_id not in nguoi_hop_le:
                raise ValidationError(
                    {'MaNguoiGui': 'Người gửi phải là Khách hàng hoặc Nhiếp ảnh gia của cuộc trò chuyện này.'})

    def __str__(self):  # chữ hiển thị trong trang admin
        return f'{self.MaNguoiGui}: {self.NoiDung[:30]}'  # người gửi và 30 ký tự đầu của tin