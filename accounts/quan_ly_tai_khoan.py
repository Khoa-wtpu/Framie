# =====================================================================
# accounts/quan_ly_tai_khoan.py  -  P7 (UC7.3): quản lý vai trò và khóa/mở tài khoản
# Chỗ DUY NHẤT chứa luật nghiệp vụ; view chỉ gọi các hàm ở đây.
# =====================================================================
import logging  # ghi một dòng vết mỗi lần đổi vai trò hoặc khóa/mở (không cần model, không cần migration)

from django.contrib.auth import get_user_model  # lấy class User của dự án (accounts.User)
from django.contrib.auth.models import Group  # bảng nhóm quyền của Django (mỗi nhóm = một vai trò)
from django.db import transaction  # gom nhiều thao tác DB thành một khối, lỗi thì hoàn tác
from django.db.models import Q  # ghép điều kiện lọc bằng "hoặc" (|) và "và" (&)

from core.constants import VaiTro  # tên 3 vai trò, không tự gõ chữ tiếng Việt (README)

User = get_user_model()  # class User của dự án
logger = logging.getLogger(__name__)  # bộ ghi log riêng của file này

# Vai trò mà Quản trị viên được GÁN cho tài khoản. Nhiếp ảnh gia KHÔNG nằm ở đây vì phải đăng ký + điền hồ sơ + được duyệt (P5, K7).
VAI_TRO_CHO_DOI = (VaiTro.KHACH_HANG, VaiTro.QUAN_TRI_VIEN)  # muốn cho phép thêm vai trò thì sửa đúng dòng này


class LoiQuanLyTaiKhoan(Exception):  # lỗi nghiệp vụ tự đặt; nội dung lỗi là câu tiếng Việt để hiện cho Quản trị viên
    pass  # không cần thêm gì, chỉ cần có tên


def vai_tro_cua(user):  # vai trò chính của một User, đọc từ nhóm ĐÃ prefetch (không truy vấn thêm cho từng dòng)
    ten_nhom = {nhom.name for nhom in user.groups.all()}  # tập tên các nhóm của User
    if user.is_superuser:  # tài khoản tạo bằng createsuperuser
        return VaiTro.QUAN_TRI_VIEN  # luôn là Quản trị viên (giống permissions.lay_vai_tro)
    for vai_tro in (VaiTro.QUAN_TRI_VIEN, VaiTro.NHIEP_ANH_GIA, VaiTro.KHACH_HANG):  # duyệt theo thứ tự ưu tiên
        if vai_tro in ten_nhom:  # User thuộc nhóm này
            return vai_tro  # trả vai trò tìm được
    return VaiTro.KHACH_HANG  # chưa có nhóm nào: coi là Khách hàng (giống permissions.lay_vai_tro)


def danh_sach_tai_khoan(tim='', vai_tro='', trang_thai=''):  # trả QuerySet tài khoản đã lọc, mới nhất lên đầu
    ds = User.objects.prefetch_related('groups').order_by('-date_joined', '-pk')  # prefetch nhóm để hiện vai trò mà không bị N+1 truy vấn
    for tu in tim.split():  # tách ô tìm kiếm thành từng từ; mỗi từ đều phải khớp ở ÍT NHẤT một cột
        ds = ds.filter(  # lọc tiếp theo từ này
            Q(first_name__icontains=tu) | Q(last_name__icontains=tu)  # khớp tên hoặc họ và tên đệm
            | Q(email__icontains=tu) | Q(so_dien_thoai__icontains=tu)  # hoặc khớp email hoặc số điện thoại
        )  # hết điều kiện của một từ
    if vai_tro == VaiTro.QUAN_TRI_VIEN:  # lọc Quản trị viên
        ds = ds.filter(Q(is_superuser=True) | Q(groups__name=VaiTro.QUAN_TRI_VIEN))  # superuser cũng tính là Quản trị viên
    elif vai_tro == VaiTro.NHIEP_ANH_GIA:  # lọc Nhiếp ảnh gia
        ds = ds.filter(groups__name=VaiTro.NHIEP_ANH_GIA).exclude(is_superuser=True)  # trừ superuser
    elif vai_tro == VaiTro.KHACH_HANG:  # lọc Khách hàng
        ds = ds.exclude(is_superuser=True).exclude(groups__name__in=[VaiTro.QUAN_TRI_VIEN, VaiTro.NHIEP_ANH_GIA])  # không phải 2 vai trò kia
    if trang_thai == 'hoat_dong':  # lọc tài khoản đang hoạt động
        ds = ds.filter(is_active=True)  # còn đăng nhập được
    elif trang_thai == 'bi_khoa':  # lọc tài khoản bị khóa
        ds = ds.filter(is_active=False)  # không đăng nhập được
    return ds.distinct()  # distinct: một người không xuất hiện hai lần do ghép bảng nhóm


def mo_ta_tai_khoan(nguoi_thuc_hien, user):  # cho template biết dòng này được phép làm gì
    la_toi = user.pk == nguoi_thuc_hien.pk  # chính Quản trị viên đang đăng nhập
    vai_tro = vai_tro_cua(user)  # vai trò hiện tại
    thao_tac_duoc = not la_toi and not user.is_superuser  # không tự đổi/khóa mình; không đụng tài khoản hệ thống
    return {  # gói thông tin cho template
        'user': user,  # chính tài khoản
        'vai_tro': vai_tro,  # vai trò hiện tại
        'la_toi': la_toi,  # có phải mình không
        'he_thong': user.is_superuser,  # có phải superuser không
        'doi_duoc_vai_tro': thao_tac_duoc and vai_tro != VaiTro.NHIEP_ANH_GIA,  # Nhiếp ảnh gia không đổi vai trò ở đây
        'khoa_duoc': thao_tac_duoc,  # có hiện nút Khóa/Mở không
    }  # hết dict


def doi_vai_tro(nguoi_thuc_hien, user, vai_tro_moi):  # đổi vai trò chính của một tài khoản; sai luật thì ném LoiQuanLyTaiKhoan
    if vai_tro_moi not in VAI_TRO_CHO_DOI:  # vai trò gửi lên không hợp lệ (kể cả người dùng tự sửa form)
        raise LoiQuanLyTaiKhoan('Vai trò mới không hợp lệ.')  # báo lỗi
    if user.pk == nguoi_thuc_hien.pk:  # tự đổi vai trò của mình
        raise LoiQuanLyTaiKhoan('Bạn không thể đổi vai trò của chính mình.')  # chặn; luật này cũng bảo đảm luôn còn ít nhất 1 Quản trị viên (chính người đang thao tác)
    if user.is_superuser:  # tài khoản hệ thống
        raise LoiQuanLyTaiKhoan('Tài khoản hệ thống (superuser) không đổi được vai trò ở trang này.')  # vì lay_vai_tro luôn coi là Quản trị viên, đổi nhóm cũng vô nghĩa
    hien_tai = vai_tro_cua(user)  # vai trò hiện tại
    if hien_tai == VaiTro.NHIEP_ANH_GIA:  # Nhiếp ảnh gia đã có hồ sơ và có thể có Booking
        raise LoiQuanLyTaiKhoan('Không đổi vai trò của Nhiếp ảnh gia ở trang này (hồ sơ và Booking đang gắn với tài khoản). Bạn có thể khóa tài khoản.')  # chỉ cho khóa
    if hien_tai == vai_tro_moi:  # đã đúng vai trò rồi
        raise LoiQuanLyTaiKhoan('Tài khoản đã ở vai trò này.')  # không có gì để đổi
    with transaction.atomic():  # từ dòng này, lỗi ở đâu thì hoàn tác hết
        nhom_moi, _ = Group.objects.get_or_create(name=vai_tro_moi)  # lấy nhóm của vai trò mới (migration 0003 đã tạo sẵn)
        user.groups.set([nhom_moi])  # set: THAY toàn bộ nhóm cũ bằng đúng 1 nhóm mới => mỗi tài khoản một vai trò chính
    logger.warning('Đổi vai trò: %s đổi tài khoản %s từ %s sang %s', nguoi_thuc_hien.email, user.email, hien_tai, vai_tro_moi)  # ai làm, với tài khoản nào, trước và sau; dùng warning vì settings.py chưa có LOGGING nên mức info không hiện ra Terminal


def khoa_mo_tai_khoan(nguoi_thuc_hien, user, khoa):  # khoa=True: khóa; khoa=False: mở lại
    if user.pk == nguoi_thuc_hien.pk:  # tự khóa mình
        raise LoiQuanLyTaiKhoan('Bạn không thể khóa chính mình.')  # chặn; tránh tự mất quyền vào trang quản trị
    if user.is_superuser:  # tài khoản hệ thống
        raise LoiQuanLyTaiKhoan('Không khóa được tài khoản hệ thống (superuser).')  # chặn
    if user.is_active == (not khoa):  # đã ở đúng trạng thái yêu cầu (ví dụ bấm Khóa hai lần)
        raise LoiQuanLyTaiKhoan('Tài khoản đã ở trạng thái này.')  # báo nhẹ
    user.is_active = not khoa  # khóa: is_active=False; mở: is_active=True
    user.save(update_fields=['is_active'])  # chỉ lưu đúng cột này; phiên đăng nhập cũ tự mất hiệu lực ở lần truy cập kế tiếp
    logger.warning('%s tài khoản %s bởi %s', 'Khóa' if khoa else 'Mở', user.email, nguoi_thuc_hien.email)  # ghi vết khóa/mở: ai làm, với tài khoản nào