# =====================================================================
# bookings/giu_cho.py  -  UC4.1 Chọn lịch khả dụng và giữ chỗ 5 phút (Tuyền)
#
# Yêu cầu: Khách hàng đã đăng nhập chọn slot "Lịch trống" -> slot thành "Đang giữ chỗ" 5 phút,
# người khác không chọn được. Chọn slot khác thì ghi nhận slot mới. Màn hình đếm ngược 5 phút.
# Hết 5 phút chưa gửi Booking -> slot về "Lịch trống", lượt giữ chỗ (GIUCHO) thành "Hết hạn".
#
# File gồm 4 phần:
#   PHẦN 1. Import, hằng số, lỗi nghiệp vụ
#   PHẦN 2. Hàm nghiệp vụ (service):
#           giu_cho_slot(khach_hang, ma_lich)     -> bước 3-5 của Basic Flow (+ 3a, 4a, 4b)
#           giai_phong_giu_cho_het_han()          -> ngoại lệ 5b: nhả các slot quá 5 phút
#           lay_giu_cho_hien_tai(khach_hang)      -> lượt giữ chỗ còn hạn của khách (hoặc None)
#           so_giay_con_lai(giu_cho)              -> số giây còn lại để đếm ngược
#           hoan_tat_giu_cho(khach_hang, ma_giu_cho) -> DÀNH CHO UC4.2: gửi Booking kịp 5 phút
#   PHẦN 3. View (trang lịch, nút chọn slot, màn hình đếm ngược, API trạng thái)
#   PHẦN 4. urlpatterns (nối vào config/urls.py bằng include('bookings.giu_cho'))
#
# Quy tắc nhóm: KHÔNG đổi slot bằng cách tự gán TrangThai; luôn gọi
# schedule.services.doi_trang_thai_khung_gio (hàm của Khoa). File này cũng làm đúng như vậy.
# Chữ trạng thái luôn lấy từ core/constants.py.
# =====================================================================

# ---------------------------------------------------------------------
# PHẦN 1: IMPORT, HẰNG SỐ, LỖI NGHIỆP VỤ
# ---------------------------------------------------------------------
import logging
from collections import OrderedDict
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, path, reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from bookings.models import THOI_GIAN_GIU_CHO, GiuCho   # THOI_GIAN_GIU_CHO = 5 phút (BR4.1-1)
from core.constants import TrangThaiGiuCho, TrangThaiHoSo, TrangThaiSlot, VaiTro
from profiles.models import NhiepAnhGia
from schedule.models import LichKhaDung
from schedule.services import doi_trang_thai_khung_gio, khung_gio_trong

logger = logging.getLogger(__name__)

# Thông báo cho người dùng (đúng chữ trong đặc tả UC4.1).
TB_SLOT_KHONG_KHA_DUNG = 'Slot không còn khả dụng'                                   # ngoại lệ 4a
TB_LOI_HE_THONG = 'Không thể thực hiện yêu cầu, vui lòng thử lại sau.'               # ngoại lệ 4b
TB_HET_HAN = 'Thời gian giữ chỗ đã hết hạn. Khung giờ đã được trả về lịch trống.'     # ngoại lệ 5b
TB_KHONG_PHAI_KHACH = 'Chỉ tài khoản Khách hàng mới được chọn lịch và giữ chỗ.'

SO_NGAY_HIEN_THI_LICH = 30   # trang lịch chỉ liệt kê slot trống trong 30 ngày tới


class GiuChoLoi(Exception):
    """Lỗi nghiệp vụ của UC4.1; .thong_bao là câu tiếng Việt hiện cho người dùng."""

    def __init__(self, thong_bao):
        super().__init__(thong_bao)
        self.thong_bao = thong_bao


# ---------------------------------------------------------------------
# PHẦN 2: HÀM NGHIỆP VỤ (SERVICE)
# ---------------------------------------------------------------------
def _la_khach_hang(nguoi_dung):
    # GiuCho.clean() yêu cầu người giữ chỗ thuộc Group "Khách hàng"; kiểm tra trước để báo lỗi rõ.
    return nguoi_dung.is_authenticated and nguoi_dung.groups.filter(name=VaiTro.KHACH_HANG).exists()


def _tra_slot_ve_trong(ma_lich):
    """Trả slot về 'Lịch trống' bằng hàm của Khoa. Chỉ làm khi slot đang là 'Đang giữ chỗ'
    (nếu slot đã sang trạng thái khác thì không đụng vào)."""
    lich = LichKhaDung.objects.select_for_update().get(pk=ma_lich)
    if lich.TrangThai == TrangThaiSlot.DANG_GIU:
        doi_trang_thai_khung_gio(lich, TrangThaiSlot.TRONG)


def _ket_thuc_luot_giu(giu_cho):
    """Kết thúc một lượt đang giữ: lượt -> 'Hết hạn', slot -> 'Lịch trống'.
    Phải gọi bên trong transaction.atomic(). Trả True nếu thật sự kết thúc được."""
    # UPDATE có điều kiện "vẫn đang giữ": nếu nơi khác (vd gửi Booking) vừa đổi trạng thái thì số dòng = 0.
    so_dong = (GiuCho.objects.filter(pk=giu_cho.pk, TrangThai=TrangThaiGiuCho.DANG_GIU)
               .update(TrangThai=TrangThaiGiuCho.HET_HAN))
    if so_dong != 1:
        return False
    _tra_slot_ve_trong(giu_cho.MaLich_id)
    return True


def _het_han_mot_luot(ma_giu_cho, bay_gio):
    """Nhả MỘT lượt giữ nếu nó vẫn 'Đang giữ chỗ' và đã quá hạn. Trả True nếu đã nhả."""
    try:
        with transaction.atomic():
            giu_cho = GiuCho.objects.select_for_update().filter(pk=ma_giu_cho).first()
            if (giu_cho is None or giu_cho.TrangThai != TrangThaiGiuCho.DANG_GIU
                    or giu_cho.ThoiDiemHetHan > bay_gio):
                return False     # đã có nơi khác xử lý, hoặc chưa tới hạn
            return _ket_thuc_luot_giu(giu_cho)
    except ValidationError:      # hàm của Khoa từ chối đổi slot: bỏ qua lượt này, quét tiếp lượt khác
        logger.exception('giai_phong_giu_cho_het_han: không nhả được lượt %s', ma_giu_cho)
        return False


def giai_phong_giu_cho_het_han():
    """Ngoại lệ 5b / BR4.1-1: mọi lượt 'Đang giữ chỗ' đã quá ThoiDiemHetHan -> 'Hết hạn',
    slot tương ứng -> 'Lịch trống'. Trả về số lượt đã nhả.

    Project không có tác vụ chạy nền, nên hàm này được gọi "lười" ngay đầu các view đọc/đổi slot
    (trang lịch, chọn slot, màn hình đếm ngược). Muốn nhả đúng giờ cả khi không ai mở web thì gọi
    định kỳ (vd mỗi phút) bằng lệnh quản trị/Task Scheduler."""
    bay_gio = timezone.now()
    ds_ma = list(GiuCho.objects.filter(TrangThai=TrangThaiGiuCho.DANG_GIU, ThoiDiemHetHan__lte=bay_gio)
                 .values_list('pk', flat=True))
    return sum(1 for ma in ds_ma if _het_han_mot_luot(ma, bay_gio))


def lay_giu_cho_hien_tai(khach_hang):
    """Lượt giữ chỗ còn hạn của khách (mỗi khách tối đa một lượt), hoặc None."""
    giai_phong_giu_cho_het_han()
    return (GiuCho.objects.select_related('MaLich__MaNhiepAnhGia__MaTaiKhoan')
            .filter(MaKhachHang=khach_hang, TrangThai=TrangThaiGiuCho.DANG_GIU).first())


def so_giay_con_lai(giu_cho):
    """Số giây còn lại của lượt giữ (0 nếu không còn 'Đang giữ chỗ' hoặc đã quá hạn)."""
    if giu_cho.TrangThai != TrangThaiGiuCho.DANG_GIU:
        return 0
    return max(0, int((giu_cho.ThoiDiemHetHan - timezone.now()).total_seconds()))


def giu_cho_slot(khach_hang, ma_lich):
    """Bước 3-5 của Basic Flow: Khách chọn slot -> kiểm tra -> giữ 5 phút.

    - Slot 'Lịch trống'            -> thành 'Đang giữ chỗ', tạo một dòng GIUCHO (5 phút).
    - Khách đang giữ đúng slot này -> trả lại lượt cũ, KHÔNG gia hạn (tránh giữ chỗ vô hạn).
    - Khách đang giữ slot khác     -> (3a) nhả slot cũ về 'Lịch trống', ghi nhận slot mới.
      Mỗi khách chỉ có tối đa MỘT lượt đang giữ.
    Mọi thứ trong một transaction: lỗi ở đâu thì không đổi gì (slot cũ của khách vẫn được giữ).

    Trả về đối tượng GiuCho. Báo GiuChoLoi (có .thong_bao) khi:
      slot không còn khả dụng (4a), lỗi hệ thống (4b), hoặc người dùng không phải Khách hàng."""
    if not _la_khach_hang(khach_hang):
        raise GiuChoLoi(TB_KHONG_PHAI_KHACH)

    try:
        giai_phong_giu_cho_het_han()          # nhả slot quá hạn trước, để slot đó chọn được lại
        with transaction.atomic():
            # Khóa dòng slot: hai khách bấm cùng lúc thì lần lượt từng người (BR4.1-2).
            try:
                lich = LichKhaDung.objects.select_for_update().get(pk=ma_lich)
            except LichKhaDung.DoesNotExist:
                raise GiuChoLoi(TB_SLOT_KHONG_KHA_DUNG)

            bay_gio = timezone.now()

            # Các lượt đang giữ của chính khách này.
            luot_cu = list(GiuCho.objects.select_for_update()
                           .filter(MaKhachHang=khach_hang, TrangThai=TrangThaiGiuCho.DANG_GIU))
            for cu in luot_cu:
                if cu.MaLich_id == lich.pk and cu.ThoiDiemHetHan > bay_gio:
                    return cu                 # đang giữ đúng slot này và còn hạn: dùng lại

            # 4. Kiểm tra trạng thái slot.
            if lich.TrangThai != TrangThaiSlot.TRONG:
                raise GiuChoLoi(TB_SLOT_KHONG_KHA_DUNG)       # 4a: người khác giữ/đặt rồi

            # 3a. Chọn slot khác: nhả slot cũ của chính khách này.
            try:
                for cu in luot_cu:
                    _ket_thuc_luot_giu(cu)
            except ValidationError:               # slot cũ không nhả được: huỷ cả thao tác, khách giữ nguyên slot cũ
                logger.exception('giu_cho_slot: không nhả được slot cũ (khách %s)', khach_hang.pk)
                raise GiuChoLoi(TB_LOI_HE_THONG)

            # 5. Đổi slot -> 'Đang giữ chỗ' bằng hàm của Khoa. Hàm này tự chặn slot đã qua giờ bắt đầu
            #    và dùng UPDATE có điều kiện nên nếu có người nhanh tay hơn thì báo lỗi.
            try:
                doi_trang_thai_khung_gio(lich, TrangThaiSlot.DANG_GIU)
            except ValidationError:
                raise GiuChoLoi(TB_SLOT_KHONG_KHA_DUNG)

            # Ghi lượt giữ chỗ. Đặt sẵn giờ hết hạn = giờ giữ + 5 phút; gọi full_clean()
            # theo ghi chú trong bookings/models.py (clean() chỉ chạy khi mình gọi).
            giu_cho = GiuCho(MaKhachHang=khach_hang, MaLich=lich, ThoiDiemGiu=bay_gio,
                             ThoiDiemHetHan=bay_gio + THOI_GIAN_GIU_CHO,
                             TrangThai=TrangThaiGiuCho.DANG_GIU)
            try:
                with transaction.atomic():    # savepoint riêng để bắt IntegrityError mà không hỏng transaction ngoài
                    giu_cho.full_clean()
                    giu_cho.save()
            except (ValidationError, IntegrityError):
                # ràng buộc "mỗi slot một lượt đang giữ" (BR4.1-2) chặn lại
                raise GiuChoLoi(TB_SLOT_KHONG_KHA_DUNG)
            return giu_cho
    except GiuChoLoi:
        raise
    except DatabaseError:                     # 4b: không đọc/ghi được database
        logger.exception('giu_cho_slot: lỗi hệ thống (khách %s, slot %s)', khach_hang.pk, ma_lich)
        raise GiuChoLoi(TB_LOI_HE_THONG)


def hoan_tat_giu_cho(khach_hang, ma_giu_cho):
    """DÀNH CHO UC4.2 (Gửi yêu cầu Booking): gọi trong cùng transaction với việc tạo Booking.

    Lượt giữ còn hạn -> 'Đã hoàn tất Booking'. Slot vẫn ở 'Đang giữ chỗ' (đã gửi Booking chưa chốt,
    đúng chú thích TrangThaiSlot.DANG_GIU). Quá 5 phút -> nhả slot, báo TB_HET_HAN.
    Trả về đối tượng GiuCho."""
    with transaction.atomic():
        giu_cho = (GiuCho.objects.select_for_update()
                   .filter(pk=ma_giu_cho, MaKhachHang=khach_hang).first())
        if giu_cho is None:
            raise GiuChoLoi('Không tìm thấy lượt giữ chỗ.')
        if giu_cho.TrangThai == TrangThaiGiuCho.DANG_GIU and giu_cho.ThoiDiemHetHan > timezone.now():
            giu_cho.TrangThai = TrangThaiGiuCho.DA_HOAN_TAT        # kịp 5 phút
            giu_cho.save(update_fields=['TrangThai'])
            return giu_cho
        if giu_cho.TrangThai == TrangThaiGiuCho.DANG_GIU:           # quá 5 phút mà chưa ai nhả: nhả ngay
            _ket_thuc_luot_giu(giu_cho)
    # Báo lỗi NGOÀI khối atomic: nếu raise bên trong thì việc nhả slot ở trên bị rollback theo.
    raise GiuChoLoi(TB_HET_HAN)


# ---------------------------------------------------------------------
# PHẦN 3: VIEW
# ---------------------------------------------------------------------
def khach_hang_required(view):
    """Chỉ cho Khách hàng đã đăng nhập: chưa đăng nhập -> trang đăng nhập (kèm ?next=); sai vai trò -> 403."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            try:
                trang_dang_nhap = reverse('login')      # tên URL 'login' do Phanh (accounts) đặt, xem core/navigation.py
            except NoReverseMatch:
                trang_dang_nhap = settings.LOGIN_URL    # chưa có thì dùng LOGIN_URL, không làm sập trang
            return redirect_to_login(request.get_full_path(), trang_dang_nhap)
        if not _la_khach_hang(request.user):
            raise PermissionDenied(TB_KHONG_PHAI_KHACH)
        return view(request, *args, **kwargs)
    return wrapper


def _url_gui_booking(giu_cho):
    """Link sang UC4.2 'Gửi yêu cầu Booking'. Khi bạn viết UC4.2, đặt tên URL đó là 'gui_booking'
    (nhận ma_giu_cho) thì nút 'Tiếp tục' tự hiện; chưa có thì trả None."""
    try:
        return reverse('gui_booking', kwargs={'ma_giu_cho': giu_cho.pk})
    except NoReverseMatch:
        return None


def _ve_trang_lich(ma_nhiep_anh_gia):
    # Quay lại trang lịch của nhiếp ảnh gia; thiếu mã thì về trang chủ.
    try:
        return redirect('lich_chon_slot', ma_nhiep_anh_gia=int(ma_nhiep_anh_gia))
    except (TypeError, ValueError, NoReverseMatch):
        try:
            return redirect('home')
        except NoReverseMatch:
            return redirect('/')


@khach_hang_required
@require_GET
def trang_lich_nhiep_anh_gia(request, ma_nhiep_anh_gia):
    """Bước 1-2: trang lịch công khai, liệt kê các slot 'Lịch trống' của một nhiếp ảnh gia."""
    nag = get_object_or_404(NhiepAnhGia.objects.select_related('MaTaiKhoan'), pk=ma_nhiep_anh_gia,
                            MaTaiKhoan__trang_thai_ho_so=TrangThaiHoSo.DA_DUYET)   # chỉ hồ sơ đã duyệt mới công khai
    giu_cho_hien_tai = lay_giu_cho_hien_tai(request.user)   # (đã nhả slot quá hạn) để hiện banner "bạn đang giữ"

    # Gom slot theo ngày: [(ngày, [slot, slot...]), ...]
    theo_ngay = OrderedDict()
    for slot in khung_gio_trong(nag, so_ngay=SO_NGAY_HIEN_THI_LICH):
        theo_ngay.setdefault(slot.Ngay, []).append(slot)

    return render(request, 'bookings/lich_chon_slot.html', {
        'nag': nag,
        'ten_nag': nag.MaTaiKhoan.get_full_name() or nag.MaTaiKhoan.username,
        'lich_theo_ngay': list(theo_ngay.items()),
        'giu_cho_hien_tai': giu_cho_hien_tai,
        'so_ngay': SO_NGAY_HIEN_THI_LICH,
    })


@khach_hang_required
@require_POST
def chon_slot(request, ma_lich):
    """Bước 3: Khách bấm chọn một slot. Thành công -> sang màn hình đếm ngược (bước 6)."""
    ma_nag = request.POST.get('ma_nhiep_anh_gia')        # form trên trang lịch gửi kèm để biết đường quay lại
    try:
        giu_cho = giu_cho_slot(request.user, ma_lich)
    except GiuChoLoi as loi:                              # 4a / 4b: báo lỗi rồi kết thúc UC
        messages.error(request, loi.thong_bao)
        return _ve_trang_lich(ma_nag)
    return redirect('man_hinh_giu_cho', ma_giu_cho=giu_cho.pk)


@khach_hang_required
@require_GET
def man_hinh_giu_cho(request, ma_giu_cho):
    """Bước 6: màn hình hiện slot đang giữ + đếm ngược 5 phút (và nút sang Gửi yêu cầu Booking)."""
    giai_phong_giu_cho_het_han()
    giu_cho = get_object_or_404(
        GiuCho.objects.select_related('MaLich__MaNhiepAnhGia__MaTaiKhoan'),
        pk=ma_giu_cho, MaKhachHang=request.user)          # chỉ xem được lượt của chính mình
    lich = giu_cho.MaLich
    nag = lich.MaNhiepAnhGia
    con_lai = so_giay_con_lai(giu_cho)
    return render(request, 'bookings/giu_cho.html', {
        'giu_cho': giu_cho,
        'lich': lich,
        'ten_nag': nag.MaTaiKhoan.get_full_name() or nag.MaTaiKhoan.username,
        'con_lai_giay': con_lai,
        'tong_giay': int(THOI_GIAN_GIU_CHO.total_seconds()),
        'dang_giu': con_lai > 0,                                              # còn đếm ngược
        'da_het_han': giu_cho.TrangThai == TrangThaiGiuCho.HET_HAN,           # ngoại lệ 5b
        'da_hoan_tat': giu_cho.TrangThai == TrangThaiGiuCho.DA_HOAN_TAT,      # đã gửi Booking kịp hạn
        'url_gui_booking': _url_gui_booking(giu_cho),
        'url_lich': reverse('lich_chon_slot', kwargs={'ma_nhiep_anh_gia': nag.pk}),
        'url_trang_thai': reverse('trang_thai_giu_cho', kwargs={'ma_giu_cho': giu_cho.pk}),
        'TB_HET_HAN': TB_HET_HAN,
    })


@khach_hang_required
@require_GET
def trang_thai_giu_cho(request, ma_giu_cho):
    """API JSON cho bộ đếm ngược: trả số giây còn lại thật của server (không tin đồng hồ máy khách).
    Khi hết giờ, JS gọi lại đây; việc nhả slot xảy ra ở dòng giai_phong_giu_cho_het_han()."""
    giai_phong_giu_cho_het_han()
    giu_cho = get_object_or_404(GiuCho, pk=ma_giu_cho, MaKhachHang=request.user)
    con_lai = so_giay_con_lai(giu_cho)
    return JsonResponse({
        'trang_thai': giu_cho.TrangThai,
        'con_lai_giay': con_lai,
        'het_han': giu_cho.TrangThai == TrangThaiGiuCho.HET_HAN,
        'thong_bao': TB_HET_HAN if giu_cho.TrangThai == TrangThaiGiuCho.HET_HAN else '',
    })


# ---------------------------------------------------------------------
# PHẦN 4: URL  (trong config/urls.py thêm:  path('bookings/', include('bookings.giu_cho')),)
# ---------------------------------------------------------------------
urlpatterns = [
    path('nhiep-anh-gia/<int:ma_nhiep_anh_gia>/lich/', trang_lich_nhiep_anh_gia, name='lich_chon_slot'),
    path('giu-cho/chon/<int:ma_lich>/', chon_slot, name='chon_slot'),
    path('giu-cho/<int:ma_giu_cho>/', man_hinh_giu_cho, name='man_hinh_giu_cho'),
    path('giu-cho/<int:ma_giu_cho>/trang-thai/', trang_thai_giu_cho, name='trang_thai_giu_cho'),
]
