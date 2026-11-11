# =====================================================================
# core/views_tong_quan.py  -  B9: Trang tổng quan sau đăng nhập
#
#   Khách hàng    : Booking đang xử lý + thông báo mới.
#   Nhiếp ảnh gia : yêu cầu Booking mới + lịch sắp tới + tình trạng hồ sơ.
#                   (hồ sơ chưa được duyệt chỉ thấy tình trạng hồ sơ, giống menu bị rút gọn ở header)
#   Quản trị viên : chuyển sang trang tổng quan riêng của Quản trị (B7, name='admin_dashboard').
#
# Trang này KHÔNG tự tính nghiệp vụ: chỉ gọi lại các hàm/bảng có sẵn của module khác
# (bookings.theo_doi, bookings.tiep_nhan, notifications, schedule, profiles) rồi gom lại.
# =====================================================================
from django.contrib.auth.decorators import login_required  # nhãn: chưa đăng nhập thì chuyển về trang đăng nhập
from django.core.exceptions import ObjectDoesNotExist  # lỗi "không có dòng dữ liệu liên quan" (ví dụ chưa tạo hồ sơ)
from django.shortcuts import redirect, render  # redirect: chuyển sang trang khác; render: dựng trang HTML
from django.urls import NoReverseMatch, reverse  # reverse: từ TÊN url ra địa chỉ; NoReverseMatch: lỗi khi tên url chưa tồn tại
from django.utils import timezone  # lấy giờ hiện tại có múi giờ
from django.views.decorators.http import require_GET  # nhãn: chỉ cho mở trang bằng GET (xem), chặn POST

from accounts.permissions import lay_vai_tro  # biết người đang đăng nhập là Khách hàng / Nhiếp ảnh gia / Quản trị viên
from bookings.theo_doi import booking_cua_nguoi_dung          # "cửa ngõ" lấy Booking của chính người dùng (BR4.7-1)
from bookings.tiep_nhan import dem_cho_xac_nhan               # số yêu cầu đang chờ Nhiếp ảnh gia xác nhận
from core.constants import KetQuaDuyetHoSo, TrangThaiBooking as BK, TrangThaiDoc, TrangThaiHoSo, VaiTro  # tên các trạng thái / vai trò dùng chung (BK = tên viết tắt)
from notifications.models import ThongBao  # bảng thông báo
from notifications.services import dem_chua_doc  # hàm đếm thông báo chưa đọc của một người
from profiles.models import DuyetHoSo  # bảng các lượt duyệt hồ sơ Nhiếp ảnh gia
from schedule.services import dem_khung_gio_trong  # hàm đếm khung giờ còn trống của Nhiếp ảnh gia

SO_DONG_TOI_DA = 5          # mỗi danh sách trên trang chỉ hiện 5 dòng đầu, còn lại bấm "Xem tất cả"
SO_NGAY_KHUNG_GIO = 7       # "khung giờ còn trống trong 7 ngày tới" (cùng cách tính với Trang chủ)

# 4 trạng thái kết thúc: Booking ở đây không còn "đang xử lý" nữa.
TRANG_THAI_KET_THUC = [BK.HOAN_THANH, BK.DA_TU_CHOI, BK.HET_THOI_HAN_DAT_COC, BK.DA_HUY]  # danh sách dùng để loại các Booking đã xong


def _url(ten_url, args=None):  # hàm nhỏ: đổi TÊN url thành địa chỉ, không bao giờ báo lỗi
    """Tên URL -> đường dẫn; trang của bạn khác chưa có thì trả '' (template ẩn nút, không báo lỗi)."""
    try:  # thử suy ra địa chỉ
        return reverse(ten_url, args=args)  # có tên url -> trả địa chỉ thật (args: các số đi kèm, ví dụ mã Booking)
    except NoReverseMatch:  # tên url chưa tồn tại (trang của người khác chưa merge)
        return ''  # trả chuỗi rỗng; template thấy rỗng sẽ ẩn nút / link


def _dong_booking(booking, ten_url_chi_tiet, ben_kia):  # gom một Booking thành một "dòng" cho template
    """Một dòng Booking trên trang. ben_kia: tên người đối diện (Nhiếp ảnh gia nếu là Khách, Khách nếu là Nhiếp ảnh gia)."""
    return {'ma': booking.pk, 'goi': booking.MaGoi.TenGoi, 'ben_kia': ben_kia,  # mã Booking, tên gói, tên người đối diện
            'gio_chup': booking.NgayGioChup, 'trang_thai': booking.TrangThai,  # giờ chụp, trạng thái hiện tại
            'href': _url(ten_url_chi_tiet, [booking.pk])}  # link tới trang chi tiết (rỗng nếu trang đó chưa có)


def _ten(user):  # tên hiển thị của một người
    return user.get_full_name() or user.username  # có họ tên thì dùng, trống thì lấy tên đăng nhập


# ---------------------------------------------------------------- Khách hàng
def _du_lieu_khach_hang(user):  # gom dữ liệu cho trang của Khách hàng
    dang_xu_ly = (booking_cua_nguoi_dung(user, VaiTro.KHACH_HANG)  # chỉ Booking do chính Khách này đặt (cửa ngõ BR4.7-1)
                  .exclude(TrangThai__in=TRANG_THAI_KET_THUC).order_by('-NgayTao', '-MaBooking'))  # bỏ Booking đã kết thúc; mới nhất lên đầu
    # Sắp xếp rõ ràng (mới nhất lên đầu) ngay tại đây, không dựa vào Meta.ordering của model, rồi mới cắt [:5].
    thong_bao = (ThongBao.objects.filter(MaNguoiNhan=user, TrangThaiDoc=TrangThaiDoc.CHUA_DOC)  # chỉ thông báo của chính Khách này và chưa đọc
                 .order_by('-NgayTao', '-MaThongBao'))  # mới nhất lên đầu; '-MaThongBao' để hai thông báo cùng giờ vẫn có thứ tự cố định
    return {  # từ điển dữ liệu đưa cho template
        'so_dang_xu_ly': dang_xu_ly.count(),  # tổng số Booking đang xử lý (không bị cắt 5 dòng)
        'dang_xu_ly': [_dong_booking(b, 'chi_tiet_booking', _ten(b.MaNhiepAnhGia.MaTaiKhoan))  # mỗi Booking thành một dòng; người đối diện = Nhiếp ảnh gia
                       for b in dang_xu_ly[:SO_DONG_TOI_DA]],  # chỉ lấy 5 Booking đầu
        'so_thong_bao': dem_chua_doc(user),  # tổng số thông báo chưa đọc
        'thong_bao': [{'tieu_de': t.TieuDe, 'noi_dung': t.NoiDung, 'ngay_tao': t.NgayTao,  # mỗi thông báo thành một dòng: tiêu đề, nội dung, giờ tạo
                       'href': _url('chi_tiet_booking', [t.MaBooking_id]) if t.MaBooking_id else ''}  # có gắn Booking thì link tới Booking đó, không thì rỗng
                      for t in thong_bao[:SO_DONG_TOI_DA]],  # chỉ lấy 5 thông báo mới nhất
        'url_booking_cua_toi': _url('my_bookings'),  # link "Xem tất cả" Booking
        'url_thong_bao': _url('notifications'),  # link "Xem tất cả" thông báo
        'url_tim_kiem': _url('search'),  # link nút "Tìm nhiếp ảnh gia" khi chưa có Booking
    }


# ------------------------------------------------------------- Nhiếp ảnh gia
def _luot_duyet_moi_nhat(nag):  # tìm lượt duyệt mới nhất của hồ sơ
    """Lượt duyệt MỚI NHẤT của hồ sơ (kể cả lượt chưa có kết quả), sắp theo LanNop giảm dần.
    Cùng cách xác định với màn "Hồ sơ của tôi" (profiles/views_cua_toi.py): chỉ lượt mới nhất mới quyết định
    Nhiếp ảnh gia đang ở trạng thái nào. Nhờ lấy cả lượt chưa có kết quả, hồ sơ vừa được nộp lại sẽ hiện
    "đang chờ duyệt" chứ không hiện lại lý do của lượt trước."""
    return DuyetHoSo.objects.filter(MaNhiepAnhGia=nag).order_by('-LanNop').first()  # lấy các lượt của hồ sơ này, lần nộp lớn nhất đứng đầu, lấy lượt đầu (None nếu chưa có)


def _du_lieu_nhiep_anh_gia(user):  # gom dữ liệu cho trang của Nhiếp ảnh gia
    trang_thai = user.trang_thai_ho_so  # trạng thái hồ sơ lưu trên tài khoản: Chờ duyệt / Đã duyệt / Đã từ chối
    da_duyet = trang_thai == TrangThaiHoSo.DA_DUYET  # hồ sơ đã được duyệt chưa
    try:  # thử lấy hồ sơ Nhiếp ảnh gia của tài khoản này
        nag = user.ho_so_nhiep_anh_gia  # truy ngược từ tài khoản sang hồ sơ
    except ObjectDoesNotExist:          # tài khoản có vai trò Nhiếp ảnh gia nhưng chưa tạo hồ sơ
        nag = None  # chưa có hồ sơ

    # Chỉ hồ sơ chưa duyệt mới cần lượt duyệt gần nhất (để biết bị từ chối hay bị yêu cầu chỉnh sửa, và lý do).
    luot = None if da_duyet or nag is None else _luot_duyet_moi_nhat(nag)  # đã duyệt hoặc chưa có hồ sơ thì khỏi tra; còn lại lấy lượt mới nhất
    ket_qua = luot.KetQua if luot else None  # kết quả của lượt đó (None = lượt đang chờ duyệt, hoặc không có lượt)
    da_tu_choi = trang_thai == TrangThaiHoSo.DA_TU_CHOI  # hồ sơ có đang ở trạng thái "Đã từ chối" không
    # Theo quy ước của nhóm, "Yêu cầu chỉnh sửa" vẫn giữ User.trang_thai_ho_so = 'Chờ duyệt' nên không thể nhận ra
    # từ trạng thái hồ sơ; phải xem KetQua của lượt duyệt mới nhất.
    can_chinh_sua = not da_tu_choi and ket_qua == KetQuaDuyetHoSo.YEU_CAU_CHINH_SUA  # True khi lượt mới nhất là "Yêu cầu chỉnh sửa"
    du_lieu = {  # dữ liệu dùng chung cho cả hồ sơ đã duyệt và chưa duyệt
        'da_duyet': da_duyet,  # template: hiện khối Booking hay không
        'da_tu_choi': da_tu_choi,  # template: nhánh "Đã từ chối"
        'can_chinh_sua': can_chinh_sua,  # template: nhánh "Quản trị viên yêu cầu chỉnh sửa"
        'trang_thai_ho_so': trang_thai,  # chữ trạng thái để vẽ nhãn màu
        # Lý do chỉ có khi lượt mới nhất là "Đã từ chối" hoặc "Yêu cầu chỉnh sửa"; đang chờ duyệt thì để trống.
        'phan_hoi': (luot.NoiDungPhanHoi or '') if (can_chinh_sua or (da_tu_choi and ket_qua == KetQuaDuyetHoSo.DA_TU_CHOI)) else '',  # lý do Quản trị viên ghi; không đúng trường hợp thì rỗng
        'url_ho_so': _url('photographer_profile') or _url('cap_nhat_ho_so'),  # link nút hồ sơ: ưu tiên "Hồ sơ của tôi", không có thì trang cập nhật
    }
    if not da_duyet:                    # Chờ duyệt / Yêu cầu chỉnh sửa / Đã từ chối: chỉ có tình trạng hồ sơ
        return du_lieu  # dừng ở đây, không đưa dữ liệu Booking

    cua_toi = booking_cua_nguoi_dung(user, VaiTro.NHIEP_ANH_GIA)  # chỉ Booking gửi tới chính Nhiếp ảnh gia này (cửa ngõ BR4.7-1)
    yeu_cau_moi = cua_toi.filter(TrangThai=BK.CHO_XAC_NHAN).order_by('-NgayTao', '-MaBooking')  # yêu cầu đang chờ xác nhận, mới nhất lên đầu
    lich_sap_toi = (cua_toi.filter(TrangThai=BK.CHOT_BOOKING, NgayGioChup__gte=timezone.now())  # Booking đã chốt và giờ chụp chưa tới
                    .order_by('NgayGioChup', 'MaBooking'))  # buổi chụp gần nhất lên đầu
    du_lieu.update({  # thêm phần dữ liệu Booking vào từ điển
        'so_yeu_cau_moi': dem_cho_xac_nhan(user),  # số yêu cầu chờ xác nhận (dùng hàm của module Booking)
        'yeu_cau_moi': [_dong_booking(b, 'chi_tiet_yeu_cau_booking', _ten(b.MaKhachHang))  # mỗi yêu cầu thành một dòng; người đối diện = Khách
                        for b in yeu_cau_moi[:SO_DONG_TOI_DA]],  # chỉ lấy 5 dòng đầu
        'so_lich_sap_toi': lich_sap_toi.count(),  # tổng số buổi chụp sắp tới
        'lich_sap_toi': [_dong_booking(b, 'chi_tiet_yeu_cau_booking', _ten(b.MaKhachHang))  # mỗi buổi chụp thành một dòng
                         for b in lich_sap_toi[:SO_DONG_TOI_DA]],  # chỉ lấy 5 dòng đầu
        'so_khung_gio_trong': dem_khung_gio_trong(nag, SO_NGAY_KHUNG_GIO) if nag else 0,  # số khung giờ trống trong 7 ngày tới (0 nếu chưa có hồ sơ)
        'so_ngay_khung_gio': SO_NGAY_KHUNG_GIO,  # con số 7 để template ghi "trong 7 ngày tới"
        'url_quan_ly_booking': _url('manage_bookings'),  # link "Xem tất cả" yêu cầu Booking
        'url_lich': _url('my_calendar'),  # link "Xem lịch"
    })
    return du_lieu  # trả toàn bộ dữ liệu


# ------------------------------------------------------------------- View
@login_required  # chưa đăng nhập -> trang đăng nhập
@require_GET  # chỉ nhận GET
def tong_quan(request):  # view của trang /tong-quan/
    vai_tro = lay_vai_tro(request.user)  # biết người đang xem là ai
    if vai_tro == VaiTro.QUAN_TRI_VIEN:      # Quản trị viên có trang tổng quan riêng (B7)
        return redirect(_url('admin_dashboard') or 'home')  # chuyển sang trang của Quản trị; chưa có thì về Trang chủ
    la_nag = vai_tro == VaiTro.NHIEP_ANH_GIA  # người xem có phải Nhiếp ảnh gia không (còn lại là Khách hàng)
    return render(request, 'core/tong_quan.html', {  # dựng trang từ template, kèm dữ liệu bên dưới
        'la_nhiep_anh_gia': la_nag,  # template chọn nhánh Khách hay Nhiếp ảnh gia
        'khach': None if la_nag else _du_lieu_khach_hang(request.user),  # dữ liệu Khách (None nếu là Nhiếp ảnh gia)
        'nag': _du_lieu_nhiep_anh_gia(request.user) if la_nag else None,  # dữ liệu Nhiếp ảnh gia (None nếu là Khách)
    })
