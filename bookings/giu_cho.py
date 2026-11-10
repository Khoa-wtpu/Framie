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
# Import thư viện logging để ghi lại lỗi và thông tin phục vụ kiểm tra hệ thống.
import logging
# Import OrderedDict để lưu các slot theo ngày và giữ nguyên thứ tự ngày xuất hiện.
from collections import OrderedDict
# Import wraps để decorator giữ lại tên và thông tin của view gốc.
from functools import wraps
# Import urlencode để ghép ?goi=<mã gói> vào đường dẫn (tự mã hóa ký tự đặc biệt).
from urllib.parse import urlencode

# Lấy cấu hình Django, ở đây dùng để lấy LOGIN_URL khi cần chuyển người dùng đến trang đăng nhập.
from django.conf import settings
# Import messages để hiển thị thông báo thành công hoặc lỗi trên giao diện.
from django.contrib import messages
# Import hàm chuyển hướng đến trang đăng nhập và lưu URL người dùng muốn truy cập.
from django.contrib.auth.views import redirect_to_login
# Import các loại lỗi Django dùng để báo không đủ quyền hoặc dữ liệu không hợp lệ.
from django.core.exceptions import PermissionDenied, ValidationError
# Import lỗi database và công cụ transaction để nhóm nhiều thao tác thành một giao dịch an toàn.
from django.db import DatabaseError, IntegrityError, transaction
# Import JsonResponse để trả dữ liệu JSON cho JavaScript cập nhật đồng hồ đếm ngược.
from django.http import HttpResponse, JsonResponse
# Import các hàm lấy dữ liệu, chuyển trang và render template.
from django.shortcuts import get_object_or_404, redirect, render
# Import công cụ xử lý URL: path để khai báo đường dẫn, reverse để tìm URL theo tên.
from django.urls import NoReverseMatch, path, reverse
# Import timezone của Django để lấy thời gian hiện tại theo múi giờ dự án.
from django.utils import timezone
# Import bộ giới hạn phương thức HTTP: view chỉ nhận GET hoặc POST theo yêu cầu.
from django.views.decorators.http import require_GET, require_POST

# Lấy thời lượng giữ chỗ và model GiuCho; thời lượng được cấu hình là 5 phút.
from bookings.models import THOI_GIAN_GIU_CHO, GiuCho   # THOI_GIAN_GIU_CHO = 5 phút (BR4.1-1)
# Import các hằng số trạng thái và vai trò dùng thống nhất trong toàn dự án.
from core.constants import TrangThaiGiuCho, TrangThaiGoi, TrangThaiSlot, VaiTro
# Import model hồ sơ nhiếp ảnh gia để tìm thông tin người cung cấp dịch vụ.
from profiles.models import GoiDichVu
# Import model lịch khả dụng của nhiếp ảnh gia.
from schedule.models import LichKhaDung
# Import hàm đổi trạng thái slot và hàm lấy danh sách khung giờ còn trống từ module schedule.
from schedule.services import doi_trang_thai_khung_gio, khung_gio_trong
# Nhiếp ảnh gia được công khai (hồ sơ 'Đã duyệt' VÀ tài khoản chưa bị khóa): dùng chung với tìm kiếm / hồ sơ công khai.
from search.services import nhiep_anh_gia_cong_khai

# Tạo logger riêng cho module này để ghi nhận lỗi khi xử lý giữ chỗ.
logger = logging.getLogger(__name__)

# Thông báo cho người dùng (đúng chữ trong đặc tả UC4.1).
# Thông báo hiển thị khi slot khách chọn không còn trống hoặc không thể giữ.
TB_SLOT_KHONG_KHA_DUNG = 'Slot không còn khả dụng'                                   # ngoại lệ 4a
# Thông báo khi Nhiếp ảnh gia không còn công khai (bị khóa tài khoản hoặc hồ sơ không còn 'Đã duyệt').
TB_NAG_KHONG_NHAN_BOOKING = 'Nhiếp ảnh gia này hiện không nhận Booking.'
# Thông báo chung khi xảy ra lỗi hệ thống trong quá trình giữ chỗ.
TB_LOI_HE_THONG = 'Không thể thực hiện yêu cầu, vui lòng thử lại sau.'               # ngoại lệ 4b
# Thông báo hiển thị khi thời gian giữ chỗ đã hết.
TB_HET_HAN = 'Thời gian giữ chỗ đã hết hạn. Khung giờ đã được trả về lịch trống.'     # ngoại lệ 5b
# Thông báo khi người truy cập không thuộc nhóm Khách hàng.
TB_KHONG_PHAI_KHACH = 'Chỉ tài khoản Khách hàng mới được chọn lịch và giữ chỗ.'

# Giới hạn trang lịch chỉ hiển thị các slot trong 30 ngày tiếp theo.
SO_NGAY_HIEN_THI_LICH = 30   # trang lịch chỉ liệt kê slot trống trong 30 ngày tới


# Khai báo ngoại lệ riêng cho lỗi nghiệp vụ của chức năng giữ chỗ.
class GiuChoLoi(Exception):
    # Docstring mô tả mục đích của lớp lỗi; thuộc tính thong_bao chứa nội dung gửi ra giao diện.
    """Lỗi nghiệp vụ của UC4.1; .thong_bao là câu tiếng Việt hiện cho người dùng."""

    # Khởi tạo lỗi và nhận nội dung thông báo cần hiển thị.
    def __init__(self, thong_bao):
        # Gọi hàm khởi tạo của lớp Exception cha để lỗi hoạt động đúng chuẩn Python.
        super().__init__(thong_bao)
        # Lưu nội dung thông báo vào thuộc tính để view có thể đọc và hiển thị.
        self.thong_bao = thong_bao


# ---------------------------------------------------------------------
# PHẦN 2: HÀM NGHIỆP VỤ (SERVICE)
# ---------------------------------------------------------------------
# Định nghĩa hàm kiểm tra tài khoản hiện tại có phải Khách hàng hay không.
def _la_khach_hang(nguoi_dung):
    # GiuCho.clean() yêu cầu người giữ chỗ thuộc Group "Khách hàng"; kiểm tra trước để báo lỗi rõ.
    # Trả về True khi tài khoản đã đăng nhập và thuộc group Khách hàng; ngược lại trả False.
    return nguoi_dung.is_authenticated and nguoi_dung.groups.filter(name=VaiTro.KHACH_HANG).exists()


# Định nghĩa hàm đưa một slot về trạng thái Lịch trống khi lượt giữ kết thúc.
def _tra_slot_ve_trong(ma_lich):
    # Docstring mô tả điều kiện đổi trạng thái: chỉ trả slot về trống nếu hiện đang được giữ.
    """Trả slot về 'Lịch trống' bằng hàm của Khoa. Chỉ làm khi slot đang là 'Đang giữ chỗ'
    (nếu slot đã sang trạng thái khác thì không đụng vào)."""
    # Lấy bản ghi lịch theo khóa chính và khóa dòng trong database để tránh hai tiến trình sửa cùng lúc.
    lich = LichKhaDung.objects.select_for_update().get(pk=ma_lich)
    # Kiểm tra trạng thái hiện tại của slot có đúng là Đang giữ chỗ không.
    if lich.TrangThai == TrangThaiSlot.DANG_GIU:
        # Nếu đúng, gọi service dùng chung của nhóm để chuyển slot về Lịch trống.
        doi_trang_thai_khung_gio(lich, TrangThaiSlot.TRONG)


# Định nghĩa hàm kết thúc một lượt giữ chỗ.
def _ket_thuc_luot_giu(giu_cho):
    # Docstring mô tả hai việc cần làm: lượt giữ thành Hết hạn và slot được trả về trống.
    """Kết thúc một lượt đang giữ: lượt -> 'Hết hạn', slot -> 'Lịch trống'.
    # Ghi chú yêu cầu hàm phải chạy trong transaction và trả True nếu kết thúc thành công.
    Phải gọi bên trong transaction.atomic(). Trả True nếu thật sự kết thúc được."""
    # UPDATE có điều kiện "vẫn đang giữ": nếu nơi khác (vd gửi Booking) vừa đổi trạng thái thì số dòng = 0.
    # Tìm lượt giữ theo mã và chỉ cập nhật nếu trạng thái vẫn là Đang giữ chỗ.
    so_dong = (GiuCho.objects.filter(pk=giu_cho.pk, TrangThai=TrangThaiGiuCho.DANG_GIU)
               # Đổi trạng thái lượt giữ thành Hết hạn; update trả về số bản ghi được cập nhật.
               .update(TrangThai=TrangThaiGiuCho.HET_HAN))
    # Kiểm tra có đúng một bản ghi vừa được cập nhật hay không.
    if so_dong != 1:
        # Nếu không cập nhật được, lượt giữ có thể đã được xử lý ở nơi khác nên trả False.
        return False
    # Nếu cập nhật thành công, trả slot liên quan về trạng thái Lịch trống.
    _tra_slot_ve_trong(giu_cho.MaLich_id)
    # Báo rằng lượt giữ đã được kết thúc thành công.
    return True


# Định nghĩa hàm kiểm tra và giải phóng một lượt giữ đã quá hạn.
def _het_han_mot_luot(ma_giu_cho, bay_gio):
    # Docstring nêu điều kiện: lượt vẫn đang giữ và thời điểm hết hạn không muộn hơn thời điểm hiện tại.
    """Nhả MỘT lượt giữ nếu nó vẫn 'Đang giữ chỗ' và đã quá hạn. Trả True nếu đã nhả."""
    # Bắt đầu khối xử lý lỗi có thể phát sinh khi giải phóng slot.
    try:
        # Mở transaction để các thao tác kiểm tra và cập nhật của lượt giữ được thực hiện an toàn.
        with transaction.atomic():
            # Lấy lượt giữ theo mã, đồng thời khóa bản ghi; first() trả về bản ghi đầu tiên hoặc None.
            giu_cho = GiuCho.objects.select_for_update().filter(pk=ma_giu_cho).first()
            # Kiểm tra lượt giữ có tồn tại và còn ở trạng thái Đang giữ chỗ hay không.
            if (giu_cho is None or giu_cho.TrangThai != TrangThaiGiuCho.DANG_GIU
                    # Kiểm tra thêm thời điểm hết hạn; nếu thời điểm hết hạn vẫn ở tương lai thì chưa cần giải phóng.
                    or giu_cho.ThoiDiemHetHan > bay_gio):
                # Nếu không tồn tại, đã được xử lý hoặc chưa đến hạn thì bỏ qua lượt này.
                return False     # đã có nơi khác xử lý, hoặc chưa tới hạn
            # Nếu đủ điều kiện, gọi hàm kết thúc lượt giữ và trả về kết quả.
            return _ket_thuc_luot_giu(giu_cho)
    # Bắt lỗi khi service đổi trạng thái slot từ chối thao tác.
    except ValidationError:      # hàm của Khoa từ chối đổi slot: bỏ qua lượt này, quét tiếp lượt khác
        # Ghi lại thông tin lỗi cùng mã lượt giữ để lập trình viên kiểm tra.
        logger.exception('giai_phong_giu_cho_het_han: không nhả được lượt %s', ma_giu_cho)
        # Trả False để bỏ qua lượt lỗi và tiếp tục xử lý các lượt khác.
        return False


# Định nghĩa hàm quét và giải phóng tất cả lượt giữ đã quá hạn.
def giai_phong_giu_cho_het_han():
    # Docstring mô tả chức năng xử lý ngoại lệ hết 5 phút theo yêu cầu UC4.1.
    """Ngoại lệ 5b / BR4.1-1: mọi lượt 'Đang giữ chỗ' đã quá ThoiDiemHetHan -> 'Hết hạn',
    # Nêu kết quả mong muốn: lượt giữ hết hạn, slot tương ứng trở lại lịch trống.
    slot tương ứng -> 'Lịch trống'. Trả về số lượt đã nhả.

    # Giải thích cơ chế hiện tại: dự án chưa có tác vụ chạy nền nên kiểm tra khi người dùng truy cập view.
    Project không có tác vụ chạy nền, nên hàm này được gọi "lười" ngay đầu các view đọc/đổi slot
    # Liệt kê các view sẽ gọi hàm giải phóng lượt hết hạn.
    (trang lịch, chọn slot, màn hình đếm ngược). Muốn nhả đúng giờ cả khi không ai mở web thì gọi
    # Gợi ý có thể cấu hình tác vụ chạy định kỳ nếu muốn tự giải phóng đúng giờ dù không có người truy cập.
    định kỳ (vd mỗi phút) bằng lệnh quản trị/Task Scheduler."""
    # Lấy thời điểm hiện tại theo timezone của Django để so sánh với hạn giữ chỗ.
    bay_gio = timezone.now()
    # Truy vấn các lượt đang giữ nhưng có thời điểm hết hạn nhỏ hơn hoặc bằng hiện tại.
    ds_ma = list(GiuCho.objects.filter(TrangThai=TrangThaiGiuCho.DANG_GIU, ThoiDiemHetHan__lte=bay_gio)
                 # Chỉ lấy danh sách mã khóa chính thay vì tải toàn bộ đối tượng GiuCho vào bộ nhớ.
                 .values_list('pk', flat=True))
    # Gọi hàm giải phóng cho từng mã và cộng số lượt thực sự được giải phóng.
    return sum(1 for ma in ds_ma if _het_han_mot_luot(ma, bay_gio))


# Định nghĩa hàm lấy lượt giữ chỗ hiện tại của một khách hàng.
def lay_giu_cho_hien_tai(khach_hang):
    # Docstring cho biết mỗi khách tối đa một lượt đang giữ; không có thì trả None.
    """Lượt giữ chỗ còn hạn của khách (mỗi khách tối đa một lượt), hoặc None."""
    # Giải phóng các lượt đã quá hạn trước khi tìm lượt hiện tại.
    giai_phong_giu_cho_het_han()
    # Truy vấn GiuCho và tải sẵn thông tin lịch, nhiếp ảnh gia, tài khoản để hạn chế truy vấn phát sinh.
    return (GiuCho.objects.select_related('MaLich__MaNhiepAnhGia__MaTaiKhoan')
            # Lọc theo khách hàng và trạng thái Đang giữ chỗ, sau đó lấy một kết quả đầu tiên.
            .filter(MaKhachHang=khach_hang, TrangThai=TrangThaiGiuCho.DANG_GIU).first())


# Định nghĩa hàm tính số giây còn lại của một lượt giữ.
def so_giay_con_lai(giu_cho):
    # Docstring mô tả kết quả bằng 0 nếu lượt không còn hiệu lực.
    """Số giây còn lại của lượt giữ (0 nếu không còn 'Đang giữ chỗ' hoặc đã quá hạn)."""
    # Kiểm tra trạng thái lượt giữ có khác Đang giữ chỗ hay không.
    if giu_cho.TrangThai != TrangThaiGiuCho.DANG_GIU:
        # Nếu không còn đang giữ, trả về 0 giây.
        return 0
    # Lấy chênh lệch giữa thời điểm hết hạn và hiện tại, đổi sang giây, lấy số nguyên và chặn giá trị âm về 0.
    return max(0, int((giu_cho.ThoiDiemHetHan - timezone.now()).total_seconds()))


# Định nghĩa hàm chính xử lý yêu cầu khách hàng giữ một slot cụ thể.
def giu_cho_slot(khach_hang, ma_lich):
    # Docstring mô tả luồng chính: khách chọn slot, hệ thống kiểm tra rồi giữ trong 5 phút.
    """Bước 3-5 của Basic Flow: Khách chọn slot -> kiểm tra -> giữ 5 phút.

    # Mô tả trường hợp slot trống được chuyển sang Đang giữ chỗ và tạo bản ghi GiuCho.
    - Slot 'Lịch trống'            -> thành 'Đang giữ chỗ', tạo một dòng GIUCHO (5 phút).
    # Mô tả trường hợp khách chọn lại slot mình đang giữ: dùng lại lượt cũ, không cộng thêm 5 phút.
    - Khách đang giữ đúng slot này -> trả lại lượt cũ, KHÔNG gia hạn (tránh giữ chỗ vô hạn).
    # Mô tả trường hợp khách chuyển sang slot khác: giải phóng slot cũ rồi giữ slot mới.
    - Khách đang giữ slot khác     -> (3a) nhả slot cũ về 'Lịch trống', ghi nhận slot mới.
      # Nêu quy tắc mỗi khách chỉ có tối đa một lượt giữ đang hoạt động.
      Mỗi khách chỉ có tối đa MỘT lượt đang giữ.
    # Nêu nguyên tắc transaction: nếu thao tác thất bại thì không để lại thay đổi dở dang.
    Mọi thứ trong một transaction: lỗi ở đâu thì không đổi gì (slot cũ của khách vẫn được giữ).

    # Docstring mô tả giá trị trả về khi thành công và loại lỗi nghiệp vụ khi thất bại.
    Trả về đối tượng GiuCho. Báo GiuChoLoi (có .thong_bao) khi:
      # Liệt kê các nhóm lỗi mà hàm có thể báo cho view xử lý.
      slot không còn khả dụng (4a), lỗi hệ thống (4b), hoặc người dùng không phải Khách hàng."""
    # Kiểm tra vai trò của người yêu cầu trước khi thực hiện giữ chỗ.
    if not _la_khach_hang(khach_hang):
        # Nếu không phải Khách hàng, phát sinh lỗi kèm thông báo phù hợp.
        raise GiuChoLoi(TB_KHONG_PHAI_KHACH)

    # Bắt đầu khối try để chuyển các lỗi kỹ thuật thành lỗi nghiệp vụ dễ hiển thị.
    try:
        # Giải phóng các lượt đã hết hạn trước để slot vừa được trả lại có thể được chọn.
        giai_phong_giu_cho_het_han()          # nhả slot quá hạn trước, để slot đó chọn được lại
        # Mở transaction bao trọn quá trình đổi slot cũ và giữ slot mới.
        with transaction.atomic():
            # Khóa dòng slot: hai khách bấm cùng lúc thì lần lượt từng người (BR4.1-2).
            # Bắt riêng lỗi khi tìm slot theo mã.
            try:
                # Lấy slot cần giữ và khóa bản ghi để tránh hai khách cùng giữ một slot tại cùng thời điểm.
                lich = LichKhaDung.objects.select_for_update().get(pk=ma_lich)
            # Bắt trường hợp mã lịch không tồn tại trong database.
            except LichKhaDung.DoesNotExist:
                # Chuyển lỗi không tìm thấy thành thông báo slot không còn khả dụng.
                raise GiuChoLoi(TB_SLOT_KHONG_KHA_DUNG)

            # Nhiếp ảnh gia bị khóa / hồ sơ không còn công khai: không giữ chỗ được nữa (kể cả khi Khách đang giữ đúng slot này).
            if not nhiep_anh_gia_cong_khai().filter(pk=lich.MaNhiepAnhGia_id).exists():
                raise GiuChoLoi(TB_NAG_KHONG_NHAN_BOOKING)

            # Ghi nhận thời điểm hiện tại để kiểm tra hạn của lượt giữ cũ.
            bay_gio = timezone.now()

            # Chú thích cho thao tác lấy các lượt đang giữ của chính khách hàng.
            # Các lượt đang giữ của chính khách này.
            # Truy vấn các lượt giữ và khóa các bản ghi tương ứng để tránh cập nhật đồng thời.
            luot_cu = list(GiuCho.objects.select_for_update()
                           # Chỉ lấy những lượt thuộc khách hàng hiện tại và vẫn ở trạng thái Đang giữ chỗ.
                           .filter(MaKhachHang=khach_hang, TrangThai=TrangThaiGiuCho.DANG_GIU))
            # Duyệt qua các lượt giữ hiện tại của khách.
            for cu in luot_cu:
                # Kiểm tra lượt đang giữ có phải đúng slot vừa chọn và vẫn còn hạn hay không.
                if cu.MaLich_id == lich.pk and cu.ThoiDiemHetHan > bay_gio:
                    # Nếu đúng, trả lại lượt hiện tại để không tạo lượt mới hoặc gia hạn thời gian.
                    return cu                 # đang giữ đúng slot này và còn hạn: dùng lại

            # Chú thích bước kiểm tra trạng thái của slot mà khách muốn chọn.
            # 4. Kiểm tra trạng thái slot.
            # Kiểm tra slot có đang ở trạng thái Lịch trống hay không.
            if lich.TrangThai != TrangThaiSlot.TRONG:
                # Nếu slot không trống, báo lỗi vì có thể đã được người khác giữ hoặc đặt.
                raise GiuChoLoi(TB_SLOT_KHONG_KHA_DUNG)       # 4a: người khác giữ/đặt rồi

            # 3a. Chọn slot khác: nhả slot cũ của chính khách này.
            # Bắt lỗi trong quá trình giải phóng slot cũ của khách.
            try:
                # Duyệt từng lượt giữ cũ của khách hàng.
                for cu in luot_cu:
                    # Kết thúc lượt giữ cũ, đồng thời trả slot cũ về lịch trống.
                    _ket_thuc_luot_giu(cu)
            # Nếu không thể giải phóng slot cũ, hủy toàn bộ transaction để không mất lượt giữ hiện tại.
            except ValidationError:               # slot cũ không nhả được: huỷ cả thao tác, khách giữ nguyên slot cũ
                # Ghi log lỗi và mã khách hàng để phục vụ kiểm tra.
                logger.exception('giu_cho_slot: không nhả được slot cũ (khách %s)', khach_hang.pk)
                # Thông báo lỗi hệ thống cho view nếu không thể giải phóng slot cũ.
                raise GiuChoLoi(TB_LOI_HE_THONG)

            # 5. Đổi slot -> 'Đang giữ chỗ' bằng hàm của Khoa. Hàm này tự chặn slot đã qua giờ bắt đầu
            #    và dùng UPDATE có điều kiện nên nếu có người nhanh tay hơn thì báo lỗi.
            # Bắt lỗi khi chuyển trạng thái slot mới sang Đang giữ chỗ.
            try:
                # Gọi service dùng chung của module schedule để chuyển slot sang Đang giữ chỗ.
                doi_trang_thai_khung_gio(lich, TrangThaiSlot.DANG_GIU)
            # Bắt lỗi nếu service không cho phép đổi trạng thái, ví dụ slot không còn hợp lệ.
            except ValidationError:
                # Chuyển lỗi đó thành thông báo slot không còn khả dụng.
                raise GiuChoLoi(TB_SLOT_KHONG_KHA_DUNG)

            # Chú thích phần tạo bản ghi lưu thông tin lượt giữ chỗ.
            # Ghi lượt giữ chỗ. Đặt sẵn giờ hết hạn = giờ giữ + 5 phút; gọi full_clean()
            # Nhắc rằng full_clean() cần được gọi chủ động để chạy kiểm tra model trước khi lưu.
            # theo ghi chú trong bookings/models.py (clean() chỉ chạy khi mình gọi).
            # Tạo đối tượng GiuCho và gắn khách hàng, slot cùng thời điểm bắt đầu giữ.
            giu_cho = GiuCho(MaKhachHang=khach_hang, MaLich=lich, ThoiDiemGiu=bay_gio,
                             # Tính thời điểm hết hạn bằng thời điểm bắt đầu cộng thời lượng giữ chỗ đã cấu hình.
                             ThoiDiemHetHan=bay_gio + THOI_GIAN_GIU_CHO,
                             # Đặt trạng thái ban đầu của lượt giữ là Đang giữ chỗ.
                             TrangThai=TrangThaiGiuCho.DANG_GIU)
            # Bắt lỗi riêng cho bước kiểm tra và lưu bản ghi GiuCho.
            try:
                # Tạo savepoint bên trong transaction lớn để nếu lưu lỗi có thể rollback phần này.
                with transaction.atomic():    # savepoint riêng để bắt IntegrityError mà không hỏng transaction ngoài
                    # Chạy các kiểm tra hợp lệ của model trước khi ghi vào database.
                    giu_cho.full_clean()
                    # Lưu bản ghi lượt giữ chỗ vào database.
                    giu_cho.save()
            # Bắt lỗi dữ liệu không hợp lệ hoặc vi phạm ràng buộc duy nhất khi lưu.
            except (ValidationError, IntegrityError):
                # Chú thích nguyên nhân thường gặp: một slot không được có nhiều lượt giữ đang hoạt động.
                # ràng buộc "mỗi slot một lượt đang giữ" (BR4.1-2) chặn lại
                # Báo slot không còn khả dụng nếu dữ liệu không vượt qua kiểm tra hoặc ràng buộc database.
                raise GiuChoLoi(TB_SLOT_KHONG_KHA_DUNG)
            # Trả về đối tượng GiuCho vừa được tạo khi giữ chỗ thành công.
            return giu_cho
    # Bắt lỗi nghiệp vụ đã được chủ động phát sinh trong hàm.
    except GiuChoLoi:
        # Ném lại lỗi để lớp view nhận và hiển thị đúng thông báo ban đầu.
        raise
    # Bắt lỗi database để xử lý trường hợp hệ thống không thể đọc hoặc ghi dữ liệu.
    except DatabaseError:                     # 4b: không đọc/ghi được database
        # Ghi lại chi tiết lỗi cùng mã khách và mã slot.
        logger.exception('giu_cho_slot: lỗi hệ thống (khách %s, slot %s)', khach_hang.pk, ma_lich)
        # Chuyển lỗi database thành thông báo chung, tránh hiển thị chi tiết kỹ thuật cho người dùng.
        raise GiuChoLoi(TB_LOI_HE_THONG)


# Định nghĩa hàm cho Khách chủ động bỏ lượt giữ chỗ (bấm "Chọn khung giờ khác" hoặc rời khỏi trang đặt lịch).
def huy_giu_cho(khach_hang, ma_giu_cho):
    """Khách chủ động bỏ lượt giữ: lượt -> 'Hết hạn', slot -> 'Lịch trống' ngay, không đợi hết 5 phút.
    Chỉ nhả lượt CỦA CHÍNH KHÁCH và còn 'Đang giữ chỗ' (đã gửi Booking = 'Đã hoàn tất' thì không đụng vào).
    Trả True nếu đã nhả; False nếu không có gì để nhả hoặc có lỗi (không báo lỗi ra ngoài: gọi nhiều lần vẫn an toàn)."""
    try:
        with transaction.atomic():
            giu_cho = (GiuCho.objects.select_for_update()
                       .filter(pk=ma_giu_cho, MaKhachHang=khach_hang, TrangThai=TrangThaiGiuCho.DANG_GIU).first())
            if giu_cho is None:
                return False
            return _ket_thuc_luot_giu(giu_cho)
    except (ValidationError, DatabaseError):
        logger.exception('huy_giu_cho: không nhả được lượt %s (khách %s)', ma_giu_cho, khach_hang.pk)
        return False


# Định nghĩa hàm UC4.1 cung cấp cho UC4.2 để xác nhận khách gửi Booking trong thời hạn giữ chỗ.
def hoan_tat_giu_cho(khach_hang, ma_giu_cho):
    # Docstring nhấn mạnh hàm phải nằm cùng transaction với thao tác tạo Booking.
    """DÀNH CHO UC4.2 (Gửi yêu cầu Booking): gọi trong cùng transaction với việc tạo Booking.

    # Mô tả kết quả khi khách gửi Booking trước khi hết hạn: lượt giữ chuyển sang Đã hoàn tất Booking.
    Lượt giữ còn hạn -> 'Đã hoàn tất Booking'. Slot vẫn ở 'Đang giữ chỗ' (đã gửi Booking chưa chốt,
    # Giải thích slot vẫn giữ trạng thái Đang giữ chỗ trong khi Booking chờ được xác nhận; nếu quá hạn thì giải phóng.
    đúng chú thích TrangThaiSlot.DANG_GIU). Quá 5 phút -> nhả slot, báo TB_HET_HAN.
    # Nêu đối tượng được trả về khi hoàn tất thành công.
    Trả về đối tượng GiuCho."""
    # Mở transaction để khóa và cập nhật lượt giữ an toàn.
    with transaction.atomic():
        # Truy vấn lượt giữ và khóa bản ghi trước khi kiểm tra, cập nhật.
        giu_cho = (GiuCho.objects.select_for_update()
                   # Chỉ lấy lượt có đúng mã được gửi và thuộc về khách hàng hiện tại.
                   .filter(pk=ma_giu_cho, MaKhachHang=khach_hang).first())
        # Kiểm tra có tìm thấy lượt giữ tương ứng hay không.
        if giu_cho is None:
            # Nếu không tìm thấy, báo lỗi không tồn tại lượt giữ.
            raise GiuChoLoi('Không tìm thấy lượt giữ chỗ.')
        # Kiểm tra lượt còn ở trạng thái Đang giữ chỗ và thời điểm hết hạn vẫn ở tương lai.
        if giu_cho.TrangThai == TrangThaiGiuCho.DANG_GIU and giu_cho.ThoiDiemHetHan > timezone.now():
            # Đổi trạng thái lượt giữ thành Đã hoàn tất Booking vì khách đã gửi yêu cầu đúng hạn.
            giu_cho.TrangThai = TrangThaiGiuCho.DA_HOAN_TAT        # kịp 5 phút
            # Chỉ lưu trường TrangThai để tránh cập nhật các trường không liên quan.
            giu_cho.save(update_fields=['TrangThai'])
            # Trả về lượt giữ sau khi hoàn tất.
            return giu_cho
        # Nếu lượt vẫn đang giữ nhưng đã quá hạn, cần giải phóng ngay.
        if giu_cho.TrangThai == TrangThaiGiuCho.DANG_GIU:           # quá 5 phút mà chưa ai nhả: nhả ngay
            # Kết thúc lượt giữ và trả slot về lịch trống.
            _ket_thuc_luot_giu(giu_cho)
    # Báo lỗi NGOÀI khối atomic: nếu raise bên trong thì việc nhả slot ở trên bị rollback theo.
    # Phát sinh lỗi hết hạn sau khi ra khỏi transaction để thao tác giải phóng ở trên không bị rollback.
    raise GiuChoLoi(TB_HET_HAN)


# ---------------------------------------------------------------------
# PHẦN 3: VIEW
# ---------------------------------------------------------------------
# Định nghĩa decorator kiểm tra quyền truy cập của các view chỉ dành cho Khách hàng.
def khach_hang_required(view):
    # Docstring mô tả: chưa đăng nhập thì chuyển đến trang login; sai vai trò thì trả lỗi 403.
    """Chỉ cho Khách hàng đã đăng nhập: chưa đăng nhập -> trang đăng nhập (kèm ?next=); sai vai trò -> 403.

    VÌ SAO KHÔNG DÙNG accounts.permissions.chi_khach_hang (đã đối chiếu bằng cách chạy cả hai):
      - GIỐNG: chưa đăng nhập -> cùng chuyển tới /dang-nhap/?next=<đường dẫn đầy đủ gồm query>; Khách hàng -> vào được;
        Nhiếp ảnh gia / Quản trị viên / superuser thường -> 403.
      - KHÁC: cách xác định "là Khách hàng". chi_khach_hang dùng lay_vai_tro() (ưu tiên Quản trị > Nhiếp ảnh gia > Khách hàng,
        và coi tài khoản CHƯA CÓ NHÓM là Khách hàng). Bản này dùng _la_khach_hang(): phải thuộc Group "Khách hàng" - đúng quy tắc
        mà GiuCho.clean() và giu_cho_slot() đang áp dụng. Hệ quả:
            tài khoản chưa có nhóm            -> bản này 403,  chi_khach_hang cho qua
            thuộc cả Khách hàng và Nhiếp ảnh gia, hoặc superuser + nhóm Khách hàng -> bản này cho qua, chi_khach_hang 403
      Đổi sang chi_khach_hang thì tài khoản chưa có nhóm vào được trang lịch rồi mới bị từ chối ở bước chọn slot.
      Test ghim hành vi: test_giu_cho.test_tai_khoan_chua_co_nhom_bi_chan. Muốn thống nhất cả dự án thì cần nhóm thống nhất
      "chưa có nhóm" là gì (xem lay_vai_tro) trước, rồi mới xóa bản này."""
    # Dùng wraps để giữ metadata của view gốc khi bọc bằng decorator.
    @wraps(view)
    # Định nghĩa hàm wrapper sẽ chạy trước view thật.
    def wrapper(request, *args, **kwargs):
        # Kiểm tra người dùng đã đăng nhập hay chưa.
        if not request.user.is_authenticated:
            # Bắt lỗi nếu tên URL login chưa được khai báo trong dự án.
            try:
                # Thử lấy đường dẫn trang đăng nhập theo tên URL login.
                trang_dang_nhap = reverse('login')      # tên URL 'login' do Phanh (accounts) đặt, xem core/navigation.py
            # Nếu không tìm thấy tên URL login thì chuyển sang cấu hình dự phòng.
            except NoReverseMatch:
                # Lấy đường dẫn đăng nhập từ cấu hình Django.
                trang_dang_nhap = settings.LOGIN_URL    # chưa có thì dùng LOGIN_URL, không làm sập trang
            # Chuyển người dùng đến trang đăng nhập và lưu URL hiện tại vào tham số next.
            return redirect_to_login(request.get_full_path(), trang_dang_nhap)
        # Nếu đã đăng nhập, tiếp tục kiểm tra tài khoản có đúng vai trò Khách hàng không.
        if not _la_khach_hang(request.user):
            # Nếu sai vai trò, từ chối truy cập bằng lỗi HTTP 403.
            raise PermissionDenied(TB_KHONG_PHAI_KHACH)
        # Nếu đủ điều kiện, gọi view gốc với request và các tham số ban đầu.
        return view(request, *args, **kwargs)
    # Trả về wrapper để decorator áp dụng cho view.
    return wrapper


# Định nghĩa hàm kiểm tra "gói chọn sẵn" mà khách mang từ hồ sơ Nhiếp ảnh gia (POST 'goi' hoặc ?goi=).
def goi_chon_san_hop_le(ma_nhiep_anh_gia, gia_tri):
    """Trả về GoiDichVu nếu gia_tri là mã của một gói 'Đang áp dụng' thuộc ĐÚNG Nhiếp ảnh gia của slot; ngược lại None.
    Giá trị đến từ trình duyệt (có thể trống, không phải số, hoặc bị sửa tay) nên luôn kiểm tra lại, không tin mù quáng.
    Dùng ở chon_slot, man_hinh_giu_cho và gui_booking (UC4.2). Gói có vừa khung giờ hay không do UC4.2 kiểm tra."""
    # Trống hoặc không phải số nguyên dương hợp lý thì coi như không chọn gói.
    try:
        ma_goi = int(str(gia_tri or '').strip())
    except ValueError:
        return None
    # Chặn số quá lớn để database không báo lỗi tràn số.
    if not 0 < ma_goi < 2 ** 31:
        return None
    # Chỉ nhận gói Đang áp dụng của đúng Nhiếp ảnh gia sở hữu slot (gói của người khác hoặc gói đã ngừng/ẩn thì bỏ qua).
    return (GoiDichVu.objects.select_related('MaLoaiHinh')
            .filter(pk=ma_goi, MaNhiepAnhGia_id=ma_nhiep_anh_gia, TrangThai=TrangThaiGoi.DANG_AP_DUNG).first())


# Định nghĩa hàm tạo URL chuyển sang chức năng gửi Booking của UC4.2.
def _url_gui_booking(giu_cho, goi=None):
    # Docstring giải thích URL cần có tên gui_booking và nhận mã lượt giữ chỗ.
    """Link sang UC4.2 'Gửi yêu cầu Booking'. Khi bạn viết UC4.2, đặt tên URL đó là 'gui_booking'
    # Nếu chưa có URL UC4.2 thì hàm sẽ trả None để giao diện không tạo liên kết sai.
    (nhận ma_giu_cho) thì nút 'Tiếp tục' tự hiện; chưa có thì trả None."""
    # Bắt lỗi nếu Django không tìm thấy URL theo tên.
    try:
        # Tạo URL gui_booking và truyền mã lượt giữ chỗ vào tham số ma_giu_cho.
        url = reverse('gui_booking', kwargs={'ma_giu_cho': giu_cho.pk})
        # Có gói chọn sẵn (khách bấm "Chọn gói" ở hồ sơ Nhiếp ảnh gia) thì kèm ?goi=<mã gói> để form chọn sẵn gói đó.
        return f'{url}?{urlencode({"goi": goi.pk})}' if goi is not None else url
    # Bắt trường hợp route gui_booking chưa được khai báo.
    except NoReverseMatch:
        # Trả None để báo rằng hiện chưa có đường dẫn gửi Booking.
        return None


# Định nghĩa hàm tạo đường dẫn quay lại trang lịch của nhiếp ảnh gia.
def _ve_trang_lich(ma_nhiep_anh_gia):
    # Quay lại trang lịch của nhiếp ảnh gia; thiếu mã thì về trang chủ.
    # Thử chuyển mã nhiếp ảnh gia sang số nguyên và tạo redirect đến trang lịch.
    try:
        # Chuyển người dùng về trang lịch của nhiếp ảnh gia tương ứng.
        ma = int(ma_nhiep_anh_gia)
        # Nhiếp ảnh gia không còn công khai thì trang lịch trả 404 -> đưa Khách về trang tìm kiếm.
        if not nhiep_anh_gia_cong_khai().filter(pk=ma).exists():
            return redirect('search')
        return redirect('lich_chon_slot', ma_nhiep_anh_gia=ma)
    # Bắt lỗi mã không hợp lệ hoặc tên URL lịch chưa tồn tại.
    except (TypeError, ValueError, NoReverseMatch):
        # Nếu không thể về trang lịch, thử chuyển về trang chủ.
        try:
            # Chuyển hướng đến URL có tên home.
            return redirect('home')
        # Bắt trường hợp dự án chưa khai báo URL home.
        except NoReverseMatch:
            # Dùng dấu / làm đường dẫn dự phòng cuối cùng.
            return redirect('/')


# Áp dụng kiểm tra quyền Khách hàng cho view hiển thị lịch.
@khach_hang_required
# Chỉ cho phép request GET vì view này chỉ đọc và hiển thị dữ liệu.
@require_GET
# Định nghĩa view trang lịch của một nhiếp ảnh gia, nhận mã nhiếp ảnh gia từ URL.
def trang_lich_nhiep_anh_gia(request, ma_nhiep_anh_gia):
    # Docstring mô tả view hiển thị các slot còn trống theo đặc tả UC4.1.
    """Bước 1-2: trang lịch công khai, liệt kê các slot 'Lịch trống' của một nhiếp ảnh gia."""
    # Tìm hồ sơ nhiếp ảnh gia và tải sẵn tài khoản liên quan để giảm truy vấn.
    nag = get_object_or_404(nhiep_anh_gia_cong_khai().select_related('MaTaiKhoan'), pk=ma_nhiep_anh_gia)   # chỉ hồ sơ 'Đã duyệt' và tài khoản chưa bị khóa
    # Lấy lượt giữ chỗ hiện tại của khách để hiển thị thông tin khách đang giữ slot nào.
    giu_cho_hien_tai = lay_giu_cho_hien_tai(request.user)   # (đã nhả slot quá hạn) để hiện banner "bạn đang giữ"

    # Chú thích phần nhóm các slot theo ngày để giao diện dễ hiển thị.
    # Gom slot theo ngày: [(ngày, [slot, slot...]), ...]
    # Tạo OrderedDict để giữ thứ tự ngày khi gom các slot.
    theo_ngay = OrderedDict()
    # Duyệt danh sách khung giờ còn trống của nhiếp ảnh gia trong số ngày đã cấu hình.
    for slot in khung_gio_trong(nag, so_ngay=SO_NGAY_HIEN_THI_LICH):
        # Thêm slot vào danh sách tương ứng với ngày; nếu ngày chưa có thì tạo danh sách mới.
        theo_ngay.setdefault(slot.Ngay, []).append(slot)

    # Render template trang chọn slot và truyền dữ liệu cần thiết cho giao diện.
    return render(request, 'bookings/lich_chon_slot.html', {
        # Truyền đối tượng hồ sơ nhiếp ảnh gia sang template.
        'nag': nag,
        # Truyền tên hiển thị của nhiếp ảnh gia; nếu chưa có họ tên thì dùng username.
        'ten_nag': nag.MaTaiKhoan.get_full_name() or nag.MaTaiKhoan.username,
        # Truyền danh sách slot đã được nhóm theo ngày.
        'lich_theo_ngay': list(theo_ngay.items()),
        # Truyền lượt giữ chỗ hiện tại của khách để giao diện có thể hiển thị banner.
        'giu_cho_hien_tai': giu_cho_hien_tai,
        # Truyền số ngày được hiển thị trên trang lịch.
        'so_ngay': SO_NGAY_HIEN_THI_LICH,
        # Truyền số phút giữ chỗ lấy từ THOI_GIAN_GIU_CHO để câu "giữ chỗ cho bạn N phút" tự đổi theo khi đổi hằng số.
        'so_phut_giu': THOI_GIAN_GIU_CHO.total_seconds() / 60,
    # Kết thúc dictionary dữ liệu và trả về trang HTML đã render.
    })


# Áp dụng kiểm tra quyền Khách hàng cho view chọn slot.
@khach_hang_required
# Chỉ cho phép POST vì đây là thao tác làm thay đổi trạng thái dữ liệu.
@require_POST
# Định nghĩa view xử lý khi khách bấm chọn một slot.
def chon_slot(request, ma_lich):
    # Docstring mô tả: giữ chỗ thành công thì chuyển khách đến màn hình đếm ngược.
    """Bước 3: Khách bấm chọn một slot. Thành công -> sang màn hình đếm ngược (bước 6).
    Form ở hồ sơ Nhiếp ảnh gia có thể gửi thêm 'goi' (mã gói, có thể trống): chỉ nhận nếu là gói 'Đang áp dụng' của đúng
    Nhiếp ảnh gia của slot, rồi chuyển tiếp ?goi=<mã> qua màn hình giữ chỗ tới UC4.2 để form chọn sẵn gói. Không có thì như cũ."""
    # Lấy mã nhiếp ảnh gia từ dữ liệu form để biết trang lịch cần quay lại nếu xảy ra lỗi.
    ma_nag = request.POST.get('ma_nhiep_anh_gia')        # form trên trang lịch gửi kèm để biết đường quay lại
    # Bắt lỗi nghiệp vụ trong quá trình giữ slot.
    try:
        # Gọi hàm nghiệp vụ chính để kiểm tra và giữ slot cho người dùng hiện tại.
        giu_cho = giu_cho_slot(request.user, ma_lich)
    # Nếu hàm nghiệp vụ báo lỗi, nhận nội dung lỗi trong biến loi.
    except GiuChoLoi as loi:                              # 4a / 4b: báo lỗi rồi kết thúc UC
        # Đưa thông báo lỗi vào hệ thống messages để giao diện hiển thị.
        messages.error(request, loi.thong_bao)
        # Chuyển khách quay lại trang lịch của nhiếp ảnh gia.
        return _ve_trang_lich(ma_nag)
    # Nhiếp ảnh gia lấy từ chính slot (không tin mã Nhiếp ảnh gia hay mã gói do trình duyệt gửi) để kiểm tra gói chọn sẵn.
    goi = goi_chon_san_hop_le(giu_cho.MaLich.MaNhiepAnhGia_id, request.POST.get('goi'))
    # Nếu giữ thành công, chuyển đến màn hình giữ chỗ với mã lượt giữ vừa tạo hoặc tìm được (kèm ?goi= nếu có gói hợp lệ).
    url = reverse('man_hinh_giu_cho', kwargs={'ma_giu_cho': giu_cho.pk})
    return redirect(f'{url}?{urlencode({"goi": goi.pk})}' if goi is not None else url)


# Áp dụng kiểm tra quyền Khách hàng cho view hủy giữ chỗ.
@khach_hang_required
# Chỉ cho phép POST vì đây là thao tác làm thay đổi trạng thái dữ liệu.
@require_POST
# Định nghĩa view nhả lượt giữ chỗ: dùng cho nút "Chọn khung giờ khác" và cho sendBeacon khi Khách rời trang.
def huy_giu_cho_view(request, ma_giu_cho):
    """Khách bấm "Chọn khung giờ khác"/"Hủy giữ chỗ" -> nhả slot rồi về trang lịch của Nhiếp ảnh gia.
    nha_giu_cho.js gửi thêm nhanh=1 (sendBeacon khi rời trang) -> chỉ trả 204, không chuyển hướng, không thông báo."""
    giu_cho = get_object_or_404(GiuCho.objects.select_related('MaLich'),
                                pk=ma_giu_cho, MaKhachHang=request.user)   # chỉ thao tác với lượt của chính mình
    da_nha = huy_giu_cho(request.user, giu_cho.pk)
    if request.POST.get('nhanh') == '1':
        return HttpResponse(status=204)
    if da_nha:
        messages.info(request, 'Đã hủy giữ chỗ. Khung giờ đã được trả về lịch trống.')
    return _ve_trang_lich(giu_cho.MaLich.MaNhiepAnhGia_id)


# Áp dụng kiểm tra quyền Khách hàng cho màn hình giữ chỗ.
@khach_hang_required
# Chỉ cho phép GET vì view chỉ hiển thị thông tin.
@require_GET
# Định nghĩa view hiển thị thông tin slot đang giữ và bộ đếm ngược.
def man_hinh_giu_cho(request, ma_giu_cho):
    # Docstring mô tả nội dung màn hình và nút tiếp tục sang UC4.2.
    """Bước 6: màn hình hiện slot đang giữ + đếm ngược 5 phút (và nút sang Gửi yêu cầu Booking)."""
    # Giải phóng các lượt giữ đã quá hạn trước khi tải dữ liệu hiển thị.
    giai_phong_giu_cho_het_han()
    # Tìm lượt giữ theo điều kiện; nếu không có thì Django trả lỗi 404.
    giu_cho = get_object_or_404(
        # Tải sẵn slot, nhiếp ảnh gia và tài khoản liên quan để dùng ở các dòng dưới.
        GiuCho.objects.select_related('MaLich__MaNhiepAnhGia__MaTaiKhoan'),
        # Chỉ cho phép khách hiện tại xem lượt giữ thuộc chính tài khoản của mình.
        pk=ma_giu_cho, MaKhachHang=request.user)          # chỉ xem được lượt của chính mình
    # Lấy đối tượng slot từ lượt giữ chỗ.
    lich = giu_cho.MaLich
    # Lấy hồ sơ nhiếp ảnh gia gắn với slot đó.
    nag = lich.MaNhiepAnhGia
    # Tính số giây còn lại để truyền sang giao diện.
    con_lai = so_giay_con_lai(giu_cho)
    # Gói chọn sẵn đi từ chon_slot qua ?goi=; URL do người dùng sửa được nên kiểm tra lại trước khi chuyển tiếp sang UC4.2.
    goi = goi_chon_san_hop_le(nag.pk, request.GET.get('goi'))
    # Render template màn hình giữ chỗ và truyền dữ liệu cần thiết.
    return render(request, 'bookings/giu_cho.html', {
        # Truyền đối tượng lượt giữ chỗ sang template.
        'giu_cho': giu_cho,
        # Truyền thông tin slot đã được giữ.
        'lich': lich,
        # Truyền tên nhiếp ảnh gia để hiển thị trên màn hình.
        'ten_nag': nag.MaTaiKhoan.get_full_name() or nag.MaTaiKhoan.username,
        # Truyền số giây còn lại cho bộ đếm ngược.
        'con_lai_giay': con_lai,
        # Truyền tổng thời lượng giữ chỗ tính bằng giây để giao diện biết mốc ban đầu.
        'tong_giay': int(THOI_GIAN_GIU_CHO.total_seconds()),
        # Cho template biết lượt giữ còn thời gian hay không.
        'dang_giu': con_lai > 0,                                              # còn đếm ngược
        # Cho template biết lượt giữ đã hết hạn hay chưa.
        'da_het_han': giu_cho.TrangThai == TrangThaiGiuCho.HET_HAN,           # ngoại lệ 5b
        # Cho template biết lượt giữ đã được hoàn tất qua bước gửi Booking hay chưa.
        'da_hoan_tat': giu_cho.TrangThai == TrangThaiGiuCho.DA_HOAN_TAT,      # đã gửi Booking kịp hạn
        # Truyền URL sang chức năng gửi Booking; nếu route chưa có thì giá trị có thể là None.
        'url_gui_booking': _url_gui_booking(giu_cho, goi),
        # Truyền URL quay lại trang lịch của nhiếp ảnh gia.
        'url_lich': reverse('lich_chon_slot', kwargs={'ma_nhiep_anh_gia': nag.pk}),
        # Truyền URL API để JavaScript hỏi thời gian giữ chỗ còn lại.
        'url_trang_thai': reverse('trang_thai_giu_cho', kwargs={'ma_giu_cho': giu_cho.pk}),
        # Truyền nội dung thông báo hết hạn để giao diện hiển thị.
        'TB_HET_HAN': TB_HET_HAN,
    # Kết thúc dữ liệu truyền vào template và trả về trang HTML.
    })


# Áp dụng kiểm tra quyền Khách hàng cho API trạng thái giữ chỗ.
@khach_hang_required
# Chỉ cho phép GET vì API này chỉ đọc trạng thái.
@require_GET
# Định nghĩa API trả trạng thái lượt giữ chỗ cho bộ đếm ngược.
def trang_thai_giu_cho(request, ma_giu_cho):
    # Docstring giải thích API lấy thời gian từ server thay vì tin đồng hồ trên máy khách.
    """API JSON cho bộ đếm ngược: trả số giây còn lại thật của server (không tin đồng hồ máy khách).
    # Khi JavaScript gọi API, hệ thống kiểm tra và giải phóng các lượt đã quá hạn.
    Khi hết giờ, JS gọi lại đây; việc nhả slot xảy ra ở dòng giai_phong_giu_cho_het_han()."""
    # Giải phóng lượt hết hạn trước khi trả dữ liệu trạng thái.
    giai_phong_giu_cho_het_han()
    # Lấy lượt giữ theo mã và đảm bảo nó thuộc về người dùng đang đăng nhập.
    giu_cho = get_object_or_404(GiuCho, pk=ma_giu_cho, MaKhachHang=request.user)
    # Tính số giây còn lại dựa trên thời gian server.
    con_lai = so_giay_con_lai(giu_cho)
    # Tạo phản hồi JSON để JavaScript đọc.
    return JsonResponse({
        # Trả trạng thái hiện tại của lượt giữ.
        'trang_thai': giu_cho.TrangThai,
        # Trả số giây còn lại.
        'con_lai_giay': con_lai,
        # Trả True nếu lượt giữ đã hết hạn, ngược lại là False.
        'het_han': giu_cho.TrangThai == TrangThaiGiuCho.HET_HAN,
        # Trả thông báo hết hạn nếu đã hết hạn; nếu chưa thì trả chuỗi rỗng.
        'thong_bao': TB_HET_HAN if giu_cho.TrangThai == TrangThaiGiuCho.HET_HAN else '',
    # Kết thúc dữ liệu JSON và trả phản hồi cho trình duyệt.
    })


# ---------------------------------------------------------------------
# PHẦN 4: URL  (trong config/urls.py thêm:  path('bookings/', include('bookings.giu_cho')),)
# ---------------------------------------------------------------------
# Bắt đầu danh sách các URL thuộc module giữ chỗ.
urlpatterns = [
    # Khai báo URL xem lịch của một nhiếp ảnh gia; mã nhiếp ảnh gia được truyền qua URL.
    path('nhiep-anh-gia/<int:ma_nhiep_anh_gia>/lich/', trang_lich_nhiep_anh_gia, name='lich_chon_slot'),
    # Khai báo URL xử lý thao tác khách chọn slot; mã slot được truyền qua URL.
    path('giu-cho/chon/<int:ma_lich>/', chon_slot, name='chon_slot'),
    # Khai báo URL mở màn hình đếm ngược của một lượt giữ chỗ.
    path('giu-cho/<int:ma_giu_cho>/', man_hinh_giu_cho, name='man_hinh_giu_cho'),
    # Khai báo URL API trả trạng thái và thời gian còn lại của lượt giữ.
    path('giu-cho/<int:ma_giu_cho>/trang-thai/', trang_thai_giu_cho, name='trang_thai_giu_cho'),
    # Khai báo URL nhả lượt giữ chỗ (Khách chọn khung giờ khác hoặc rời trang đặt lịch).
    path('giu-cho/<int:ma_giu_cho>/huy/', huy_giu_cho_view, name='huy_giu_cho'),
# Đóng danh sách URL của module.
]
