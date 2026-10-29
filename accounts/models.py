# =====================================================================
# accounts/models.py  -  Module 7: Quản lý tài khoản & phân quyền
# Bảng User của FRAMIE. Kế thừa User có sẵn của Django nên đã có sẵn:
# username, password (lưu băm), first_name, last_name, email,
# is_active, is_staff, date_joined, last_login. Ở đây chỉ bổ sung
# những gì Django chưa có (theo feedback 6 của thầy).
# =====================================================================
from django.contrib.auth.models import AbstractUser   # bản mẫu User của Django
from django.core.exceptions import ValidationError    # báo lỗi nhập liệu bằng tiếng Việt
from django.core.validators import RegexValidator     # kiểm tra chuỗi theo mẫu
from django.db import models                          # các kiểu cột dữ liệu

# tên vai trò, tên trạng thái hồ sơ và 4 trạng thái "quên mật khẩu" lấy từ core/constants.py
from core.constants import TrangThaiDatLaiMatKhau, TrangThaiHoSo, VaiTro


class User(AbstractUser):
    # Ghi đè email của Django: bắt buộc nhập, không được trùng (đăng nhập bằng email).
    email = models.EmailField('email', max_length=100, unique=True)

    # Cột Django chưa có: số điện thoại. Bắt buộc, không trùng,
    # đúng 10 chữ số và bắt đầu bằng 0 (Bảng 54 của báo cáo).
    # Dùng chuỗi (CharField) vì kiểu số sẽ làm mất số 0 đầu.
    # Dùng [0-9] và \Z (không dùng \d và $): \d nhận cả chữ số của chữ viết khác,
    # còn $ cho phép ký tự xuống dòng ở cuối.
    so_dien_thoai = models.CharField(
        'số điện thoại',
        max_length=10,
        unique=True,
        validators=[RegexValidator(r'^0[0-9]{9}\Z',
                                   'Số điện thoại gồm 10 chữ số và bắt đầu bằng 0.')],
    )

    # Trạng thái hồ sơ Nhiếp ảnh gia: Chờ duyệt / Đã duyệt / Đã từ chối.
    # Chỉ nhiếp ảnh gia mới có giá trị; Khách hàng và Quản trị viên để trống (NULL).
    # Form đăng ký Nhiếp ảnh gia (P5) gán 'Chờ duyệt'; duyệt hồ sơ (K7) đổi sang
    # 'Đã duyệt' hoặc 'Đã từ chối'. Vai trò thì dùng Group của Django, không lưu ở đây.
    trang_thai_ho_so = models.CharField(
        'trạng thái hồ sơ',
        max_length=20,
        choices=TrangThaiHoSo.CHOICES,
        null=True,
        blank=True,
    )

    # Các cột bắt buộc khi tạo tài khoản quản trị bằng lệnh createsuperuser
    # (ngoài username và mật khẩu), để admin cũng có email và số điện thoại.
    REQUIRED_FIELDS = ['email', 'so_dien_thoai']

    def clean(self):
        super().clean()
        # Ràng buộc "kiểm tra ở tầng ứng dụng": Khách hàng và Quản trị viên phải để trống
        # trạng thái hồ sơ. Chỉ tra được nhóm khi User đã có pk (đã lưu); với tài khoản
        # vừa tạo thì view đăng ký bảo đảm (Khách hàng để trống, Nhiếp ảnh gia là 'Chờ duyệt').
        if self.trang_thai_ho_so and self.pk:
            if self.groups.filter(name__in=[VaiTro.KHACH_HANG, VaiTro.QUAN_TRI_VIEN]).exists():
                raise ValidationError(
                    {'trang_thai_ho_so': 'Chỉ Nhiếp ảnh gia mới có trạng thái hồ sơ.'})


class YeuCauDatLaiMatKhau(models.Model):  # bảng YEUCAUDATLAIMATKHAU: mỗi dòng là một lượt bấm "Quên mật khẩu"
    MaYeuCauDatLai = models.AutoField(primary_key=True)  # khóa chính INTEGER tự tăng: 1, 2, 3...
    MaTaiKhoan = models.ForeignKey(  # khóa ngoại: lượt yêu cầu này của User nào
        User,  # trỏ tới class User đã viết ở phía trên cùng file này
        on_delete=models.PROTECT,  # tương ứng ON DELETE RESTRICT: không cho xóa User nếu còn lượt yêu cầu (giữ lịch sử)
        db_column='MaTaiKhoan',  # tên cột trong DB đúng như Dictionary (nếu bỏ dòng này Django tự đặt MaTaiKhoan_id)
        related_name='yeu_cau_dat_lai_mat_khau',  # tên để từ một User gọi ngược ra các yêu cầu của họ
    )  # hết khai báo khóa ngoại MaTaiKhoan
    OtpXacThuc = models.CharField(  # mã xác thực gửi tới email
        max_length=6,  # VARCHAR(6): tối đa 6 ký tự
        validators=[RegexValidator(r'^[0-9]{6}\Z', 'Mã xác thực gồm đúng 6 chữ số.')],  # đúng 6 chữ số 0-9 (kiểm tra khi qua form)
    )  # hết khai báo OtpXacThuc
    ThoiDiemGui = models.DateTimeField(auto_now_add=True)  # giờ gửi mã, Django tự điền lúc tạo (như DEFAULT CURRENT_TIMESTAMP)
    ThoiDiemHetHan = models.DateTimeField()  # giờ mã hết hạn; view quên mật khẩu (P6) sẽ gán = giờ gửi + 10 phút
    ThoiDiemXacThuc = models.DateTimeField(null=True, blank=True)  # giờ người dùng nhập đúng mã; NULL nghĩa là chưa xác thực
    TrangThai = models.CharField(  # trạng thái của lượt yêu cầu
        max_length=20,  # VARCHAR(20)
        choices=TrangThaiDatLaiMatKhau.CHOICES,  # chỉ nhận 4 giá trị khai báo trong core/constants.py
        default=TrangThaiDatLaiMatKhau.CHO_XAC_THUC,  # mặc định 'Chờ xác thực' khi vừa tạo
    )  # hết khai báo TrangThai

    class Meta:  # khai báo tên bảng và các ràng buộc cho bảng
        db_table = 'YEUCAUDATLAIMATKHAU'  # tên bảng đúng như Data Dictionary (nếu bỏ dòng này Django tự đặt accounts_yeucaudatlaimatkhau)
        verbose_name = 'yêu cầu đặt lại mật khẩu'
        verbose_name_plural = 'yêu cầu đặt lại mật khẩu'
        constraints = [  # danh sách ràng buộc CHECK ở mức cơ sở dữ liệu
            models.CheckConstraint(  # ràng buộc 1: mã phải hết hạn SAU lúc gửi
                condition=models.Q(ThoiDiemHetHan__gt=models.F('ThoiDiemGui')),  # ThoiDiemHetHan > ThoiDiemGui
                name='otp_het_han_sau_gio_gui',  # tên ràng buộc (để hiện trong thông báo lỗi)
            ),  # hết ràng buộc 1
            models.CheckConstraint(  # ràng buộc 2: giờ xác thực (nếu có) phải nằm trong khoảng hiệu lực
                condition=(  # điều kiện gồm hai trường hợp nối bằng dấu |
                    models.Q(ThoiDiemXacThuc__isnull=True)  # trường hợp 1: chưa xác thực (NULL) thì hợp lệ
                    | (models.Q(ThoiDiemXacThuc__gte=models.F('ThoiDiemGui'))  # trường hợp 2: đã xác thực thì phải >= giờ gửi
                       & models.Q(ThoiDiemXacThuc__lte=models.F('ThoiDiemHetHan')))  # và phải <= giờ hết hạn
                ),  # hết điều kiện
                name='otp_xac_thuc_trong_han',  # tên ràng buộc
            ),  # hết ràng buộc 2
            models.CheckConstraint(  # ràng buộc 3: TrangThai chỉ nhận 4 giá trị của Quy ước trạng thái (như CHECK trong Dictionary)
                condition=models.Q(TrangThai__in=[c[0] for c in TrangThaiDatLaiMatKhau.CHOICES]),  # TrangThai IN (4 giá trị)
                name='otp_trang_thai_hop_le',  # tên ràng buộc
            ),  # hết ràng buộc 3
        ]  # hết danh sách ràng buộc

    def __str__(self):  # chữ hiển thị của một dòng dữ liệu trong trang admin
        return f'{self.MaTaiKhoan} - {self.TrangThai}'  # ví dụ: "phanh - Chờ xác thực"