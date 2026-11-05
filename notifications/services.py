# notifications/services.py - P2: hàm gửi thông báo dùng chung (Phanh)
# Các bạn khác import hàm ở đây để gửi thông báo khi có sự kiện (Booking mới, duyệt hồ sơ...)
import logging  # thư viện ghi log: để in cảnh báo ra Terminal khi có lỗi, thay vì làm sập web

from django.core.mail import send_mail  # hàm gửi email của Django (khi làm thử chỉ in ra Terminal, xem MAILERS trong settings.py)

from django.db import DatabaseError, transaction  # transaction.atomic: bọc thao tác lưu; DatabaseError: bắt lỗi DB để trang không sập
from django.db.models import Case, Count, IntegerField, Q, Value, When  # Count: đếm; Q: lọc OR/AND; Case/When/Value: xếp thứ tự có điều kiện (ghim sao)
from django.urls import NoReverseMatch, reverse  # reverse: đổi tên URL thành địa chỉ; NoReverseMatch: chưa có URL đó

from core.constants import DanhDauSao, TrangThaiDoc, TrangThaiGuiEmail, VaiTro  # hằng số trạng thái đọc, sao, kết quả gửi email và 3 vai trò (README: không tự gõ chữ tiếng Việt)
from core.navigation import get_role  # lấy vai trò của người dùng (Khách hàng / Nhiếp ảnh gia / Quản trị viên)
from notifications.models import ThongBao  # model bảng THONGBAO đã có sẵn trong notifications/models.py

logger = logging.getLogger(__name__)  # tạo bộ ghi log riêng cho file này


def gui_thong_bao(nguoi_nhan, tieu_de, noi_dung, booking=None):  # hàm chính: gửi 1 thông báo cho 1 người
    """Tạo thông báo 'Chưa đọc'. Trả về ThongBao nếu thành công, None nếu lỗi."""  # mô tả hàm
    if nguoi_nhan is None or getattr(nguoi_nhan, 'pk', None) is None:  # không có người nhận, hoặc User chưa lưu vào DB
        logger.warning('gui_thong_bao: thiếu người nhận (%r)', tieu_de)  # ghi cảnh báo để dễ tìm lỗi
        return None  # dừng, không tạo gì

    tieu_de = (tieu_de or '').strip()[:255]  # bỏ khoảng trắng thừa và cắt còn 255 ký tự (cột TieuDe tối đa 255)
    noi_dung = (noi_dung or '').strip()  # bỏ khoảng trắng thừa ở nội dung
    if not tieu_de or not noi_dung:  # tiêu đề hoặc nội dung rỗng thì không có gì để báo
        logger.warning('gui_thong_bao: thiếu tiêu đề hoặc nội dung')  # ghi cảnh báo
        return None  # dừng, không tạo gì

    try:  # thử lưu; nếu lỗi thì bắt lại, không để nghiệp vụ chính của bạn khác bị sập
        with transaction.atomic():  # savepoint riêng: lỗi ở đây không làm hỏng giao dịch của nơi gọi
            thong_bao = ThongBao.objects.create(  # INSERT một dòng mới vào bảng THONGBAO
                MaNguoiNhan=nguoi_nhan,  # người nhận thông báo
                MaBooking=booking,  # Booking liên quan (None nếu không có, cột cho phép NULL)
                TieuDe=tieu_de,  # tiêu đề đã làm sạch
                NoiDung=noi_dung,  # nội dung đã làm sạch
                TrangThaiDoc=TrangThaiDoc.CHUA_DOC,  # luôn bắt đầu ở trạng thái 'Chưa đọc'
            )  # NgayTao do Django tự điền (auto_now_add)
    except Exception:  # noqa: BLE001  # bắt mọi lỗi khi lưu (DB lỗi, dữ liệu sai...)
        logger.exception('gui_thong_bao: lưu thất bại (%s)', tieu_de)  # ghi log đầy đủ lỗi để sửa sau
        return None  # báo không tạo được nhưng không ném lỗi ra ngoài

    return thong_bao  # trả về thông báo vừa tạo để nơi gọi dùng nếu cần


def gui_thong_bao_nhieu_nguoi(ds_nguoi_nhan, tieu_de, noi_dung, booking=None):  # gửi cùng nội dung cho nhiều người
    """Ví dụ: báo cho tất cả Quản trị viên khi có hồ sơ mới. Trả về list ThongBao đã tạo."""  # mô tả hàm
    da_gui = set()  # tập các mã User đã gửi, để không gửi trùng một người hai lần
    ket_qua = []  # danh sách thông báo tạo thành công
    for user in ds_nguoi_nhan:  # duyệt từng người trong danh sách
        if user is None or user.pk in da_gui:  # bỏ qua giá trị rỗng hoặc người đã gửi rồi
            continue  # sang người tiếp theo
        da_gui.add(user.pk)  # ghi nhớ người này đã được xử lý
        thong_bao = gui_thong_bao(user, tieu_de, noi_dung, booking=booking)  # gửi cho từng người bằng hàm chính
        if thong_bao is not None:  # chỉ giữ lại những thông báo tạo thành công
            ket_qua.append(thong_bao)  # thêm vào danh sách kết quả
    return ket_qua  # trả về danh sách


def dem_chua_doc(user):  # đếm số thông báo chưa đọc của một người
    """Dùng cho số đỏ trên chuông ở đầu trang (header)."""  # mô tả hàm
    if user is None or not getattr(user, 'is_authenticated', False):  # chưa đăng nhập hoặc không có user
        return 0  # khách vãng lai không có thông báo
    return ThongBao.objects.filter(  # đếm trong bảng THONGBAO
        MaNguoiNhan=user,  # chỉ thông báo của người này
        TrangThaiDoc=TrangThaiDoc.CHUA_DOC,  # chỉ thông báo còn 'Chưa đọc'
    ).count()  # trả về số lượng



# =====================================================================
# P8 (UC9.1 và UC9.2): XEM VÀ ĐÁNH DẤU THÔNG BÁO
# Quy tắc chung: MỌI hàm dưới đây đều nhận user và chỉ đụng tới thông báo CỦA user đó.
# =====================================================================
LOC_TAT_CA = 'tat_ca'  # khóa nhóm "Tất cả" (dùng trên thanh địa chỉ ?loc=tat_ca)
LOC_CHUA_DOC = 'chua_doc'  # khóa nhóm "Chưa đọc"
LOC_SAO = 'sao'  # khóa nhóm "Đã đánh dấu sao"
NHAN_NHOM = {  # nhãn hiển thị của từng nhóm; thứ tự ở đây là thứ tự trong menu "Lọc thông báo"
    LOC_TAT_CA: 'Tất cả',  # nhóm 1
    LOC_CHUA_DOC: 'Chưa đọc',  # nhóm 2
    LOC_SAO: 'Đã đánh dấu sao',  # nhóm 3
}  # hết bảng nhãn nhóm
SO_DONG_MOI_TRANG = 10  # mỗi trang danh sách hiện tối đa 10 thông báo (phân trang chung của nhóm)
SO_THONG_BAO_TRONG_KHUNG = 4  # khung chuông thả xuống chỉ hiện 4 thông báo mới nhất (đúng wireframe)
DO_DAI_TU_KHOA_TOI_DA = 100  # tìm kiếm tối đa 100 ký tự, tránh chuỗi quá dài

# Tên URL trang chi tiết Booking theo vai trò. Muốn đổi tên URL của Tuyền thì CHỈ sửa ở đây.
URL_BOOKING_THEO_VAI_TRO = {
    VaiTro.NHIEP_ANH_GIA: 'chi_tiet_yeu_cau_booking',  # đã có trong bookings/tiep_nhan.py (nhận ma_booking)
    VaiTro.KHACH_HANG: 'chi_tiet_booking',  # Tuyền sẽ tạo khi làm UC4.7; chưa có thì link tạm là '#'
}  # Quản trị viên chưa có trang Booking nên không có link


def chuan_hoa_loc(loc):  # biến giá trị ?loc= người dùng gõ thành giá trị hợp lệ
    """Giá trị lạ (hoặc rỗng) thì dùng nhóm 'Tất cả'."""  # mô tả hàm
    return loc if loc in NHAN_NHOM else LOC_TAT_CA  # nằm trong 3 nhóm thì giữ, không thì về 'Tất cả'


def thong_bao_cua(nguoi_dung):  # bộ lọc gốc: chỉ thông báo của người này
    """Mọi truy vấn của P8 đều bắt đầu từ đây nên không thể lộ thông báo của người khác."""  # mô tả hàm
    return ThongBao.objects.filter(MaNguoiNhan=nguoi_dung)  # WHERE MaNguoiNhan = người này


def ghim_sao_len_dau(ds):  # xếp thứ tự dùng chung cho trang danh sách VÀ khung chuông
    """Có sao đứng trước, sau đó mới nhất trước. Một nơi duy nhất để hai màn hình không lệch nhau."""  # mô tả hàm
    return ds.annotate(thu_tu_sao=Case(  # cột tạm: 0 nếu đã đánh dấu sao, 1 nếu chưa
        When(DanhDauSao=DanhDauSao.DA_DANH_DAU, then=Value(0)),  # có sao -> 0
        default=Value(1), output_field=IntegerField()),  # còn lại -> 1
    ).order_by('thu_tu_sao', '-NgayTao', '-MaThongBao')  # sao lên đầu, rồi mới nhất trước


def lay_danh_sach(nguoi_dung, loc=LOC_TAT_CA, tu_khoa=''):  # danh sách cho trang SC9.1
    """Trả về QuerySet (chưa chạy truy vấn) đã lọc nhóm, tìm kiếm; thông báo có sao ghim lên đầu, sau đó mới nhất trước."""  # mô tả hàm
    ds = thong_bao_cua(nguoi_dung)  # bắt đầu từ thông báo của người này
    loc = chuan_hoa_loc(loc)  # làm sạch giá trị nhóm
    if loc == LOC_CHUA_DOC:  # nhóm "Chưa đọc"
        ds = ds.filter(TrangThaiDoc=TrangThaiDoc.CHUA_DOC)  # chỉ lấy dòng còn Chưa đọc
    elif loc == LOC_SAO:  # nhóm "Đã đánh dấu sao"
        ds = ds.filter(DanhDauSao=DanhDauSao.DA_DANH_DAU)  # chỉ lấy dòng đã gắn sao
    tu_khoa = (tu_khoa or '').strip()[:DO_DAI_TU_KHOA_TOI_DA]  # bỏ khoảng trắng thừa, cắt còn 100 ký tự
    if tu_khoa:  # có gõ từ khóa
        ds = ds.filter(Q(TieuDe__icontains=tu_khoa) | Q(NoiDung__icontains=tu_khoa))  # khớp tiêu đề HOẶC nội dung
    return ghim_sao_len_dau(ds)  # FR-38: có sao ghim lên đầu; trong mỗi nhóm thì mới nhất trước


def dem_theo_nhom(nguoi_dung):  # đếm số thông báo của 3 nhóm bằng ĐÚNG 1 câu truy vấn
    """Trả về dict {'tat_ca': n, 'chua_doc': n, 'sao': n}."""  # mô tả hàm
    ket_qua = thong_bao_cua(nguoi_dung).aggregate(  # gom đếm trong một lần chạy SQL
        tat_ca=Count('pk'),  # tổng số thông báo
        chua_doc=Count('pk', filter=Q(TrangThaiDoc=TrangThaiDoc.CHUA_DOC)),  # số dòng Chưa đọc
        sao=Count('pk', filter=Q(DanhDauSao=DanhDauSao.DA_DANH_DAU)),  # số dòng đã đánh dấu sao
    )  # hết aggregate
    return {khoa: ket_qua[khoa] or 0 for khoa in (LOC_TAT_CA, LOC_CHUA_DOC, LOC_SAO)}  # đảm bảo luôn là số nguyên


def lay_moi_nhat(nguoi_dung, so_luong=SO_THONG_BAO_TRONG_KHUNG):  # dữ liệu cho khung chuông thả xuống
    """Trả về list 4 thông báo đầu theo cùng thứ tự với trang danh sách: có sao lên đầu, rồi mới nhất."""  # mô tả hàm
    return list(ghim_sao_len_dau(thong_bao_cua(nguoi_dung))[:so_luong])  # cắt lấy 4 dòng đầu


def queryset_chi_tiet(nguoi_dung):  # nguồn dữ liệu cho trang chi tiết SC9.2
    """Dùng với get_object_or_404: thông báo của người khác sẽ thành 404, không lộ nội dung."""  # mô tả hàm
    return thong_bao_cua(nguoi_dung).select_related('MaBooking__MaGoi')  # nạp sẵn Booking và Gói để trang chi tiết không truy vấn thêm


def _cap_nhat(nguoi_dung, ma_thong_bao, **cot):  # hàm dùng chung: sửa cột của MỘT thông báo của người này
    """Trả về True nếu sửa được đúng 1 dòng; False nếu không có dòng (của người khác) hoặc DB lỗi."""  # mô tả hàm
    try:  # thử cập nhật; lỗi DB thì bắt lại để hiện hộp "Cập nhật không thành công"
        so_dong = thong_bao_cua(nguoi_dung).filter(pk=ma_thong_bao).update(**cot)  # UPDATE ... WHERE đúng chủ và đúng mã
    except DatabaseError:  # lỗi cơ sở dữ liệu
        logger.exception('thong_bao: cập nhật thất bại (mã %s)', ma_thong_bao)  # ghi log đầy đủ để sửa sau
        return False  # báo thất bại, không ném lỗi ra ngoài
    return so_dong == 1  # đúng 1 dòng bị sửa là thành công


def dat_trang_thai_doc(nguoi_dung, ma_thong_bao, da_doc):  # UC9.2: đổi Chưa đọc <-> Đã đọc
    """da_doc=True: Đã đọc; da_doc=False: Chưa đọc. Đặt thẳng giá trị đích nên bấm hai lần vẫn an toàn."""  # mô tả hàm
    trang_thai = TrangThaiDoc.DA_DOC if da_doc else TrangThaiDoc.CHUA_DOC  # chọn giá trị đích
    return _cap_nhat(nguoi_dung, ma_thong_bao, TrangThaiDoc=trang_thai)  # ghi vào DB


def dat_dau_sao(nguoi_dung, ma_thong_bao, co_sao):  # UC9.2: đánh dấu sao hoặc bỏ đánh dấu sao
    """co_sao=True: Đã đánh dấu sao; co_sao=False: Chưa đánh dấu sao."""  # mô tả hàm
    gia_tri = DanhDauSao.DA_DANH_DAU if co_sao else DanhDauSao.CHUA_DANH_DAU  # chọn giá trị đích
    return _cap_nhat(nguoi_dung, ma_thong_bao, DanhDauSao=gia_tri)  # ghi vào DB

def xoa_thong_bao(nguoi_dung, ma_thong_bao):  # UC9.2 bổ sung: xóa MỘT thông báo của người này
    """Trả về True nếu xóa được; False nếu không có dòng (của người khác) hoặc DB lỗi."""  # mô tả hàm
    try:  # thử xóa; lỗi DB thì bắt lại để hiện hộp "Không thể xóa"
        so_dong, _ = thong_bao_cua(nguoi_dung).filter(pk=ma_thong_bao).delete()  # DELETE ... WHERE đúng chủ và đúng mã; trả về (số dòng đã xóa, chi tiết theo bảng)
    except DatabaseError:  # lỗi cơ sở dữ liệu
        logger.exception('thong_bao: xóa thất bại (mã %s)', ma_thong_bao)  # ghi log đầy đủ để sửa sau
        return False  # báo thất bại, không ném lỗi ra ngoài
    return so_dong > 0  # xóa được ít nhất 1 dòng là thành công

def tu_dong_danh_dau_da_doc(nguoi_dung, thong_bao):  # UC9.2: mở xem thì tự chuyển Chưa đọc -> Đã đọc
    """Trả về True nếu thông báo đã (hoặc vừa được) chuyển sang Đã đọc; False nếu cập nhật lỗi."""  # mô tả hàm
    if thong_bao.TrangThaiDoc == TrangThaiDoc.DA_DOC:  # đã đọc từ trước
        return True  # không cần làm gì
    if dat_trang_thai_doc(nguoi_dung, thong_bao.pk, True):  # ghi 'Đã đọc' vào DB thành công
        thong_bao.TrangThaiDoc = TrangThaiDoc.DA_DOC  # cập nhật luôn bản đang cầm để trang hiển thị đúng
        return True  # thành công
    return False  # thất bại: thông báo vẫn Chưa đọc (wireframe: Lỗi cập nhật đã đọc)


def url_booking(thong_bao, nguoi_dung):  # địa chỉ trang Booking liên quan, theo vai trò người xem
    """None: không có Booking hoặc vai trò này chưa có trang Booking (ẩn nút).
    '#': có Booking nhưng trang chi tiết chưa được làm (nút hiện nhưng chưa bấm được).
    Chuỗi địa chỉ: link thật."""  # mô tả 3 kết quả
    if thong_bao.MaBooking_id is None:  # thông báo không gắn Booking
        return None  # không có gì để dẫn tới
    ten_url = URL_BOOKING_THEO_VAI_TRO.get(get_role(nguoi_dung))  # tên URL ứng với vai trò
    if ten_url is None:  # vai trò chưa có trang Booking (Quản trị viên)
        return None  # ẩn nút
    try:  # thử tạo địa chỉ từ tên URL
        return reverse(ten_url, kwargs={'ma_booking': thong_bao.MaBooking_id})  # ví dụ /bookings/quan-ly/12/
    except NoReverseMatch:  # chưa có URL đó trong project
        return '#'  # link tạm, không làm lỗi trang


# =====================================================================
# P9: GỬI EMAIL KÈM THÔNG BÁO TRÊN WEB (Phanh)
# Email KHÔNG phải actor, chỉ là một bước tự động của hệ thống (kết quả A2 của báo cáo GĐ2).
# Khi làm thử: email in ra Terminal; khi có .env mới gửi thật (cấu hình MAILERS trong config/settings.py).
# Quy tắc: gửi email SAU KHI dữ liệu đã commit; lỗi email chỉ ghi 'Gửi thất bại', không làm hỏng việc chính.
# CÁCH DÙNG cho các bạn khác (thay cho việc gọi gui_thong_bao rồi tự gọi gui_email_sau_commit):
#     from notifications.services import gui_thong_bao_kem_email
#     gui_thong_bao_kem_email(user, 'Tiêu đề', 'Nội dung', booking=bk)
# =====================================================================
def gui_email_sau_commit(thong_bao, nguoi_nhan, tieu_de, noi_dung):  # hẹn gửi email; cùng tên và cùng tham số với hàm của bookings/services.py
    """Hẹn gửi email cho nguoi_nhan SAU KHI transaction hiện tại commit, rồi ghi kết quả vào thong_bao (có thể None)."""  # mô tả hàm
    transaction.on_commit(  # nếu đang trong transaction.atomic thì chờ commit xong; nếu không thì chạy ngay
        lambda: _gui_email_va_ghi_ket_qua(thong_bao, nguoi_nhan, tieu_de, noi_dung)  # việc gửi thật nằm ở hàm bên dưới
    )  # hết đăng ký on_commit


def _gui_email_va_ghi_ket_qua(thong_bao, nguoi_nhan, tieu_de, noi_dung):  # phần chạy thật: gửi mail rồi ghi TrangThaiGuiEmail
    """Không bao giờ ném lỗi ra ngoài."""  # mô tả hàm
    try:  # thử gửi; lỗi gì cũng nhảy xuống except
        if not nguoi_nhan.email:  # người nhận chưa có địa chỉ email thì không gửi được
            raise ValueError('Người nhận chưa có email')  # ném lỗi để nhảy xuống except và đánh dấu thất bại
        send_mail(tieu_de, noi_dung, None, [nguoi_nhan.email], fail_silently=False)  # None = DEFAULT_FROM_EMAIL; fail_silently=False để lỗi SMTP nổi lên và bị bắt
        ket_qua = TrangThaiGuiEmail.THANH_CONG  # gửi được (khi làm thử thì nghĩa là đã in ra Terminal)
    except Exception:  # noqa: BLE001  # SMTP, DNS, mất mạng... lỗi gì cũng không được làm sập web
        logger.exception('gui_email_sau_commit: gửi email thất bại (%s)', tieu_de)  # ghi log đầy đủ để sửa sau
        ket_qua = TrangThaiGuiEmail.THAT_BAI  # đánh dấu gửi thất bại
    if thong_bao is not None:  # có thông báo web đi kèm thì ghi kết quả vào đó
        try:  # ghi kết quả cũng có thể lỗi DB
            ThongBao.objects.filter(pk=thong_bao.pk).update(TrangThaiGuiEmail=ket_qua)  # UPDATE đúng một cột, không đụng cột khác
        except DatabaseError:  # lỗi cơ sở dữ liệu
            logger.exception('gui_email_sau_commit: không ghi được TrangThaiGuiEmail')  # chỉ ghi log


def _noi_dung_email(nguoi_nhan, noi_dung):  # ghép lời chào và chữ ký quanh nội dung thông báo
    ten = (nguoi_nhan.get_full_name() or '').strip() or nguoi_nhan.email  # ưu tiên họ tên, không có thì dùng email
    return f'Xin chào {ten},\n\n{noi_dung}\n\nFRAMIE'  # cùng kiểu với email đăng ký ở accounts/services.py


def gui_thong_bao_kem_email(nguoi_nhan, tieu_de, noi_dung, booking=None):  # HÀM CHÍNH P9: thông báo web + email
    """Tạo thông báo web (như gui_thong_bao) và hẹn gửi email cho cùng người nhận. Trả về ThongBao, hoặc None nếu không tạo được."""  # mô tả hàm
    thong_bao = gui_thong_bao(nguoi_nhan, tieu_de, noi_dung, booking=booking)  # bước 1: thông báo trên web (hàm này tự nuốt lỗi)
    if nguoi_nhan is None or getattr(nguoi_nhan, 'pk', None) is None:  # không có người nhận hợp lệ
        return thong_bao  # gui_thong_bao đã ghi cảnh báo, không có ai để gửi email
    tieu_de = (tieu_de or '').strip()[:255]  # làm sạch tiêu đề giống gui_thong_bao
    noi_dung = (noi_dung or '').strip()  # làm sạch nội dung giống gui_thong_bao
    if not tieu_de or not noi_dung:  # thiếu tiêu đề hoặc nội dung thì không có gì để gửi
        return thong_bao  # dừng, không gửi email rỗng
    gui_email_sau_commit(thong_bao, nguoi_nhan, tieu_de, _noi_dung_email(nguoi_nhan, noi_dung))  # bước 2: hẹn gửi email sau commit
    return thong_bao  # trả về thông báo web (có thể None nếu lưu web lỗi; email vẫn được gửi)


def gui_thong_bao_nhieu_nguoi_kem_email(ds_nguoi_nhan, tieu_de, noi_dung, booking=None):  # như gui_thong_bao_nhieu_nguoi nhưng có email
    """Ví dụ: báo cho tất cả Quản trị viên khi có hồ sơ mới. Mỗi người chỉ nhận một lần. Trả về list ThongBao tạo được."""  # mô tả hàm
    da_gui = set()  # tập mã User đã xử lý để không gửi trùng
    ket_qua = []  # danh sách thông báo web tạo thành công
    for user in ds_nguoi_nhan:  # duyệt từng người nhận
        if user is None or user.pk in da_gui:  # bỏ qua giá trị rỗng hoặc người đã gửi
            continue  # sang người tiếp theo
        da_gui.add(user.pk)  # ghi nhớ người này đã xử lý
        thong_bao = gui_thong_bao_kem_email(user, tieu_de, noi_dung, booking=booking)  # gửi web + email cho từng người
        if thong_bao is not None:  # chỉ giữ thông báo tạo thành công
            ket_qua.append(thong_bao)  # thêm vào kết quả
    return ket_qua  # trả về danh sách