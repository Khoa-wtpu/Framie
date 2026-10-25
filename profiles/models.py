# =====================================================================
# profiles/models.py  -  Module 1: Quản lý hồ sơ & Portfolio (Khoa)
# Bảng: LOAIHINHCHUP, PHONGCACH, KHUVUC, NHIEPANHGIA, 3 bảng nối nhiều-nhiều,
#       PROJECT, HINHANHPROJECT, GOIDICHVU, DUYETHOSO.
# (LICHKHADUNG nằm ở schedule/models.py)
#
# Quy ước trong file này (bám đúng Data Dictionary v2):
#   - Tên bảng (db_table) và tên cột/field giống hệt Data Dictionary.
#   - Bảng đơn: khóa chính là MaXxx (ví dụ MaProject). Vì vậy KHÔNG có .id,
#     các module khác dùng .pk (hoặc .MaProject).
#   - Bảng nối (thực thể kết hợp): khóa chính là id; hai mã còn lại là FK và
#     được ràng buộc không trùng cặp (UniqueConstraint).
#   - Chữ trạng thái lấy từ core/constants.py, không gõ trực tiếp.
# =====================================================================
from django.conf import settings                      # để trỏ tới User (AUTH_USER_MODEL)
from django.core.exceptions import ValidationError    # báo lỗi nhập liệu bằng tiếng Việt
from django.core.validators import FileExtensionValidator, RegexValidator
from django.db import models, transaction
from django.db.models import F, Q                     # Q: điều kiện cho CHECK; F: so sánh 2 cột
from django.utils import timezone

from core.constants import KetQuaDuyetHoSo, TrangThaiGoi, TrangThaiHoSo, VaiTro
# Đặt bí danh vì GoiDichVu có field cũng tên LoaiHauKy (tránh nhầm hai thứ cùng tên).
from core.constants import LoaiHauKy as HangSoLoaiHauKy

# Chỉ nhận JPG, JPEG, PNG (Quy ước code: file tải lên, NFR-08).
# ImageField lưu ĐƯỜNG DẪN trong cột VARCHAR(255), giống Data Dictionary.
CHI_NHAN_ANH = FileExtensionValidator(['jpg', 'jpeg', 'png'],
                                      'Chỉ nhận ảnh JPG, JPEG hoặc PNG.')


def _user_thuoc_nhom(user, ten_nhom):
    # Kiểm tra User có thuộc Group (vai trò) này không. Dùng cho các ràng buộc
    # "kiểm tra ở tầng ứng dụng" trong Data Dictionary.
    return user.groups.filter(name=ten_nhom).exists()


# ---------------------------------------------------------------------
# 3 bảng danh mục dùng chung (tìm kiếm, lọc)
# ---------------------------------------------------------------------
class LoaiHinhChup(models.Model):
    MaLoaiHinh = models.AutoField(primary_key=True)
    TenLoaiHinh = models.CharField('Tên loại hình chụp', max_length=100, unique=True)

    class Meta:
        db_table = 'LOAIHINHCHUP'
        verbose_name = 'Loại hình chụp'
        verbose_name_plural = 'Loại hình chụp'
        ordering = ['TenLoaiHinh']

    def __str__(self):
        return self.TenLoaiHinh


class PhongCach(models.Model):
    MaPhongCach = models.AutoField(primary_key=True)
    TenPhongCach = models.CharField('Tên phong cách', max_length=100, unique=True)

    class Meta:
        db_table = 'PHONGCACH'
        verbose_name = 'phong cách'
        verbose_name_plural = 'phong cách'
        ordering = ['TenPhongCach']

    def __str__(self):
        return self.TenPhongCach


class KhuVuc(models.Model):
    MaKhuVuc = models.AutoField(primary_key=True)
    TenKhuVuc = models.CharField('tên khu vực', max_length=100, unique=True)

    class Meta:
        db_table = 'KHUVUC'
        verbose_name = 'khu vực'
        verbose_name_plural = 'khu vực'
        ordering = ['TenKhuVuc']

    def __str__(self):
        return self.TenKhuVuc


# ---------------------------------------------------------------------
# NHIEPANHGIA: hồ sơ chuyên môn, nối 1-1 với User (nhóm Nhiếp ảnh gia).
# Họ tên, email, số điện thoại, trạng thái hồ sơ nằm ở User (accounts).
# ---------------------------------------------------------------------
class NhiepAnhGia(models.Model):
    MaNhiepAnhGia = models.AutoField(primary_key=True)
    # 1-1 với User. PROTECT = không cho xóa User khi còn hồ sơ (ON DELETE RESTRICT).
    # Cột trong DB tên MaTaiKhoan (Data Dictionary), FK tới User(id).
    MaTaiKhoan = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        db_column='MaTaiKhoan', related_name='ho_so_nhiep_anh_gia',
        verbose_name='tài khoản')
    AnhDaiDien = models.ImageField('ảnh đại diện', upload_to='avatars/',
                                   max_length=255, validators=[CHI_NHAN_ANH])
    GioiThieu = models.TextField('giới thiệu')
    NganHang = models.CharField('ngân hàng', max_length=100)
    # Chỉ chữ số, tối đa 20. Dùng CharField vì số tài khoản có thể bắt đầu bằng 0.
    # Kiểm tra bằng validator (chạy ở form/admin, báo lỗi tiếng Việt).
    # Dùng [0-9] và \Z (không dùng \d và $): \d nhận cả chữ số của chữ viết khác,
    # còn $ cho phép ký tự xuống dòng ở cuối; Data Dictionary chỉ nhận đúng 0-9.
    SoTaiKhoan = models.CharField(
        'số tài khoản', max_length=20,
        validators=[RegexValidator(r'^[0-9]{1,20}\Z',
                                   'Số tài khoản chỉ gồm chữ số, tối đa 20 chữ số.')])
    ChuTaiKhoan = models.CharField('chủ tài khoản', max_length=100)
    AnhMaQR = models.ImageField('ảnh mã QR', upload_to='qr/', max_length=255,
                                validators=[CHI_NHAN_ANH])

    # 3 quan hệ nhiều-nhiều, qua các bảng nối khai báo ở cuối file.
    # (Không phải cột trong DB; chỉ để truy vấn tiện: nag.loai_hinh_chup.all())
    loai_hinh_chup = models.ManyToManyField(
        LoaiHinhChup, through='NhiepAnhGia_LoaiHinhChup',
        related_name='nhiep_anh_gia', verbose_name='loại hình chụp')
    phong_cach = models.ManyToManyField(
        PhongCach, through='NhiepAnhGia_PhongCach',
        related_name='nhiep_anh_gia', verbose_name='phong cách')
    khu_vuc = models.ManyToManyField(
        KhuVuc, through='NhiepAnhGia_KhuVuc',
        related_name='nhiep_anh_gia', verbose_name='khu vực')

    class Meta:
        db_table = 'NHIEPANHGIA'
        verbose_name = 'nhiếp ảnh gia'
        verbose_name_plural = 'nhiếp ảnh gia'

    def clean(self):
        super().clean()
        # Ràng buộc "kiểm tra ở tầng ứng dụng": User phải thuộc nhóm Nhiếp ảnh gia.
        if self.MaTaiKhoan_id and not _user_thuoc_nhom(self.MaTaiKhoan, VaiTro.NHIEP_ANH_GIA):
            raise ValidationError({'MaTaiKhoan': 'Tài khoản này không thuộc nhóm Nhiếp ảnh gia.'})

    def __str__(self):
        ten = self.MaTaiKhoan.get_full_name() or self.MaTaiKhoan.username
        return f'{ten} (#{self.pk})'


# ---------------------------------------------------------------------
# PROJECT và HINHANHPROJECT: Portfolio
# ---------------------------------------------------------------------
class Project(models.Model):
    MaProject = models.AutoField(primary_key=True)
    MaNhiepAnhGia = models.ForeignKey(NhiepAnhGia, on_delete=models.PROTECT,
                                      db_column='MaNhiepAnhGia', related_name='projects',
                                      verbose_name='nhiếp ảnh gia')
    MaLoaiHinh = models.ForeignKey(LoaiHinhChup, on_delete=models.PROTECT,
                                   db_column='MaLoaiHinh', related_name='projects',
                                   verbose_name='loại hình chụp')
    TenProject = models.CharField('tên project', max_length=150)
    Concept = models.TextField('concept', null=True, blank=True)
    AnhBia = models.ImageField('ảnh bìa', upload_to='portfolio/', max_length=255,
                               validators=[CHI_NHAN_ANH])
    NgayChup = models.DateField('ngày chụp', null=True, blank=True)
    # DEFAULT CURRENT_TIMESTAMP: Django tự gán lúc tạo.
    NgayTao = models.DateTimeField('ngày tạo', auto_now_add=True)
    # Để trống cho tới lần sửa đầu tiên (xem save() bên dưới).
    NgayCapNhat = models.DateTimeField('ngày cập nhật', null=True, blank=True, editable=False)

    class Meta:
        db_table = 'PROJECT'
        verbose_name = 'project'
        verbose_name_plural = 'project'
        ordering = ['-NgayTao']
        constraints = [
            # NgayCapNhat có thì phải >= NgayTao.
            models.CheckConstraint(
                condition=Q(NgayCapNhat__isnull=True) | Q(NgayCapNhat__gte=F('NgayTao')),
                name='project_ngay_cap_nhat_sau_ngay_tao'),
        ]

    def save(self, *args, **kwargs):
        # Từ lần lưu thứ hai trở đi mới ghi NgayCapNhat (lần tạo đầu giữ NULL).
        if not self._state.adding:
            self.NgayCapNhat = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.TenProject


class HinhAnhProject(models.Model):
    MaHinhAnh = models.AutoField(primary_key=True)
    # Xóa project thì xóa luôn ảnh bên trong (ON DELETE CASCADE).
    MaProject = models.ForeignKey(Project, on_delete=models.CASCADE,
                                  db_column='MaProject', related_name='hinh_anh',
                                  verbose_name='project')
    DuongDanHinhAnh = models.ImageField('hình ảnh', upload_to='portfolio/', max_length=255,
                                        validators=[CHI_NHAN_ANH])
    ThuTu = models.PositiveIntegerField('thứ tự hiển thị')
    NgayTaiLen = models.DateTimeField('ngày tải lên', auto_now_add=True)

    class Meta:
        db_table = 'HINHANHPROJECT'
        verbose_name = 'hình ảnh project'
        verbose_name_plural = 'hình ảnh project'
        ordering = ['MaProject_id', 'ThuTu']
        constraints = [
            models.CheckConstraint(condition=Q(ThuTu__gte=1),
                                   name='hinhanh_thu_tu_tu_1',
                                   violation_error_message='Thứ tự hiển thị phải từ 1 trở lên.'),
            # Thứ tự ảnh trong cùng một project không được trùng.
            models.UniqueConstraint(fields=['MaProject', 'ThuTu'],
                                    name='hinhanh_project_thu_tu_duy_nhat',
                                    violation_error_message='Thứ tự này đã có trong project.'),
        ]

    def __str__(self):
        return f'{self.MaProject} - ảnh {self.ThuTu}'


# ---------------------------------------------------------------------
# GOIDICHVU
# ---------------------------------------------------------------------
class GoiDichVu(models.Model):
    MaGoi = models.AutoField(primary_key=True)
    MaNhiepAnhGia = models.ForeignKey(NhiepAnhGia, on_delete=models.PROTECT,
                                      db_column='MaNhiepAnhGia', related_name='goi_dich_vu',
                                      verbose_name='nhiếp ảnh gia')
    MaLoaiHinh = models.ForeignKey(LoaiHinhChup, on_delete=models.PROTECT,
                                   db_column='MaLoaiHinh', related_name='goi_dich_vu',
                                   verbose_name='loại hình chụp')
    TenGoi = models.CharField('tên gói', max_length=150)
    MoTa = models.TextField('mô tả', null=True, blank=True)
    # Tiền VNĐ, không có phần lẻ: DECIMAL(12,0).
    Gia = models.DecimalField('giá (VNĐ)', max_digits=12, decimal_places=0)
    ThoiLuongChup = models.PositiveIntegerField('thời lượng chụp (phút)')
    LoaiHauKy = models.CharField('hình thức hậu kỳ', max_length=30, choices=HangSoLoaiHauKy.CHOICES)
    SoAnhHauKyToiDa = models.PositiveIntegerField(
        'số ảnh hậu kỳ tối đa', null=True, blank=True,
        help_text='Chỉ nhập khi chọn "Giới hạn số lượng ảnh"; để trống nếu "Hậu kỳ toàn bộ ảnh".')
    TrangThai = models.CharField('trạng thái', max_length=30, choices=TrangThaiGoi.CHOICES,
                                 default=TrangThaiGoi.DANG_AP_DUNG)

    class Meta:
        db_table = 'GOIDICHVU'
        verbose_name = 'gói dịch vụ'
        verbose_name_plural = 'gói dịch vụ'
        constraints = [
            models.CheckConstraint(condition=Q(Gia__gt=0), name='goi_gia_lon_hon_0',
                                   violation_error_message='Giá gói phải lớn hơn 0.'),
            models.CheckConstraint(condition=Q(ThoiLuongChup__gt=0),
                                   name='goi_thoi_luong_lon_hon_0',
                                   violation_error_message='Thời lượng chụp phải lớn hơn 0.'),
            # Gói giới hạn: bắt buộc có số ảnh tối đa > 0.
            # Gói hậu kỳ toàn bộ: số ảnh tối đa phải để trống.
            models.CheckConstraint(
                condition=(
                    Q(LoaiHauKy=HangSoLoaiHauKy.GIOI_HAN, SoAnhHauKyToiDa__gt=0)
                    | Q(LoaiHauKy=HangSoLoaiHauKy.TOAN_BO, SoAnhHauKyToiDa__isnull=True)),
                name='goi_so_anh_theo_loai_hau_ky',
                violation_error_message=(
                    'Gói "Giới hạn số lượng ảnh" phải nhập số ảnh tối đa lớn hơn 0; '
                    'gói "Hậu kỳ toàn bộ ảnh" thì để trống số ảnh tối đa.')),
            # TrangThai chỉ nhận 3 giá trị của Quy ước trạng thái (CHECK trong Data Dictionary).
            models.CheckConstraint(
                condition=Q(TrangThai__in=[c[0] for c in TrangThaiGoi.CHOICES]),
                name='goi_trang_thai_hop_le',
                violation_error_message='Trạng thái gói không hợp lệ.'),
        ]

    def __str__(self):
        return self.TenGoi


# ---------------------------------------------------------------------
# DUYETHOSO: mỗi lượt hồ sơ nộp để Quản trị viên xem xét
# ---------------------------------------------------------------------
class DuyetHoSo(models.Model):
    MaDuyetHoSo = models.AutoField(primary_key=True)
    MaNhiepAnhGia = models.ForeignKey(NhiepAnhGia, on_delete=models.PROTECT,
                                      db_column='MaNhiepAnhGia', related_name='luot_duyet',
                                      verbose_name='nhiếp ảnh gia')
    # NULL cho tới khi có Quản trị viên xử lý lượt này. FK tới User(id).
    MaQuanTriVien = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        db_column='MaQuanTriVien', related_name='luot_duyet_ho_so',
        verbose_name='quản trị viên')
    LanNop = models.PositiveIntegerField('lần nộp', default=1)
    ThoiDiemNop = models.DateTimeField('thời điểm nộp', default=timezone.now)
    ThoiDiemDuyet = models.DateTimeField('thời điểm duyệt', null=True, blank=True)
    # NULL = đang chờ duyệt.
    KetQua = models.CharField('kết quả', max_length=20, null=True, blank=True,
                              choices=KetQuaDuyetHoSo.CHOICES)
    NoiDungPhanHoi = models.CharField('nội dung phản hồi', max_length=1000,
                                      null=True, blank=True)

    class Meta:
        db_table = 'DUYETHOSO'
        verbose_name = 'Lượt duyệt hồ sơ'
        verbose_name_plural = 'Lượt duyệt hồ sơ'
        ordering = ['-ThoiDiemNop']
        constraints = [
            models.UniqueConstraint(fields=['MaNhiepAnhGia', 'LanNop'],
                                    name='duyet_nag_lan_nop_duy_nhat'),
            models.CheckConstraint(condition=Q(LanNop__gte=1), name='duyet_lan_nop_tu_1'),
            # Có kết quả thì phải có Quản trị viên và ngược lại.
            models.CheckConstraint(
                condition=(Q(KetQua__isnull=True, MaQuanTriVien__isnull=True)
                           | Q(KetQua__isnull=False, MaQuanTriVien__isnull=False)),
                name='duyet_ket_qua_va_quan_tri_vien'),
            # Có kết quả thì phải có thời điểm duyệt (>= thời điểm nộp) và ngược lại.
            models.CheckConstraint(
                condition=(Q(KetQua__isnull=True, ThoiDiemDuyet__isnull=True)
                           | Q(KetQua__isnull=False, ThoiDiemDuyet__isnull=False,
                               ThoiDiemDuyet__gte=F('ThoiDiemNop'))),
                name='duyet_ket_qua_va_thoi_diem_duyet'),
            models.CheckConstraint(
                condition=Q(KetQua__isnull=True) | Q(KetQua__in=[c[0] for c in KetQuaDuyetHoSo.CHOICES]),
                name='duyet_ket_qua_hop_le'),
            # Yêu cầu chỉnh sửa hoặc Từ chối thì bắt buộc có nội dung phản hồi.
            # (Kiểm tra "chỉ toàn dấu cách" nằm ở clean(), vì DB Browser không có hàm REGEXP.)
            models.CheckConstraint(
                condition=(Q(KetQua__isnull=True) | Q(KetQua=KetQuaDuyetHoSo.DA_DUYET)
                           | (Q(NoiDungPhanHoi__isnull=False) & ~Q(NoiDungPhanHoi=''))),
                name='duyet_phan_hoi_khi_chinh_sua_hoac_tu_choi',
                violation_error_message='Phải nhập nội dung khi yêu cầu chỉnh sửa hoặc từ chối.'),
        ]

    def clean(self):
        super().clean()
        # Ràng buộc "kiểm tra ở tầng ứng dụng": người duyệt phải thuộc nhóm Quản trị viên.
        if self.MaQuanTriVien_id and not _user_thuoc_nhom(self.MaQuanTriVien, VaiTro.QUAN_TRI_VIEN):
            raise ValidationError({'MaQuanTriVien': 'Người duyệt phải thuộc nhóm Quản trị viên.'})
        # Yêu cầu chỉnh sửa / Từ chối: nội dung phản hồi không được chỉ gồm dấu cách.
        if (self.KetQua in (KetQuaDuyetHoSo.YEU_CAU_CHINH_SUA, KetQuaDuyetHoSo.DA_TU_CHOI)
                and not (self.NoiDungPhanHoi or '').strip()):
            raise ValidationError({'NoiDungPhanHoi': 'Phải nhập nội dung khi yêu cầu chỉnh sửa hoặc từ chối.'})

    def save(self, *args, **kwargs):
        # Lưu lượt duyệt rồi đồng bộ User.trang_thai_ho_so trong CÙNG một giao dịch,
        # để hai bảng không bao giờ lệch nhau dù lưu từ view hay từ trang quản trị.
        with transaction.atomic():
            super().save(*args, **kwargs)
            self.dong_bo_trang_thai_ho_so()

    def dong_bo_trang_thai_ho_so(self):
        # Chỉ lượt nộp MỚI NHẤT của nhiếp ảnh gia mới quyết định trạng thái hồ sơ
        # (sửa một lượt cũ không được làm đổi trạng thái hiện tại).
        moi_nhat = (DuyetHoSo.objects.filter(MaNhiepAnhGia_id=self.MaNhiepAnhGia_id)
                    .order_by('-LanNop').first())
        if moi_nhat is None or moi_nhat.pk != self.pk:
            return
        # Đã duyệt -> Đã duyệt; Đã từ chối -> Đã từ chối;
        # Yêu cầu chỉnh sửa hoặc chưa có kết quả -> giữ Chờ duyệt.
        if self.KetQua == KetQuaDuyetHoSo.DA_DUYET:
            moi = TrangThaiHoSo.DA_DUYET
        elif self.KetQua == KetQuaDuyetHoSo.DA_TU_CHOI:
            moi = TrangThaiHoSo.DA_TU_CHOI
        else:
            moi = TrangThaiHoSo.CHO_DUYET
        user = self.MaNhiepAnhGia.MaTaiKhoan
        if user.trang_thai_ho_so != moi:
            user.trang_thai_ho_so = moi
            user.save(update_fields=['trang_thai_ho_so'])

    def __str__(self):
        return f'Duyệt hồ sơ #{self.MaNhiepAnhGia_id} - lần {self.LanNop}'


# ---------------------------------------------------------------------
# 3 bảng nối nhiều-nhiều (thực thể kết hợp)
# Khóa chính là id (theo quy ước chung của nhóm, giống User_groups);
# hai mã còn lại là FK và không được trùng cặp.
# Xóa nhiếp ảnh gia -> xóa dòng nối (CASCADE); xóa danh mục đang dùng bị chặn (PROTECT).
# ---------------------------------------------------------------------
class NhiepAnhGia_LoaiHinhChup(models.Model):
    id = models.AutoField(primary_key=True)
    MaNhiepAnhGia = models.ForeignKey(NhiepAnhGia, on_delete=models.CASCADE,
                                      db_column='MaNhiepAnhGia')
    MaLoaiHinh = models.ForeignKey(LoaiHinhChup, on_delete=models.PROTECT,
                                   db_column='MaLoaiHinh')

    class Meta:
        db_table = 'NHIEPANHGIA_LOAIHINHCHUP'
        verbose_name = 'loại hình chụp của nhiếp ảnh gia'
        verbose_name_plural = 'loại hình chụp của nhiếp ảnh gia'
        constraints = [models.UniqueConstraint(fields=['MaNhiepAnhGia', 'MaLoaiHinh'],
                                               name='nag_loaihinh_duy_nhat')]


class NhiepAnhGia_PhongCach(models.Model):
    id = models.AutoField(primary_key=True)
    MaNhiepAnhGia = models.ForeignKey(NhiepAnhGia, on_delete=models.CASCADE,
                                      db_column='MaNhiepAnhGia')
    MaPhongCach = models.ForeignKey(PhongCach, on_delete=models.PROTECT,
                                    db_column='MaPhongCach')

    class Meta:
        db_table = 'NHIEPANHGIA_PHONGCACH'
        verbose_name = 'phong cách của nhiếp ảnh gia'
        verbose_name_plural = 'phong cách của nhiếp ảnh gia'
        constraints = [models.UniqueConstraint(fields=['MaNhiepAnhGia', 'MaPhongCach'],
                                               name='nag_phongcach_duy_nhat')]


class NhiepAnhGia_KhuVuc(models.Model):
    id = models.AutoField(primary_key=True)
    MaNhiepAnhGia = models.ForeignKey(NhiepAnhGia, on_delete=models.CASCADE,
                                      db_column='MaNhiepAnhGia')
    MaKhuVuc = models.ForeignKey(KhuVuc, on_delete=models.PROTECT, db_column='MaKhuVuc')

    class Meta:
        db_table = 'NHIEPANHGIA_KHUVUC'
        verbose_name = 'khu vực của nhiếp ảnh gia'
        verbose_name_plural = 'khu vực của nhiếp ảnh gia'
        constraints = [models.UniqueConstraint(fields=['MaNhiepAnhGia', 'MaKhuVuc'],
                                               name='nag_khuvuc_duy_nhat')]