# =====================================================================
# bookings/gui_booking.py  -  UC4.2 Gửi yêu cầu Booking (Tuyền)
#
# Yêu cầu: Khách hàng (đã giữ slot ở UC4.1) điền gói dịch vụ (chỉ gói "Đang áp dụng", nhóm theo loại hình của gói),
# ngày giờ chụp nằm trong khung giờ đã giữ và gói phải vừa khung giờ đó (giờ chụp + thời lượng gói <= giờ kết thúc slot),
# địa điểm, số người, concept, yêu cầu riêng. Không có ô "Loại hình" riêng: loại hình là của gói (BOOKING không có cột này).
#   - Địa điểm : CHỌN 1 khu vực (bắt buộc, trong các KhuVuc Nhiếp ảnh gia đã chọn ở hồ sơ) + ô "Địa chỉ cụ thể" (không bắt buộc).
#   - Concept  : CHỌN 1 phong cách (bắt buộc, trong các PhongCach Nhiếp ảnh gia đã chọn ở hồ sơ) + ô "Mô tả concept" (không bắt buộc).
#   BOOKING vẫn chỉ có 2 cột chữ DiaDiem / Concept (không đổi CSDL) nên khi lưu ta GHÉP chữ:
#       DiaDiem = "<Khu vực>"  hoặc  "<Khu vực> - <Địa chỉ cụ thể>"
#       Concept = "<Phong cách>" hoặc "<Phong cách> - <Mô tả concept>"
#   - Quá 5 phút        -> "Slot đã hết thời gian giữ chỗ, vui lòng chọn lại" (kết thúc UC, làm lại UC4.1).
#   - Thông tin hợp lệ  -> tạo Booking "Chờ xác nhận", TongGiaTri = giá gói,
#                          lượt giữ chỗ -> "Đã hoàn tất Booking", thông báo cho Nhiếp ảnh gia (web + Email)
#                          và thông báo xác nhận đã gửi cho Khách hàng (web).
#
# File gồm 4 phần (giống bookings/giu_cho.py của UC4.1):
#   PHẦN 1. Import, hằng số, lỗi nghiệp vụ
#   PHẦN 2. Form nhập thông tin buổi chụp (kiểm tra bước 4 / luồng thay thế 1a)
#   PHẦN 3. Hàm nghiệp vụ (service):
#           gui_yeu_cau_booking(...)   -> bước 4-8 của Basic Flow (+ ngoại lệ 4a)
#   PHẦN 4. View và urlpatterns (nối vào config/urls.py bằng include('bookings.gui_booking'))
#
# Quy tắc nhóm:
#   - Slot KHÔNG bị đổi ở đây: sau khi gửi Booking, slot vẫn "Đang giữ chỗ" cho tới khi Nhiếp ảnh gia
#     xử lý (T6 / N3 sẽ gọi chuyen_trang_thai_booking để đổi slot). Đúng chú thích TrangThaiSlot.DANG_GIU.
#   - Booking mới tạo ra KHÔNG đi qua chuyen_trang_thai_booking (hàm đó chỉ đổi trạng thái có sẵn),
#     nên file này tự ghi dòng Lịch sử đầu tiên (trạng thái cũ = trống, mới = "Chờ xác nhận").
#   - Chữ trạng thái luôn lấy từ core/constants.py.
# =====================================================================

# ---------------------------------------------------------------------
# PHẦN 1: IMPORT, HẰNG SỐ, LỖI NGHIỆP VỤ
# ---------------------------------------------------------------------
import logging                                          # Ghi log khi có lỗi hệ thống
from datetime import datetime                           # Dùng để tạo datetime từ ngày + giờ của slot
from itertools import groupby                           # Nhóm các gói dịch vụ theo loại hình để tạo <optgroup>

from django import forms                                # Tạo form nhập liệu
from django.forms.models import ModelChoiceIterator     # Iterator tùy chỉnh để nhóm option theo loại hình
from django.contrib import messages                     # Hiển thị thông báo (success/error/warning) cho người dùng
from django.core.exceptions import ValidationError      # Lỗi khi kiểm tra dữ liệu form/model
from django.db import DatabaseError, IntegrityError, transaction  # Xử lý lỗi DB + transaction atomic
from django.shortcuts import get_object_or_404, redirect, render  # Lấy object hoặc 404, chuyển hướng, render template
from django.urls import NoReverseMatch, path, reverse   # Tạo URL, bắt lỗi khi URL chưa được định nghĩa
from django.utils import timezone                       # Làm việc với timezone (giờ Việt Nam)
from django.views.decorators.http import require_http_methods  # Chỉ cho phép GET và POST

# Import các hàm/hằng số từ UC4.1 (giữ chỗ) để 2 UC nhất quán với nhau
from bookings.giu_cho import (
    goi_chon_san_hop_le,         # Kiểm tra mã gói chọn sẵn (?goi=) đúng là gói Đang áp dụng của Nhiếp ảnh gia
    TB_HET_HAN,                  # Câu báo hết hạn của UC4.1 (hàm hoan_tat_giu_cho ném ra), UC4.2 đổi sang câu riêng bên dưới
    TB_LOI_HE_THONG,             # Thông báo lỗi hệ thống chung
    GiuChoLoi,                   # Exception nghiệp vụ của UC4.1
    giai_phong_giu_cho_het_han,  # Hàm nhả các lượt giữ chỗ đã quá hạn
    hoan_tat_giu_cho,            # Đánh dấu lượt giữ chỗ thành "Đã hoàn tất Booking"
    khach_hang_required,         # Decorator: chỉ khách hàng mới được vào view này
    so_giay_con_lai,             # Tính số giây còn lại của lượt giữ chỗ (để đếm ngược)
)
from bookings.services import gui_email_sau_commit   # Gửi Email sau khi commit transaction + ghi TrangThaiGuiEmail
from bookings.models import (
    THOI_GIAN_GIU_CHO,           # Thời gian giữ chỗ tối đa (5 phút)
    TRANG_THAI_HET_HIEU_LUC,     # Các trạng thái Booking không còn hiệu lực (đã hủy, từ chối...)
    Booking,                     # Model Booking
    GiuCho,                      # Model lượt giữ chỗ
    LichSuTrangThaiBooking,      # Model lịch sử thay đổi trạng thái Booking
    dinh_dang_thoi_luong,        # Chuyển 180 phút -> '3 giờ'
    gio_chup_muon_nhat,          # Tính giờ bắt đầu muộn nhất để gói vẫn vừa khung giờ
    kiem_tra_goi_vua_slot,       # Quy tắc "gói phải vừa khung giờ", dùng chung với Booking.clean()
    so_phut_slot,                # Tính số phút của 1 slot
)
from core.constants import (
    BenThucHien,                 # Ai thực hiện thay đổi (Khách hàng / Nhiếp ảnh gia / Hệ thống)
    LoaiHauKy,                   # Loại hậu kỳ (toàn bộ / giới hạn số ảnh)
    TrangThaiBooking,            # Các trạng thái của Booking
    TrangThaiGiuCho,             # Các trạng thái của lượt giữ chỗ
    TrangThaiGoi,                # Trạng thái gói dịch vụ (Đang áp dụng / Ngừng...)
    TrangThaiSlot,               # Trạng thái slot lịch (Lịch trống / Đang giữ chỗ...)
)
from notifications.services import gui_thong_bao       # Gửi thông báo web
from profiles.models import GoiDichVu, KhuVuc, PhongCach  # Model gói dịch vụ, khu vực, phong cách
from search.services import nhiep_anh_gia_cong_khai    # Nhiếp ảnh gia công khai = hồ sơ 'Đã duyệt' + tài khoản chưa bị khóa
from schedule.models import LichKhaDung                # Model slot lịch khả dụng

logger = logging.getLogger(__name__)                   # Logger của module này

# Thông báo cho người dùng (đúng chữ trong đặc tả UC4.2).
TB_SLOT_HET_HAN_GIU = 'Slot đã hết thời gian giữ chỗ, vui lòng chọn lại'   # Ngoại lệ 4a
TB_DA_GUI = 'Yêu cầu Booking đã được gửi'                                   # Bước 8
TB_GIU_CHO_DA_DUNG = 'Lượt giữ chỗ này đã được dùng để gửi yêu cầu Booking.'
TB_NAG_KHONG_NHAN_BOOKING = 'Nhiếp ảnh gia này hiện không nhận Booking.'   # Nhiếp ảnh gia bị khóa / hồ sơ không còn công khai
TB_SLOT_DA_CO_BOOKING = 'Slot này đã gắn với một Booking đang có hiệu lực, vui lòng chọn lại.'   # BR4.2-3

# Ánh xạ tên field của Booking (model) -> tên field của form.
# Dùng để đưa lỗi từ Booking.clean() về đúng ô nhập trên form.
TEN_FIELD_FORM = {
    'MaGoi': 'goi',
    'NgayGioChup': 'ngay_gio_chup',
    'DiaDiem': 'khu_vuc',
    'SoNguoi': 'so_nguoi',
    'Concept': 'phong_cach',
    'YeuCauRieng': 'yeu_cau_rieng',
}


class GuiBookingLoi(Exception):
    """Lỗi nghiệp vụ của UC4.2.
    .thong_bao  : câu tiếng Việt hiện cho người dùng.
    .loi_truong : {tên field của Booking: câu lỗi} khi lỗi thuộc về một ô nhập (luồng 1a).
    .het_han    : True khi lượt giữ chỗ đã hết hạn (ngoại lệ 4a) -> kết thúc UC, không cho sửa tiếp."""

    def __init__(self, thong_bao, loi_truong=None, het_han=False):
        super().__init__(thong_bao)          # Gọi constructor của Exception gốc
        self.thong_bao = thong_bao           # Câu thông báo tiếng Việt
        self.loi_truong = loi_truong or {}   # Dictionary lỗi theo từng field (nếu có)
        self.het_han = het_han               # Cờ đánh dấu đã hết hạn giữ chỗ


# ---------------------------------------------------------------------
# PHẦN 2: FORM NHẬP THÔNG TIN BUỔI CHỤP
# ---------------------------------------------------------------------
def _tien(so):
    """Định dạng số tiền: 1500000 -> '1.500.000'"""
    return f'{int(so):,}'.replace(',', '.')


def _hau_ky_hien_thi(goi):
    """Trả về chuỗi mô tả hậu kỳ:
    - Nếu giới hạn số ảnh: 'Hậu kỳ giới hạn 50 ảnh'
    - Ngược lại: lấy đúng chữ của LoaiHauKy"""
    if goi.LoaiHauKy == LoaiHauKy.GIOI_HAN and goi.SoAnhHauKyToiDa:
        return f'Hậu kỳ giới hạn {goi.SoAnhHauKyToiDa} ảnh'
    return goi.LoaiHauKy


def _ly_do_khoa(goi, lich):
    """Trả về lý do khóa gói nếu thời lượng gói dài hơn cả khung giờ đang giữ.
    Ví dụ: 'cần 3 giờ, khung giờ bạn giữ chỉ 2 giờ'
    Nếu gói vừa khung giờ thì trả về chuỗi rỗng."""
    if lich is None or goi.ThoiLuongChup <= so_phut_slot(lich):
        return ''
    return (f'cần {dinh_dang_thoi_luong(goi.ThoiLuongChup)}, '
            f'khung giờ bạn giữ chỉ {dinh_dang_thoi_luong(so_phut_slot(lich))}')


class GoiTheoLoaiHinhIterator(ModelChoiceIterator):
    """Iterator tùy chỉnh: xếp các gói thành từng nhóm (<optgroup>) theo loại hình.
    Queryset phải đã được sắp xếp theo tên loại hình trước khi dùng."""

    def __iter__(self):
        # Nếu form có empty_label thì yield option trống trước
        if self.field.empty_label is not None:
            yield ('', self.field.empty_label)
        # Nhóm các gói theo MaLoaiHinh_id
        for _ma_loai_hinh, ds in groupby(self.queryset, key=lambda g: g.MaLoaiHinh_id):
            ds = list(ds)  # Chuyển iterator thành list để dùng nhiều lần
            # Yield (tên loại hình, danh sách các choice của loại hình đó)
            yield (ds[0].MaLoaiHinh.TenLoaiHinh, [self.choice(goi) for goi in ds])


class GoiSelect(forms.Select):
    """Widget Select tùy chỉnh cho ô chọn gói.
    Mỗi <option> được gắn thêm các data-* attribute để JavaScript (gui_booking.js)
    hiển thị khung chi tiết gói và khóa các gói quá dài.
    data-khoa chỉ có khi gói dài hơn khung giờ đang giữ.
    self.lich được gán bởi GoiChoiceField.dat_slot()."""
    lich = None  # Slot đang giữ (được gán từ bên ngoài)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        # Gọi hàm gốc để tạo option chuẩn
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        # value là ModelChoiceIteratorValue, .instance = đối tượng gói thật
        goi = getattr(value, 'instance', None)
        if goi is not None:
            # Gắn các data attribute để JS đọc
            option['attrs'].update({
                'data-ten': goi.TenGoi,
                'data-loai-hinh': goi.MaLoaiHinh.TenLoaiHinh,
                'data-gia': _tien(goi.Gia),
                'data-thoi-luong': dinh_dang_thoi_luong(goi.ThoiLuongChup),
                'data-hau-ky': _hau_ky_hien_thi(goi),
                'data-mo-ta': goi.MoTa or '',
            })
            # Kiểm tra xem gói có bị khóa không
            ly_do = _ly_do_khoa(goi, self.lich)
            if ly_do:
                option['attrs']['data-khoa'] = ly_do   # Gắn lý do khóa
                option['attrs']['disabled'] = True     # Disable option (không chọn được)
            elif self.lich is not None:
                # Gói vừa slot: gắn giờ bắt đầu muộn nhất để JS cảnh báo
                option['attrs']['data-gio-muon-nhat'] = f'{timezone.localtime(gio_chup_muon_nhat(self.lich, goi)):%H:%M}'
        return option


class GoiChoiceField(forms.ModelChoiceField):
    """Field chọn gói dịch vụ, dùng iterator nhóm theo loại hình."""
    iterator = GoiTheoLoaiHinhIterator   # Dùng iterator tùy chỉnh ở trên
    lich = None                          # Slot đang giữ

    def dat_slot(self, lich):
        """Gán slot đang giữ cho field và widget để đánh dấu khóa các gói quá dài."""
        self.lich = lich
        self.widget.lich = lich

    def label_from_instance(self, goi):
        """Tạo nhãn hiển thị của option:
        'Tên gói - Giá VNĐ - Thời lượng - Hậu kỳ'
        Nếu gói bị khóa thì thêm 🔒 và lý do."""
        nhan = (f'{goi.TenGoi} - {_tien(goi.Gia)} VNĐ - {dinh_dang_thoi_luong(goi.ThoiLuongChup)} '
                f'- {_hau_ky_hien_thi(goi)}')
        ly_do = _ly_do_khoa(goi, self.lich)
        return f'🔒 {nhan} — {ly_do}' if ly_do else nhan


# Độ dài tối đa của 2 ô nhập tự do, tính sao cho chuỗi sau khi GHÉP không vượt cột của BOOKING:
#   DiaDiem VARCHAR(255): tên khu vực tối đa 100 + " - " (3) + địa chỉ 150  = 253 <= 255
#   Concept VARCHAR(500): tên phong cách tối đa 100 + " - " (3) + mô tả 390 = 493 <= 500
MAX_DIA_CHI_CU_THE = 150
MAX_MO_TA_CONCEPT = 390


def ghep_chu(ten_muc_da_chon, ghi_chu_them):
    """Ghép mục đã chọn với ô nhập thêm.
    Ví dụ: 'Hải Châu' + '12 Nguyễn Văn Linh' -> 'Hải Châu - 12 Nguyễn Văn Linh'
    Nếu ô nhập thêm để trống thì chỉ còn tên mục đã chọn."""
    ghi_chu_them = (ghi_chu_them or '').strip()
    return f'{ten_muc_da_chon} - {ghi_chu_them}' if ghi_chu_them else str(ten_muc_da_chon)


class GuiBookingForm(forms.Form):
    """Form nhập thông tin buổi chụp (bước 2 + 4 của UC).
    Tạo form: GuiBookingForm(du_lieu, lich=slot_dang_giu).
    Không có ô "Loại hình" riêng vì loại hình thuộc về gói."""

    # Các định dạng ngày giờ được chấp nhận khi parse từ request
    DINH_DANG_NGAY_GIO = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M']

    # Ô chọn gói dịch vụ
    goi = GoiChoiceField(
        queryset=GoiDichVu.objects.none(),               # Sẽ được gán lại trong __init__
        label='Gói dịch vụ',
        empty_label='-- Chọn gói dịch vụ --',
        widget=GoiSelect,                                # Dùng widget tùy chỉnh
        error_messages={'required': 'Vui lòng chọn gói dịch vụ.'},
        help_text='Gói có 🔒 dài hơn khung giờ bạn đang giữ nên không chọn được.')

    # Ô chọn ngày giờ chụp
    ngay_gio_chup = forms.DateTimeField(
        label='Ngày giờ chụp',
        input_formats=DINH_DANG_NGAY_GIO,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        error_messages={'required': 'Vui lòng chọn ngày giờ chụp.',
                        'invalid': 'Ngày giờ chụp không hợp lệ.'})

    # Ô chọn khu vực (bắt buộc) + địa chỉ cụ thể (không bắt buộc)
    khu_vuc = forms.ModelChoiceField(
        queryset=KhuVuc.objects.none(),                  # Sẽ được gán lại trong __init__
        label='Địa điểm chụp',
        empty_label='-- Chọn khu vực --',
        error_messages={'required': 'Vui lòng chọn địa điểm chụp.',
                        'invalid_choice': 'Khu vực này không thuộc khu vực Nhiếp ảnh gia nhận chụp.'},
        help_text='Các khu vực Nhiếp ảnh gia nhận chụp.')

    dia_chi_cu_the = forms.CharField(
        max_length=MAX_DIA_CHI_CU_THE,
        required=False,
        label='Địa chỉ cụ thể',
        help_text='Không bắt buộc. Ví dụ: tên quán, số nhà, đường.')

    # Số người (mặc định 1, tối thiểu 1)
    so_nguoi = forms.IntegerField(
        min_value=1,
        initial=1,
        label='Số người xuất hiện trong ảnh',
        help_text='Chụp sản phẩm: để 1.',
        error_messages={'required': 'Vui lòng nhập số người.',
                        'invalid': 'Số người phải là số nguyên.',
                        'min_value': 'Số người phải từ 1 trở lên.'})

    # Ô chọn phong cách (bắt buộc) + mô tả concept (không bắt buộc)
    phong_cach = forms.ModelChoiceField(
        queryset=PhongCach.objects.none(),               # Sẽ được gán lại trong __init__
        label='Concept',
        empty_label='-- Chọn concept --',
        error_messages={'required': 'Vui lòng chọn concept buổi chụp.',
                        'invalid_choice': 'Concept này không thuộc phong cách Nhiếp ảnh gia theo đuổi.'},
        help_text='Các phong cách Nhiếp ảnh gia theo đuổi.')

    mo_ta_concept = forms.CharField(
        max_length=MAX_MO_TA_CONCEPT,
        required=False,
        label='Mô tả concept',
        widget=forms.Textarea(attrs={'rows': 3}),
        help_text='Không bắt buộc: tông màu, trang phục, ý tưởng...')

    # Yêu cầu riêng (không bắt buộc)
    yeu_cau_rieng = forms.CharField(
        max_length=1000,
        required=False,
        label='Yêu cầu riêng',
        widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, lich, **kwargs):
        """Khởi tạo form, gắn slot đang giữ và lọc queryset theo Nhiếp ảnh gia của slot."""
        super().__init__(*args, **kwargs)
        self.lich = lich  # Lưu slot đang giữ

        # Chỉ lấy gói "Đang áp dụng" của đúng Nhiếp ảnh gia sở hữu slot
        # Sắp xếp theo tên loại hình để groupby tạo <optgroup> đúng
        self.fields['goi'].queryset = (GoiDichVu.objects
                                       .filter(MaNhiepAnhGia_id=lich.MaNhiepAnhGia_id,
                                               TrangThai=TrangThaiGoi.DANG_AP_DUNG)
                                       .select_related('MaLoaiHinh')
                                       .order_by('MaLoaiHinh__TenLoaiHinh', 'Gia', 'MaGoi'))
        self.fields['goi'].dat_slot(lich)  # Cho field/widget biết slot để khóa gói quá dài

        # Chỉ lấy khu vực và phong cách mà Nhiếp ảnh gia đã chọn trong hồ sơ
        self.fields['khu_vuc'].queryset = KhuVuc.objects.filter(nhiep_anh_gia__pk=lich.MaNhiepAnhGia_id)
        self.fields['phong_cach'].queryset = PhongCach.objects.filter(nhiep_anh_gia__pk=lich.MaNhiepAnhGia_id)

        # Gợi ý cho trình duyệt: min/max của datetime-local = khung giờ của slot
        dang_html = '%Y-%m-%dT%H:%M'
        bat_dau = timezone.make_aware(datetime.combine(lich.Ngay, lich.GioBatDau))
        ket_thuc = timezone.make_aware(datetime.combine(lich.Ngay, lich.GioKetThuc))
        self.fields['ngay_gio_chup'].initial = bat_dau  # Mặc định = giờ bắt đầu slot
        self.fields['ngay_gio_chup'].widget.attrs.update(
            {'min': bat_dau.strftime(dang_html),
             'max': ket_thuc.strftime(dang_html)})
        self.fields['ngay_gio_chup'].help_text = (
            f'Trong khung giờ đã giữ: {lich.Ngay:%d/%m/%Y} {lich.GioBatDau:%H:%M}–{lich.GioKetThuc:%H:%M}.')

    def clean_ngay_gio_chup(self):
        """Kiểm tra ngày giờ chụp:
        - Phải nằm trong khung giờ của slot (ngày đúng + giờ bắt đầu < giờ kết thúc slot)
        - Phải sau thời điểm hiện tại"""
        gia_tri = self.cleaned_data['ngay_gio_chup']
        thoi_diem = timezone.localtime(gia_tri)  # Đổi về giờ Việt Nam để so với slot
        lich = self.lich

        # Giờ chụp phải bắt đầu TRƯỚC giờ kết thúc slot
        if not (thoi_diem.date() == lich.Ngay and lich.GioBatDau <= thoi_diem.time() < lich.GioKetThuc):
            raise ValidationError(
                f'Ngày giờ chụp phải nằm trong khung giờ đã giữ '
                f'({lich.Ngay:%d/%m/%Y} {lich.GioBatDau:%H:%M}–{lich.GioKetThuc:%H:%M}).')

        if gia_tri <= timezone.now():
            raise ValidationError('Ngày giờ chụp phải sau thời điểm hiện tại.')
        return gia_tri

    def clean(self):
        """Kiểm tra toàn form: gói phải vừa khung giờ (giờ chụp + thời lượng gói <= giờ kết thúc slot)."""
        du_lieu = super().clean()
        goi, gio_chup = du_lieu.get('goi'), du_lieu.get('ngay_gio_chup')
        if goi:
            # Gọi hàm kiểm tra chung (dùng cả ở Booking.clean())
            # Nếu gói dài hơn cả khung giờ -> lỗi ở ô 'goi'
            # Nếu bắt đầu muộn quá -> lỗi ở ô 'ngay_gio_chup'
            loi = kiem_tra_goi_vua_slot(self.lich, goi, gio_chup)
            if loi:
                self.add_error(TEN_FIELD_FORM[loi[0]], loi[1])
        return du_lieu


# ---------------------------------------------------------------------
# PHẦN 3: HÀM NGHIỆP VỤ (SERVICE)
# ---------------------------------------------------------------------
def _ten_hien_thi(user):
    """Trả về tên đầy đủ của user, nếu không có thì lấy username."""
    return user.get_full_name() or user.username


def _gom_loi(loi_validation):
    """Chuyển ValidationError của Django thành dictionary {tên field: câu lỗi}.
    Lỗi không thuộc field nào sẽ có khóa '__all__'."""
    if hasattr(loi_validation, 'message_dict'):
        return {ten: ' '.join(ds) for ten, ds in loi_validation.message_dict.items()}
    return {'__all__': ' '.join(loi_validation.messages)}


def _gui_thong_bao_booking_moi(booking, lich, goi, khach_hang):
    """Gửi thông báo sau khi tạo Booking thành công (bước 6-7 + hậu điều kiện):
    - Thông báo web + Email cho Nhiếp ảnh gia
    - Thông báo web xác nhận cho Khách hàng
    gui_thong_bao tự nuốt lỗi nên không làm hỏng transaction Booking."""
    nag_user = lich.MaNhiepAnhGia.MaTaiKhoan
    gio_chup = timezone.localtime(booking.NgayGioChup)
    # Chuỗi chi tiết dùng chung cho cả 2 thông báo
    chi_tiet = (f'gói "{goi.TenGoi}" ({goi.MaLoaiHinh.TenLoaiHinh}), {gio_chup:%H:%M %d/%m/%Y}, '
                f'địa điểm {booking.DiaDiem}, {booking.SoNguoi} người, tổng giá trị {_tien(booking.TongGiaTri)} VNĐ')

    # Thông báo cho Nhiếp ảnh gia
    tieu_de_nag = 'Yêu cầu Booking mới'
    noi_dung_nag = (f'{_ten_hien_thi(khach_hang)} vừa gửi yêu cầu Booking #{booking.pk}: {chi_tiet}. '
                    f'Vui lòng xem và xác nhận yêu cầu.')
    tb_nag = gui_thong_bao(nag_user, tieu_de_nag, noi_dung_nag, booking=booking)  # Bước 6 (web)
    gui_email_sau_commit(tb_nag, nag_user, tieu_de_nag, noi_dung_nag)             # Bước 7 (Email, gửi sau commit)

    # Thông báo xác nhận cho Khách hàng
    gui_thong_bao(khach_hang, TB_DA_GUI,
                  f'Yêu cầu Booking #{booking.pk} với {_ten_hien_thi(nag_user)} ({chi_tiet}) đã được gửi. '
                  f'Vui lòng chờ Nhiếp ảnh gia xác nhận.',
                  booking=booking)


def _tao_booking(khach_hang, giu_cho, ma_goi, ngay_gio_chup, dia_diem, so_nguoi, concept, yeu_cau_rieng):
    """Tạo Booking trạng thái 'Chờ xác nhận' (bước 5).
    Phải được gọi bên trong transaction.atomic().
    Nếu lỗi ở bất kỳ đâu sẽ ném GuiBookingLoi để rollback toàn bộ (kể cả việc đóng lượt giữ chỗ)."""

    # Khóa dòng slot (select_for_update) rồi kiểm tra lại trạng thái
    lich = (LichKhaDung.objects.select_for_update()
            .select_related('MaNhiepAnhGia__MaTaiKhoan')
            .get(pk=giu_cho.MaLich_id))

    # Nhiếp ảnh gia vừa bị khóa / hồ sơ không còn công khai
    if not nhiep_anh_gia_cong_khai().filter(pk=lich.MaNhiepAnhGia_id).exists():
        raise GuiBookingLoi(TB_NAG_KHONG_NHAN_BOOKING, het_han=True)

    # Slot không còn ở trạng thái "Đang giữ chỗ"
    if lich.TrangThai != TrangThaiSlot.DANG_GIU:
        raise GuiBookingLoi(TB_SLOT_HET_HAN_GIU, het_han=True)

    # Slot đã có Booking còn hiệu lực (BR4.2-3)
    if (Booking.objects.filter(MaLich=lich)
            .exclude(TrangThai__in=TRANG_THAI_HET_HIEU_LUC).exists()):
        raise GuiBookingLoi(TB_SLOT_DA_CO_BOOKING, het_han=True)

    # Đọc lại gói trong transaction để lấy giá + trạng thái mới nhất
    try:
        goi = (GoiDichVu.objects.select_for_update()
               .select_related('MaLoaiHinh')
               .get(pk=ma_goi))
    except GoiDichVu.DoesNotExist:
        raise GuiBookingLoi('Gói dịch vụ không tồn tại.', {'MaGoi': 'Gói dịch vụ không tồn tại.'})

    # Tạo đối tượng Booking (chưa lưu)
    booking = Booking(
        MaKhachHang=khach_hang,
        MaNhiepAnhGia=lich.MaNhiepAnhGia,
        MaGoi=goi,
        MaLich=lich,
        NgayGioChup=ngay_gio_chup,
        DiaDiem=(dia_diem or '').strip(),
        SoNguoi=so_nguoi,
        Concept=(concept or '').strip(),
        YeuCauRieng=(yeu_cau_rieng or '').strip() or None,  # Ô trống -> NULL
        TrangThai=TrangThaiBooking.CHO_XAC_NHAN,
        TongGiaTri=goi.Gia,                                 # Tổng giá trị = giá gói tại thời điểm đặt
        NgayTao=timezone.now(),
    )

    # Gọi full_clean() để chạy toàn bộ validation của model Booking
    try:
        booking.full_clean()
    except ValidationError as loi:
        loi_truong = _gom_loi(loi)
        raise GuiBookingLoi(next(iter(loi_truong.values())), loi_truong)

    # Lưu Booking (có savepoint riêng để bắt IntegrityError mà không hỏng transaction ngoài)
    try:
        with transaction.atomic():
            booking.save()
    except IntegrityError:  # Ràng buộc unique (BR4.2-3) chặn lại
        raise GuiBookingLoi(TB_SLOT_DA_CO_BOOKING, het_han=True)

    # Ghi dòng lịch sử trạng thái đầu tiên (không có trạng thái cũ)
    LichSuTrangThaiBooking.objects.create(
        MaBooking=booking,
        TrangThaiCu=None,
        TrangThaiMoi=TrangThaiBooking.CHO_XAC_NHAN,
        ThoiDiemThayDoi=booking.NgayTao,
        BenThucHien=BenThucHien.KHACH_HANG,
        LyDo=None)

    # Gửi thông báo
    _gui_thong_bao_booking_moi(booking, lich, goi, khach_hang)
    return booking


def gui_yeu_cau_booking(khach_hang, ma_giu_cho, ma_goi, ngay_gio_chup, dia_diem, so_nguoi, concept,
                        yeu_cau_rieng=None):
    # gui_yeu_cau_booking để kiểm tra
    # lượt giữ chỗ có thuộc đúng khách hàng, chưa được sử dụng và còn trong thời hạn 5 phút.
    """Hàm nghiệp vụ chính (bước 4-8 của Basic Flow).
    Kiểm tra giữ chỗ + thông tin -> tạo Booking 'Chờ xác nhận'
    -> đánh dấu lượt giữ chỗ 'Đã hoàn tất Booking'
    -> gửi thông báo cho Nhiếp ảnh gia (web + Email) và Khách hàng (web).

    Trả về đối tượng Booking.
    Ném GuiBookingLoi khi:
      - Lượt giữ chỗ quá 5 phút (4a): .het_han = True, slot đã được trả về 'Lịch trống'
      - Thông tin không hợp lệ (1a): .loi_truong cho biết ô nào sai; lượt giữ chỗ KHÔNG bị đóng
      - Lượt giữ chỗ không phải của khách / đã dùng rồi / slot đã gắn Booking khác / lỗi hệ thống
    Toàn bộ nằm trong 1 transaction: lỗi ở đâu thì không có Booking, không đổi lượt giữ chỗ."""

    # Nhả các lượt giữ chỗ đã quá hạn trước (BR4.2-1)
    giai_phong_giu_cho_het_han()

    # 1. Tìm lượt giữ chỗ thuộc về đúng khách hàng, c
    # hưa được sử dụng và còn trong thời hạn 5 phút. ->  hàm _tao_booking khóa dòng slot,
    giu_cho = GiuCho.objects.filter(pk=ma_giu_cho, MaKhachHang=khach_hang).first()
    if giu_cho is None:
        raise GuiBookingLoi('Không tìm thấy lượt giữ chỗ.')
    if giu_cho.TrangThai == TrangThaiGiuCho.DA_HOAN_TAT:
        raise GuiBookingLoi(TB_GIU_CHO_DA_DUNG)
    if giu_cho.TrangThai == TrangThaiGiuCho.HET_HAN:
        raise GuiBookingLoi(TB_SLOT_HET_HAN_GIU, het_han=True)

    loi_giu_cho = None
    booking = None
    try:
        with transaction.atomic():
            try:
                # BR4.2-2: chỉ tạo Booking khi lượt giữ còn trong 5 phút.
                # Hàm của UC4.1 sẽ khóa dòng và đổi trạng thái lượt giữ -> 'Đã hoàn tất Booking'.
                # Nếu quá hạn thì nó nhả slot rồi ném GiuChoLoi.
                hoan_tat_giu_cho(khach_hang, ma_giu_cho)
            except GiuChoLoi as loi:
                # KHÔNG ném tiếp ở đây: ném ra khỏi atomic sẽ rollback luôn việc nhả slot vừa làm.
                loi_giu_cho = loi
            else:
                # Chỉ tạo Booking khi hoàn tất giữ chỗ thành công
                booking = _tao_booking(khach_hang, giu_cho, ma_goi, ngay_gio_chup, dia_diem, so_nguoi,
                                       concept, yeu_cau_rieng)
    except GuiBookingLoi:
        raise  # Ném lại lỗi nghiệp vụ
    except DatabaseError:  # Lỗi đọc/ghi database
        logger.exception('gui_yeu_cau_booking: lỗi hệ thống (khách %s, giữ chỗ %s)',
                         khach_hang.pk, ma_giu_cho)
        raise GuiBookingLoi(TB_LOI_HE_THONG)

    # Xử lý trường hợp hết hạn giữ chỗ (đã được nhả và commit)
    if loi_giu_cho is not None:
        if loi_giu_cho.thong_bao == TB_HET_HAN:
            raise GuiBookingLoi(TB_SLOT_HET_HAN_GIU, het_han=True)
        raise GuiBookingLoi(loi_giu_cho.thong_bao)

    return booking


# ---------------------------------------------------------------------
# PHẦN 4: VIEW VÀ URL
# ---------------------------------------------------------------------
def _ve_trang_lich(nag):
    """Chuyển về trang lịch của Nhiếp ảnh gia.
    Nếu Nhiếp ảnh gia không còn công khai thì về trang tìm kiếm."""
    if not nhiep_anh_gia_cong_khai().filter(pk=nag.pk).exists():
        return redirect('search')
    return redirect('lich_chon_slot', ma_nhiep_anh_gia=nag.pk)


def _trang_sau_khi_gui(booking, giu_cho):
    """Quyết định trang chuyển đến sau khi gửi Booking thành công.
    Ưu tiên: chi_tiet_booking -> danh_sach_booking -> man_hinh_giu_cho."""
    for ten_url, tham_so in (('chi_tiet_booking', {'ma_booking': booking.pk}),
                             ('danh_sach_booking', {})):
        try:
            return redirect(reverse(ten_url, kwargs=tham_so))
        except NoReverseMatch:
            continue  # URL chưa được định nghĩa -> thử cái tiếp theo
    # Chưa có UC4.7 thì quay về màn hình giữ chỗ
    return redirect('man_hinh_giu_cho', ma_giu_cho=giu_cho.pk)


def _dua_loi_vao_form(form, loi):
    """Luồng 1a: đưa lỗi từ service về đúng ô nhập trên form.
    Lỗi không thuộc ô nào thì hiện ở đầu form."""
    da_dua = False
    for ten_field_model, cau_loi in loi.loi_truong.items():
        ten_field_form = TEN_FIELD_FORM.get(ten_field_model)
        if ten_field_form:
            form.add_error(ten_field_form, cau_loi)
            da_dua = True
    if not da_dua:
        form.add_error(None, loi.thong_bao)  # Lỗi chung (không thuộc field)


def _initial_goi_chon_san(request, nag, lich):
    """Xử lý gói chọn sẵn từ query string ?goi=<mã>
    (khách bấm 'Chọn gói' ở hồ sơ Nhiếp ảnh gia).
    Chỉ nhận gói 'Đang áp dụng' của đúng Nhiếp ảnh gia.
    Nếu gói dài hơn khung giờ đang giữ thì KHÔNG chọn sẵn và báo lý do."""
    goi = goi_chon_san_hop_le(nag.pk, request.GET.get('goi'))
    if goi is None:
        return {}
    ly_do = _ly_do_khoa(goi, lich)
    if ly_do:
        messages.warning(request, f'Gói "{goi.TenGoi}" {ly_do}. Vui lòng chọn gói khác hoặc chọn lại khung giờ.')
        return {}
    return {'goi': goi.pk}


@khach_hang_required                                          # Chỉ khách hàng mới vào được
@require_http_methods(['GET', 'POST'])                        # Chỉ cho phép GET và POST
def gui_booking(request, ma_giu_cho):
    #  Nếu request là GET (664), view khởi tạo form từ class GuiBookingForm,
    #  sau đó sử dụng render() để truyền form vào template gui_booking.html
    #  và hiển thị cho khách hàng nhập thông tin.
    #Khi khách hàng bấm gửi yêu cầu Booking, view tiếp nhận dữ liệu thông qua request.POST
    # và gọi form.is_valid() để kiểm tra tính hợp lệ của dữ liệu.

#Nếu dữ liệu hợp lệ, view gọi hàm gui_yeu_cau_booking để kiểm tra lượt giữ chỗ có thuộc
    # đúng khách hàng, chưa được sử dụng và còn trong thời hạn 5 phút.
#Sau đó, hàm _tao_booking khóa dòng slot, kiểm tra slot chưa có Booking còn hiệu lực,
    # lấy giá gói từ database và tạo Booking với trạng thái “Chờ xác nhận”.
    # Cuối cùng, hệ thống ghi lịch sử trạng thái và gọi _gui_thong_bao_booking_moi
    # để gửi thông báo cho nhiếp ảnh gia qua website và email.

    """View chính của UC4.2 (bước 1-3 và 8).
    Hiển thị form điền thông tin buổi chụp + đếm ngược thời gian giữ chỗ.
    Tên URL phải là 'gui_booking' vì bookings/giu_cho.py gọi reverse('gui_booking')."""

    # Nhả các lượt giữ chỗ hết hạn trước khi xử lý
    giai_phong_giu_cho_het_han()

    # Chỉ lấy lượt giữ chỗ thuộc về chính khách hàng đang đăng nhập
    giu_cho = get_object_or_404(
        GiuCho.objects.select_related('MaLich__MaNhiepAnhGia__MaTaiKhoan'),
        pk=ma_giu_cho, MaKhachHang=request.user)
    lich = giu_cho.MaLich
    nag = lich.MaNhiepAnhGia

    # Đã gửi Booking rồi (bấm lại / mở lại link cũ)
    if giu_cho.TrangThai == TrangThaiGiuCho.DA_HOAN_TAT:
        messages.info(request, TB_GIU_CHO_DA_DUNG)
        return redirect('man_hinh_giu_cho', ma_giu_cho=giu_cho.pk)

    # Nhiếp ảnh gia bị khóa: không cho mở form gửi Booking
    if not nhiep_anh_gia_cong_khai().filter(pk=nag.pk).exists():
        messages.error(request, TB_NAG_KHONG_NHAN_BOOKING)
        return _ve_trang_lich(nag)

    # Lượt giữ chỗ đã hết hạn (ngoại lệ 4a)
    if giu_cho.TrangThai != TrangThaiGiuCho.DANG_GIU or giu_cho.da_het_han:
        giai_phong_giu_cho_het_han()
        messages.error(request, TB_SLOT_HET_HAN_GIU)
        return _ve_trang_lich(nag)

    if request.method == 'POST':
        # Khách bấm nút "Gửi yêu cầu Booking"
        form = GuiBookingForm(request.POST, lich=lich)
        if form.is_valid(): #Nếu dữ liệu hợp lệ, view gọi hàm gui_yeu_cau_booking để kiểm tra
            # lượt giữ chỗ có thuộc đúng khách hàng, chưa được sử dụng và còn trong thời hạn 5 phút.

            du_lieu = form.cleaned_data
            # Ghép khu vực + địa chỉ cụ thể -> DiaDiem
            # Ghép phong cách + mô tả concept -> Concept
            dia_diem = ghep_chu(du_lieu['khu_vuc'].TenKhuVuc, du_lieu['dia_chi_cu_the'])
            concept = ghep_chu(du_lieu['phong_cach'].TenPhongCach, du_lieu['mo_ta_concept'])
            try:
                booking = gui_yeu_cau_booking(
                    request.user, giu_cho.pk, du_lieu['goi'].pk, du_lieu['ngay_gio_chup'],
                    dia_diem, du_lieu['so_nguoi'], concept, du_lieu['yeu_cau_rieng'])
            except GuiBookingLoi as loi:
                if loi.het_han:  # 4a: hết hạn -> kết thúc UC, khách làm lại UC4.1
                    messages.error(request, loi.thong_bao)
                    return _ve_trang_lich(nag)
                # 1a: thông tin sai -> đưa lỗi vào form để khách sửa và gửi lại
                _dua_loi_vao_form(form, loi)
            else:
                # Thành công
                messages.success(request, TB_DA_GUI)  # Bước 8
                return _trang_sau_khi_gui(booking, giu_cho)
    else:
        # Lần đầu mở form (GET)
        form = GuiBookingForm(lich=lich, initial=_initial_goi_chon_san(request, nag, lich))
        # lich=lich: thông tin khung giờ đang giữ.
        # initial: dữ liệu gói dịch vụ được chọn sẵn (nếu có).

    # Render trang form
    return render(request, 'bookings/gui_booking.html', {
        'form': form,
        'giu_cho': giu_cho,
        'lich': lich,
        'thoi_luong_slot': dinh_dang_thoi_luong(so_phut_slot(lich)),  # Ví dụ: '2 giờ'
        'ten_nag': _ten_hien_thi(nag.MaTaiKhoan),
        'con_lai_giay': so_giay_con_lai(giu_cho),                     # Số giây còn lại để đếm ngược
        'tong_giay': int(THOI_GIAN_GIU_CHO.total_seconds()),          # Tổng thời gian giữ chỗ (300 giây)
        'url_lich': reverse('lich_chon_slot', kwargs={'ma_nhiep_anh_gia': nag.pk}),
        'url_trang_thai': reverse('trang_thai_giu_cho', kwargs={'ma_giu_cho': giu_cho.pk}),
        'TB_SLOT_HET_HAN_GIU': TB_SLOT_HET_HAN_GIU,                   # Truyền xuống JS để hiện khi hết hạn
    })


# URL patterns của module này
# Trong config/urls.py cần thêm: path('bookings/', include('bookings.gui_booking')),
urlpatterns = [
    path('giu-cho/<int:ma_giu_cho>/gui-booking/', gui_booking, name='gui_booking'),
]