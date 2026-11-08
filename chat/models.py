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
    NoiDung = models.TextField(blank=True)  # nội dung tin nhắn, TEXT; được rỗng khi tin chỉ có ảnh (bước 5), service vẫn chặn tin rỗng không kèm ảnh
    ThoiGianGui = models.DateTimeField(auto_now_add=True)  # thời điểm gửi, Django tự điền
    DaThuHoi = models.BooleanField(default=False)  # True = người gửi đã thu hồi tin (bước 6); nội dung vẫn giữ trong DB, trình duyệt không nhận
    ThuHoiLuc = models.DateTimeField(null=True, blank=True)  # thời điểm thu hồi, NULL nếu chưa thu hồi
    MaTinTraLoi = models.ForeignKey(  # khóa ngoại tự trỏ: tin này trả lời tin nào (bước 6), NULL nếu không trả lời ai
        'self',  # trỏ lại chính bảng TINNHAN
        null=True, blank=True,  # được để trống
        on_delete=models.SET_NULL,  # tin gốc bị xóa (hiện chưa có chức năng này) thì chỉ mất liên kết trả lời
        db_column='MaTinTraLoi',  # tên cột
        related_name='cac_tin_tra_loi',  # từ tin gốc gọi ngược ra các tin trả lời nó
    )  # hết khai báo MaTinTraLoi

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


class ThamGia(models.Model):  # bảng THAMGIA: trạng thái RIÊNG của từng người trong một cuộc trò chuyện (đã xem tới đâu, ghim, ẩn, xóa phía mình)
    MaThamGia = models.AutoField(primary_key=True)  # khóa chính INTEGER tự tăng
    MaCuocTroChuyen = models.ForeignKey(  # khóa ngoại: cuộc trò chuyện nào
        CuocTroChuyen,  # trỏ tới CUOCTROCHUYEN
        on_delete=models.CASCADE,  # cuộc trò chuyện mất thì trạng thái mất theo (hàng này chỉ là trạng thái, không phải dữ liệu gốc)
        db_column='MaCuocTroChuyen',  # tên cột
        related_name='tham_gia',  # từ cuộc trò chuyện gọi ngược: cuoc.tham_gia.all()
    )  # hết khai báo
    MaNguoiDung = models.ForeignKey(  # khóa ngoại: người dùng này (Khách hàng hoặc tài khoản của Nhiếp ảnh gia)
        settings.AUTH_USER_MODEL,  # trỏ tới bảng User
        on_delete=models.PROTECT,  # ON DELETE RESTRICT
        db_column='MaNguoiDung',  # tên cột
        related_name='tham_gia_chat',  # từ User gọi ngược ra các hàng tham gia
    )  # hết khai báo
    MaTinDaXemCuoi = models.PositiveIntegerField(default=0)  # mã tin lớn nhất người này đã xem (0 = chưa xem tin nào); dùng cho "Đã xem" và số chưa đọc
    DanhDauChuaDoc = models.BooleanField(default=False)  # True = người này tự đánh dấu "chưa đọc" để nhớ trả lời sau
    DaAn = models.BooleanField(default=False)  # True = cuộc trò chuyện bị ẩn khỏi danh sách của người này; có tin mới thì tự hiện lại
    DaGhim = models.BooleanField(default=False)  # True = ghim lên đầu danh sách (bước 4)
    GhimLuc = models.DateTimeField(null=True, blank=True)  # thời điểm ghim, NULL nếu không ghim
    XoaDenMaTin = models.PositiveIntegerField(default=0)  # "Xóa cuộc trò chuyện" phía mình: các tin có mã <= số này không hiện cho người này nữa (người kia vẫn thấy)

    class Meta:  # tùy chọn thêm cho bảng
        db_table = 'THAMGIA'  # tên bảng đúng như Data Dictionary
        constraints = [  # danh sách ràng buộc
            models.UniqueConstraint(  # mỗi người chỉ có MỘT hàng trạng thái trong một cuộc
                fields=['MaCuocTroChuyen', 'MaNguoiDung'],  # hai cột cùng nhau không được trùng
                name='mot_tham_gia_moi_nguoi_moi_cuoc',  # tên ràng buộc
            ),  # hết ràng buộc
        ]  # hết danh sách

    def __str__(self):  # chữ hiển thị trong admin
        return f'{self.MaNguoiDung} trong cuộc {self.MaCuocTroChuyen_id}'  # ví dụ: "khach01 trong cuộc 3"


class DinhKemTinNhan(models.Model):  # bảng DINHKEMTINNHAN: ảnh đính kèm của tin nhắn (bước 5); bản ảnh nhỏ tạo tức thời khi xem nên không có cột riêng
    MaDinhKem = models.AutoField(primary_key=True)  # khóa chính INTEGER tự tăng
    MaTinNhan = models.ForeignKey(  # khóa ngoại: ảnh thuộc tin nhắn nào
        TinNhan,  # trỏ tới TINNHAN
        on_delete=models.PROTECT,  # ON DELETE RESTRICT
        db_column='MaTinNhan',  # tên cột
        related_name='dinh_kem',  # từ tin nhắn gọi ngược: tin.dinh_kem.all()
    )  # hết khai báo
    DuongDanFile = models.CharField(max_length=255)  # đường dẫn file TRONG thư mục private_media (không công khai)
    TenGoc = models.CharField(max_length=255)  # tên file người dùng đã chọn, để hiển thị
    KichThuoc = models.PositiveBigIntegerField()  # dung lượng file, tính bằng byte

    class Meta:  # tùy chọn thêm cho bảng
        db_table = 'DINHKEMTINNHAN'  # tên bảng đúng như Data Dictionary
        ordering = ['MaDinhKem']  # ảnh gửi trước hiện trước

    def __str__(self):  # chữ hiển thị trong admin
        return f'{self.TenGoc} ({self.KichThuoc} byte)'  # tên file và dung lượng