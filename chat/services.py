# chat/services.py - P10 (UC8.1): logic khởi tạo cuộc trò chuyện. View và template chỉ gọi các hàm ở đây.
from django.db import IntegrityError, transaction  # IntegrityError: lỗi trùng khóa; transaction: gói lệnh lưu cho an toàn
from django.http import Http404  # lỗi "không tìm thấy trang"
from django.urls import NoReverseMatch, reverse  # đổi tên URL (name=...) thành đường dẫn

from chat.models import CuocTroChuyen  # bảng cuộc trò chuyện (đã có sẵn trong Module 8)
from core.constants import TrangThaiHoSo, VaiTro  # tên vai trò và tên trạng thái hồ sơ, không tự gõ chữ tiếng Việt


def la_khach_hang(user):  # True nếu người dùng đã đăng nhập VÀ thuộc nhóm Khách hàng
    return bool(user.is_authenticated and user.groups.filter(name=VaiTro.KHACH_HANG).exists())  # nhóm = vai trò (README)


def nhiep_anh_gia_nhan_duoc_tin(nag):  # Nhiếp ảnh gia có được Khách bắt đầu nhắn mới không
    tai_khoan = nag.MaTaiKhoan  # tài khoản User của Nhiếp ảnh gia
    return bool(tai_khoan.is_active and tai_khoan.trang_thai_ho_so == TrangThaiHoSo.DA_DUYET)  # chỉ hồ sơ "Đã duyệt" mới công khai


def duong_dan_ho_so(ma_nhiep_anh_gia):  # đường dẫn trang hồ sơ công khai của Nhiếp ảnh gia (cùng cách làm với search/views.py)
    for ten in ('photographer_detail', 'lich_chon_slot'):  # K9 chưa có thì dùng trang chọn lịch UC4.1
        try:  # thử đổi tên URL thành đường dẫn
            return reverse(ten, args=[ma_nhiep_anh_gia])  # được thì trả về luôn
        except NoReverseMatch:  # URL này chưa tồn tại trong project
            continue  # thử tên kế tiếp
    return '/'  # cả hai chưa có thì về trang chủ


def duong_dan_cuoc_tro_chuyen(ma_cuoc):  # đường dẫn màn hình cuộc trò chuyện (SC8.2, UC8.2 - chưa làm)
    try:  # UC8.2 sau này chỉ cần đặt name='chi_tiet_cuoc_tro_chuyen' là P10 tự chạy
        return reverse('chi_tiet_cuoc_tro_chuyen', args=[ma_cuoc])  # có thì trả về
    except NoReverseMatch:  # chưa có UC8.2
        return None  # view sẽ tự xử lý


def mo_hoac_tao_cuoc_tro_chuyen(khach, nag):
    # Trả về (cuộc trò chuyện, da_tao_moi). Mỗi cặp (Khách hàng, Nhiếp ảnh gia) chỉ có MỘT cuộc trò chuyện.
    cuoc_cu = CuocTroChuyen.objects.filter(MaKhachHang=khach, MaNhiepAnhGia=nag).first()  # đã có cuộc trò chuyện của cặp này chưa
    if cuoc_cu:  # đã có
        return cuoc_cu, False  # bấm lại thì mở cuộc cũ, không tạo thêm
    if not nhiep_anh_gia_nhan_duoc_tin(nag):  # chưa có mà Nhiếp ảnh gia chưa được duyệt
        raise Http404('Nhiếp ảnh gia này chưa nhận tin nhắn.')  # không cho tạo mới
    moi = CuocTroChuyen(MaKhachHang=khach, MaNhiepAnhGia=nag)  # dựng đối tượng mới (chưa lưu)
    moi.full_clean(validate_unique=False, validate_constraints=False)  # gọi clean() của model: người khởi tạo phải là Khách hàng
    try:  # lưu vào DB
        with transaction.atomic():  # gói trong giao dịch để lỗi trùng không làm hỏng giao dịch bên ngoài
            moi.save()  # INSERT
    except IntegrityError:  # hai lần bấm cùng lúc: bên kia đã tạo trước, ràng buộc UNIQUE chặn lần này
        return CuocTroChuyen.objects.get(MaKhachHang=khach, MaNhiepAnhGia=nag), False  # lấy cuộc trò chuyện bên kia vừa tạo
    return moi, True  # tạo mới thành công
