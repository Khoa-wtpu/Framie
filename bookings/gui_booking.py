# =====================================================================
# bookings/gui_booking.py  -  UC4.2 Gửi yêu cầu Booking (Tuyền)
#
# Yêu cầu: Khách hàng (đã giữ slot ở UC4.1) điền gói dịch vụ (chỉ gói "Đang áp dụng"), loại hình,
# ngày giờ nằm trong khung giờ đã giữ, địa điểm, số người, concept, yêu cầu riêng.
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
import logging
from datetime import datetime

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import DatabaseError, IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, path, reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from bookings.giu_cho import (   # dùng lại phần của UC4.1 để hai UC nhất quán
    TB_HET_HAN,                  # câu báo hết hạn của UC4.1 (hàm hoan_tat_giu_cho ném ra), UC4.2 đổi sang câu riêng bên dưới
    TB_LOI_HE_THONG,
    GiuChoLoi,
    giai_phong_giu_cho_het_han,
    hoan_tat_giu_cho,
    khach_hang_required,
    so_giay_con_lai,
)
from bookings.models import (
    THOI_GIAN_GIU_CHO,
    TRANG_THAI_HET_HIEU_LUC,
    Booking,
    GiuCho,
    LichSuTrangThaiBooking,
)
from core.constants import (
    BenThucHien,
    TrangThaiBooking,
    TrangThaiGiuCho,
    TrangThaiGoi,
    TrangThaiGuiEmail,
    TrangThaiSlot,
)
from notifications.models import ThongBao
from notifications.services import gui_thong_bao
from profiles.models import GoiDichVu, LoaiHinhChup
from schedule.models import LichKhaDung

logger = logging.getLogger(__name__)

# Thông báo cho người dùng (đúng chữ trong đặc tả UC4.2).
TB_SLOT_HET_HAN_GIU = 'Slot đã hết thời gian giữ chỗ, vui lòng chọn lại'   # ngoại lệ 4a
TB_DA_GUI = 'Yêu cầu Booking đã được gửi'                                   # bước 8
TB_GIU_CHO_DA_DUNG = 'Lượt giữ chỗ này đã được dùng để gửi yêu cầu Booking.'
TB_SLOT_DA_CO_BOOKING = 'Slot này đã gắn với một Booking đang có hiệu lực, vui lòng chọn lại.'   # BR4.2-3

# Tên field của Booking (model) -> tên field của form. Dùng để đưa lỗi từ Booking.clean() về đúng ô nhập.
TEN_FIELD_FORM = {
    'MaGoi': 'goi',
    'NgayGioChup': 'ngay_gio_chup',
    'DiaDiem': 'dia_diem',
    'SoNguoi': 'so_nguoi',
    'Concept': 'concept',
    'YeuCauRieng': 'yeu_cau_rieng',
}


class GuiBookingLoi(Exception):
    """Lỗi nghiệp vụ của UC4.2.
    .thong_bao  : câu tiếng Việt hiện cho người dùng.
    .loi_truong : {tên field của Booking: câu lỗi} khi lỗi thuộc về một ô nhập (luồng 1a).
    .het_han    : True khi lượt giữ chỗ đã hết hạn (ngoại lệ 4a) -> kết thúc UC, không cho sửa tiếp."""

    def __init__(self, thong_bao, loi_truong=None, het_han=False):
        super().__init__(thong_bao)
        self.thong_bao = thong_bao
        self.loi_truong = loi_truong or {}
        self.het_han = het_han


# ---------------------------------------------------------------------
# PHẦN 2: FORM NHẬP THÔNG TIN BUỔI CHỤP
# ---------------------------------------------------------------------
class GoiSelect(forms.Select):
    """Ô chọn gói: mỗi <option> kèm data-loai-hinh để JS lọc gói theo loại hình đã chọn."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        goi = getattr(value, 'instance', None)          # value là ModelChoiceIteratorValue, .instance = gói
        if goi is not None:
            option['attrs']['data-loai-hinh'] = goi.MaLoaiHinh_id
        return option


class GoiChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, goi):
        gia = f'{int(goi.Gia):,}'.replace(',', '.')
        return f'{goi.TenGoi} - {gia} VNĐ'


class GuiBookingForm(forms.Form):
    """Bước 2 + 4: Khách nhập thông tin buổi chụp; form kiểm tra đầy đủ và hợp lệ.
    Tạo form: GuiBookingForm(du_lieu, lich=slot_dang_giu)."""

    DINH_DANG_NGAY_GIO = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M']

    loai_hinh = forms.ModelChoiceField(
        queryset=LoaiHinhChup.objects.none(), label='Loại hình chụp', empty_label='-- Chọn loại hình --',
        error_messages={'required': 'Vui lòng chọn loại hình chụp.'})
    goi = GoiChoiceField(
        queryset=GoiDichVu.objects.none(), label='Gói dịch vụ', empty_label='-- Chọn gói dịch vụ --',
        widget=GoiSelect, error_messages={'required': 'Vui lòng chọn gói dịch vụ.'})
    ngay_gio_chup = forms.DateTimeField(
        label='Ngày giờ chụp', input_formats=DINH_DANG_NGAY_GIO,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        error_messages={'required': 'Vui lòng chọn ngày giờ chụp.',
                        'invalid': 'Ngày giờ chụp không hợp lệ.'})
    dia_diem = forms.CharField(
        max_length=255, label='Địa điểm', error_messages={'required': 'Vui lòng nhập địa điểm chụp.'})
    so_nguoi = forms.IntegerField(
        min_value=1, label='Số người',
        error_messages={'required': 'Vui lòng nhập số người.', 'invalid': 'Số người phải là số nguyên.',
                        'min_value': 'Số người phải từ 1 trở lên.'})
    concept = forms.CharField(
        max_length=500, label='Concept', widget=forms.Textarea(attrs={'rows': 3}),
        error_messages={'required': 'Vui lòng nhập concept buổi chụp.'})
    yeu_cau_rieng = forms.CharField(
        max_length=1000, required=False, label='Yêu cầu riêng', widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, lich, **kwargs):
        super().__init__(*args, **kwargs)
        self.lich = lich
        # Chỉ gói "Đang áp dụng" của đúng Nhiếp ảnh gia sở hữu slot (BR của UC1.4).
        ds_goi = (GoiDichVu.objects
                  .filter(MaNhiepAnhGia_id=lich.MaNhiepAnhGia_id, TrangThai=TrangThaiGoi.DANG_AP_DUNG)
                  .select_related('MaLoaiHinh').order_by('MaLoaiHinh__TenLoaiHinh', 'Gia'))
        self.fields['goi'].queryset = ds_goi
        self.fields['loai_hinh'].queryset = (LoaiHinhChup.objects
                                             .filter(pk__in=ds_goi.values('MaLoaiHinh'))
                                             .order_by('TenLoaiHinh'))
        # Gợi ý cho trình duyệt: chỉ cho chọn giờ trong khung giờ của slot; mặc định là giờ bắt đầu slot.
        dang_html = '%Y-%m-%dT%H:%M'
        bat_dau = timezone.make_aware(datetime.combine(lich.Ngay, lich.GioBatDau))
        ket_thuc = timezone.make_aware(datetime.combine(lich.Ngay, lich.GioKetThuc))
        self.fields['ngay_gio_chup'].initial = bat_dau
        self.fields['ngay_gio_chup'].widget.attrs.update(
            {'min': bat_dau.strftime(dang_html), 'max': ket_thuc.strftime(dang_html)})
        self.fields['ngay_gio_chup'].help_text = (
            f'Chọn trong khung giờ đã giữ: {lich.Ngay:%d/%m/%Y} {lich.GioBatDau:%H:%M}–{lich.GioKetThuc:%H:%M}.')

    def clean_ngay_gio_chup(self):
        gia_tri = self.cleaned_data['ngay_gio_chup']
        thoi_diem = timezone.localtime(gia_tri)       # đổi về giờ Việt Nam để so với slot
        lich = self.lich
        # Giờ chụp phải bắt đầu TRƯỚC giờ kết thúc slot (buổi chụp bắt đầu đúng lúc slot kết thúc là vô nghĩa).
        if not (thoi_diem.date() == lich.Ngay and lich.GioBatDau <= thoi_diem.time() < lich.GioKetThuc):
            raise ValidationError(
                f'Ngày giờ chụp phải nằm trong khung giờ đã giữ '
                f'({lich.Ngay:%d/%m/%Y} {lich.GioBatDau:%H:%M}–{lich.GioKetThuc:%H:%M}).')
        if gia_tri <= timezone.now():
            raise ValidationError('Ngày giờ chụp phải sau thời điểm hiện tại.')
        return gia_tri

    def clean(self):
        du_lieu = super().clean()
        loai_hinh, goi = du_lieu.get('loai_hinh'), du_lieu.get('goi')
        # "loại hình" không có cột riêng trong BOOKING: nó là loại hình của gói, nên phải khớp với gói đã chọn.
        if loai_hinh and goi and goi.MaLoaiHinh_id != loai_hinh.pk:
            self.add_error('goi', 'Gói dịch vụ không thuộc loại hình chụp đã chọn.')
        return du_lieu


# ---------------------------------------------------------------------
# PHẦN 3: HÀM NGHIỆP VỤ (SERVICE)
# ---------------------------------------------------------------------
def _ten_hien_thi(user):
    return user.get_full_name() or user.username


def _gom_loi(loi_validation):
    """ValidationError của Django -> {tên field: câu lỗi}; lỗi không thuộc field nào có khóa '__all__'."""
    if hasattr(loi_validation, 'message_dict'):
        return {ten: ' '.join(ds) for ten, ds in loi_validation.message_dict.items()}
    return {'__all__': ' '.join(loi_validation.messages)}


def _tien(so):
    return f'{int(so):,}'.replace(',', '.')


def _gui_email_nhiep_anh_gia(thong_bao, nguoi_nhan, tieu_de, noi_dung):
    """Bước 7: tự động gửi Email cho Nhiếp ảnh gia. Chạy SAU KHI Booking đã lưu xong (transaction.on_commit);
    lỗi gửi mail chỉ được ghi log + đánh dấu 'Gửi thất bại', không làm hỏng Booking đã tạo."""
    try:
        if not nguoi_nhan.email:
            raise ValueError('Nhiếp ảnh gia chưa có email')
        send_mail(tieu_de, noi_dung, None, [nguoi_nhan.email], fail_silently=False)   # None = DEFAULT_FROM_EMAIL
        ket_qua = TrangThaiGuiEmail.THANH_CONG
    except Exception:  # noqa: BLE001  # SMTP/DNS/... lỗi gì cũng không được làm sập request
        logger.exception('gui_yeu_cau_booking: gửi email thất bại (%s)', tieu_de)
        ket_qua = TrangThaiGuiEmail.THAT_BAI
    if thong_bao is not None:   # ghi kết quả gửi email vào thông báo web tương ứng
        try:
            ThongBao.objects.filter(pk=thong_bao.pk).update(TrangThaiGuiEmail=ket_qua)
        except DatabaseError:
            logger.exception('gui_yeu_cau_booking: không ghi được TrangThaiGuiEmail')


def _gui_thong_bao_booking_moi(booking, lich, goi, khach_hang):
    """Bước 6-7 + hậu điều kiện: thông báo web cho Nhiếp ảnh gia, Email cho Nhiếp ảnh gia,
    thông báo web xác nhận đã gửi cho Khách hàng. gui_thong_bao (của Phanh) tự nuốt lỗi nên không phá Booking."""
    nag_user = lich.MaNhiepAnhGia.MaTaiKhoan
    gio_chup = timezone.localtime(booking.NgayGioChup)
    chi_tiet = (f'gói "{goi.TenGoi}" ({goi.MaLoaiHinh.TenLoaiHinh}), {gio_chup:%H:%M %d/%m/%Y}, '
                f'địa điểm {booking.DiaDiem}, {booking.SoNguoi} người, tổng giá trị {_tien(booking.TongGiaTri)} VNĐ')

    tieu_de_nag = 'Yêu cầu Booking mới'
    noi_dung_nag = (f'{_ten_hien_thi(khach_hang)} vừa gửi yêu cầu Booking #{booking.pk}: {chi_tiet}. '
                    f'Vui lòng xem và xác nhận yêu cầu.')
    tb_nag = gui_thong_bao(nag_user, tieu_de_nag, noi_dung_nag, booking=booking)             # bước 6 (web)
    transaction.on_commit(lambda: _gui_email_nhiep_anh_gia(tb_nag, nag_user, tieu_de_nag, noi_dung_nag))   # bước 7 (Email)

    gui_thong_bao(khach_hang, TB_DA_GUI,                                                      # hậu điều kiện: báo Khách hàng
                  f'Yêu cầu Booking #{booking.pk} với {_ten_hien_thi(nag_user)} ({chi_tiet}) đã được gửi. '
                  f'Vui lòng chờ Nhiếp ảnh gia xác nhận.',
                  booking=booking)


def _tao_booking(khach_hang, giu_cho, ma_goi, ngay_gio_chup, dia_diem, so_nguoi, concept, yeu_cau_rieng):
    """Bước 5: tạo Booking 'Chờ xác nhận'. Phải gọi trong transaction.atomic(); lỗi ở đâu thì
    ném GuiBookingLoi để transaction (cả việc đóng lượt giữ chỗ) được rollback."""
    # Khóa dòng slot rồi kiểm tra nó vẫn đang được giữ (BR4.2-3: một slot chỉ gắn một Booking còn hiệu lực).
    lich = (LichKhaDung.objects.select_for_update().select_related('MaNhiepAnhGia__MaTaiKhoan')
            .get(pk=giu_cho.MaLich_id))
    if lich.TrangThai != TrangThaiSlot.DANG_GIU:
        raise GuiBookingLoi(TB_SLOT_HET_HAN_GIU, het_han=True)
    if (Booking.objects.filter(MaLich=lich).exclude(TrangThai__in=TRANG_THAI_HET_HIEU_LUC).exists()):
        raise GuiBookingLoi(TB_SLOT_DA_CO_BOOKING, het_han=True)

    # Đọc lại gói trong transaction: lấy đúng giá và trạng thái mới nhất (Nhiếp ảnh gia có thể vừa sửa/ngừng gói).
    try:
        goi = GoiDichVu.objects.select_for_update().select_related('MaLoaiHinh').get(pk=ma_goi)
    except GoiDichVu.DoesNotExist:
        raise GuiBookingLoi('Gói dịch vụ không tồn tại.', {'MaGoi': 'Gói dịch vụ không tồn tại.'})

    booking = Booking(
        MaKhachHang=khach_hang,
        MaNhiepAnhGia=lich.MaNhiepAnhGia,
        MaGoi=goi,
        MaLich=lich,
        NgayGioChup=ngay_gio_chup,
        DiaDiem=(dia_diem or '').strip(),
        SoNguoi=so_nguoi,
        Concept=(concept or '').strip(),
        YeuCauRieng=(yeu_cau_rieng or '').strip() or None,   # ô để trống -> NULL
        TrangThai=TrangThaiBooking.CHO_XAC_NHAN,
        TongGiaTri=goi.Gia,                                  # tổng giá trị = giá gói tại thời điểm đặt
        NgayTao=timezone.now(),
    )
    try:
        # clean() của Booking kiểm tra: khách thuộc nhóm Khách hàng, gói/slot thuộc đúng Nhiếp ảnh gia,
        # gói "Đang áp dụng", giờ chụp nằm trong slot (đúng ghi chú trong bookings/models.py: phải gọi full_clean()).
        booking.full_clean()
    except ValidationError as loi:
        loi_truong = _gom_loi(loi)
        raise GuiBookingLoi(next(iter(loi_truong.values())), loi_truong)

    try:
        with transaction.atomic():   # savepoint riêng để bắt IntegrityError mà không hỏng transaction ngoài
            booking.save()
    except IntegrityError:           # ràng buộc uq_booking_malich_con_hieu_luc (BR4.2-3) chặn lại
        raise GuiBookingLoi(TB_SLOT_DA_CO_BOOKING, het_han=True)

    # Dòng Lịch sử đầu tiên của Booking (không có trạng thái cũ).
    LichSuTrangThaiBooking.objects.create(
        MaBooking=booking, TrangThaiCu=None, TrangThaiMoi=TrangThaiBooking.CHO_XAC_NHAN,
        ThoiDiemThayDoi=booking.NgayTao, BenThucHien=BenThucHien.KHACH_HANG, LyDo=None)

    _gui_thong_bao_booking_moi(booking, lich, goi, khach_hang)
    return booking


def gui_yeu_cau_booking(khach_hang, ma_giu_cho, ma_goi, ngay_gio_chup, dia_diem, so_nguoi, concept,
                        yeu_cau_rieng=None):
    """Bước 4-8 của Basic Flow: kiểm tra giữ chỗ + thông tin -> tạo Booking 'Chờ xác nhận'
    -> lượt giữ chỗ 'Đã hoàn tất Booking' -> thông báo Nhiếp ảnh gia (web + Email) và Khách hàng (web).

    Trả về đối tượng Booking. Báo GuiBookingLoi (có .thong_bao) khi:
      - lượt giữ chỗ quá 5 phút (4a): .het_han = True, slot đã được trả về 'Lịch trống';
      - thông tin không hợp lệ (1a): .loi_truong cho biết ô nào sai; lượt giữ chỗ KHÔNG bị đóng, Khách sửa và gửi lại;
      - lượt giữ chỗ không phải của khách / đã dùng rồi, slot đã gắn Booking khác, hoặc lỗi hệ thống.
    Mọi thứ nằm trong một transaction: lỗi ở đâu thì không có Booking, không đổi lượt giữ chỗ."""
    giai_phong_giu_cho_het_han()          # nhả các lượt quá hạn trước (BR4.2-1)

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
                # BR4.2-2: chỉ tạo Booking khi lượt giữ còn trong 5 phút. Hàm của UC4.1 khóa dòng và đổi
                # lượt giữ -> 'Đã hoàn tất Booking'; nếu quá hạn nó nhả slot rồi ném GiuChoLoi.
                hoan_tat_giu_cho(khach_hang, ma_giu_cho)
            except GiuChoLoi as loi:
                # KHÔNG ném tiếp ở đây: ném ra khỏi atomic sẽ rollback luôn việc nhả slot vừa làm.
                loi_giu_cho = loi
            else:
                booking = _tao_booking(khach_hang, giu_cho, ma_goi, ngay_gio_chup, dia_diem, so_nguoi,
                                       concept, yeu_cau_rieng)
    except GuiBookingLoi:
        raise
    except DatabaseError:                 # không đọc/ghi được database
        logger.exception('gui_yeu_cau_booking: lỗi hệ thống (khách %s, giữ chỗ %s)', khach_hang.pk, ma_giu_cho)
        raise GuiBookingLoi(TB_LOI_HE_THONG)

    if loi_giu_cho is not None:           # ngoại lệ 4a: slot đã được nhả và commit
        if loi_giu_cho.thong_bao == TB_HET_HAN:
            raise GuiBookingLoi(TB_SLOT_HET_HAN_GIU, het_han=True)
        raise GuiBookingLoi(loi_giu_cho.thong_bao)
    return booking


# ---------------------------------------------------------------------
# PHẦN 4: VIEW VÀ URL
# ---------------------------------------------------------------------
def _ve_trang_lich(nag):
    return redirect('lich_chon_slot', ma_nhiep_anh_gia=nag.pk)


def _trang_sau_khi_gui(booking, giu_cho):
    """Gửi xong chuyển tới đâu? Khi làm UC4.7 (Theo dõi trạng thái Booking), đặt tên URL 'chi_tiet_booking'
    (nhận ma_booking) hoặc 'danh_sach_booking' thì sẽ tự chuyển tới đó; chưa có thì về màn hình giữ chỗ
    (màn hình đó đã có khối 'Đã gửi yêu cầu Booking')."""
    for ten_url, tham_so in (('chi_tiet_booking', {'ma_booking': booking.pk}), ('danh_sach_booking', {})):
        try:
            return redirect(reverse(ten_url, kwargs=tham_so))
        except NoReverseMatch:
            continue
    return redirect('man_hinh_giu_cho', ma_giu_cho=giu_cho.pk)


def _dua_loi_vao_form(form, loi):
    """Luồng 1a: đưa lỗi của service về đúng ô nhập; lỗi không thuộc ô nào thì hiện ở đầu form."""
    da_dua = False
    for ten_field_model, cau_loi in loi.loi_truong.items():
        ten_field_form = TEN_FIELD_FORM.get(ten_field_model)
        if ten_field_form:
            form.add_error(ten_field_form, cau_loi)
            da_dua = True
    if not da_dua:
        form.add_error(None, loi.thong_bao)


@khach_hang_required
@require_http_methods(['GET', 'POST'])
def gui_booking(request, ma_giu_cho):
    """Bước 1-3 và 8: trang điền thông tin buổi chụp (slot vẫn đang giữ + đếm ngược) và nút
    'Gửi yêu cầu Booking'. Tên URL phải là 'gui_booking' vì bookings/giu_cho.py gọi reverse('gui_booking')."""
    giai_phong_giu_cho_het_han()
    giu_cho = get_object_or_404(
        GiuCho.objects.select_related('MaLich__MaNhiepAnhGia__MaTaiKhoan'),
        pk=ma_giu_cho, MaKhachHang=request.user)          # chỉ làm việc với lượt giữ của chính mình
    lich = giu_cho.MaLich
    nag = lich.MaNhiepAnhGia

    if giu_cho.TrangThai == TrangThaiGiuCho.DA_HOAN_TAT:   # đã gửi rồi (bấm lại / mở lại link cũ)
        messages.info(request, TB_GIU_CHO_DA_DUNG)
        return redirect('man_hinh_giu_cho', ma_giu_cho=giu_cho.pk)
    if giu_cho.TrangThai != TrangThaiGiuCho.DANG_GIU or giu_cho.da_het_han:   # ngoại lệ 4a
        giai_phong_giu_cho_het_han()
        messages.error(request, TB_SLOT_HET_HAN_GIU)
        return _ve_trang_lich(nag)

    if request.method == 'POST':
        form = GuiBookingForm(request.POST, lich=lich)
        if form.is_valid():
            du_lieu = form.cleaned_data
            try:
                booking = gui_yeu_cau_booking(
                    request.user, giu_cho.pk, du_lieu['goi'].pk, du_lieu['ngay_gio_chup'],
                    du_lieu['dia_diem'], du_lieu['so_nguoi'], du_lieu['concept'], du_lieu['yeu_cau_rieng'])
            except GuiBookingLoi as loi:
                if loi.het_han:                               # 4a: kết thúc UC, Khách làm lại UC4.1
                    messages.error(request, loi.thong_bao)
                    return _ve_trang_lich(nag)
                _dua_loi_vao_form(form, loi)                  # 1a: Khách sửa và gửi lại (vẫn trong 5 phút)
            else:
                messages.success(request, TB_DA_GUI)          # bước 8
                return _trang_sau_khi_gui(booking, giu_cho)
    else:
        form = GuiBookingForm(lich=lich)

    return render(request, 'bookings/gui_booking.html', {
        'form': form,
        'giu_cho': giu_cho,
        'lich': lich,
        'ten_nag': _ten_hien_thi(nag.MaTaiKhoan),
        'con_lai_giay': so_giay_con_lai(giu_cho),
        'tong_giay': int(THOI_GIAN_GIU_CHO.total_seconds()),
        'url_lich': reverse('lich_chon_slot', kwargs={'ma_nhiep_anh_gia': nag.pk}),
        'url_trang_thai': reverse('trang_thai_giu_cho', kwargs={'ma_giu_cho': giu_cho.pk}),
        'TB_SLOT_HET_HAN_GIU': TB_SLOT_HET_HAN_GIU,
    })


# URL  (trong config/urls.py thêm:  path('bookings/', include('bookings.gui_booking')),)
urlpatterns = [
    path('giu-cho/<int:ma_giu_cho>/gui-booking/', gui_booking, name='gui_booking'),
]
