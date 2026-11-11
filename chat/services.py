# chat/services.py - P10 (UC8.1), P11 (UC8.2, UC8.3) và nâng cấp chat (bước 1 đến 6): logic nghiệp vụ. View và template chỉ gọi các hàm ở đây.
import os  # lấy tên file an toàn
import re  # tìm đường link trong tin nhắn (góp ý C2)
import unicodedata  # tách dấu tiếng Việt khỏi chữ cái để tìm không dấu (bước 7)
from datetime import timedelta  # tính mốc 6 tháng lưu ảnh
import uuid  # đặt tên file ảnh ngẫu nhiên, không lộ tên gốc và không trùng

from django.conf import settings  # đọc BASE_DIR và PRIVATE_MEDIA_ROOT (nếu có)
from django.core.exceptions import PermissionDenied, ValidationError  # 403; lỗi dữ liệu không hợp lệ (tin rỗng, tin quá dài)
from django.core.files.storage import FileSystemStorage  # kho lưu ảnh trong thư mục riêng
from django.utils import timezone  # giờ hiện tại có múi giờ
from PIL import Image  # kiểm tra file có đúng là ảnh (Pillow đã có trong requirements)
from django.db import DatabaseError, IntegrityError, transaction  # IntegrityError: lỗi trùng khóa; transaction: gói lệnh lưu cho an toàn
from django.db.models import Count, DateTimeField, OuterRef, Q, Subquery  # Q: điều kiện OR; Subquery/OuterRef: lấy giá trị theo từng cuộc; Count: đếm tin chưa đọc
from django.db.models.functions import Coalesce  # lấy giá trị đầu tiên khác NULL
from django.http import Http404  # lỗi "không tìm thấy trang"
from django.shortcuts import get_object_or_404  # tìm đối tượng hoặc báo 404
from django.urls import NoReverseMatch, reverse  # đổi tên URL (name=...) thành đường dẫn

from chat.models import CuocTroChuyen, DinhKemTinNhan, ThamGia, TinNhan  # bảng cuộc trò chuyện, tin nhắn và trạng thái riêng từng người (THAMGIA)
from core.constants import TrangThaiHoSo, VaiTro  # tên vai trò và tên trạng thái hồ sơ, không tự gõ chữ tiếng Việt

SO_TIN_MOI_LAN = 30  # mỗi lần tải: 30 tin gần nhất, kéo lên trên thì tải thêm 30 tin cũ hơn (giống Messenger)
SO_TIN_MOI_TOI_DA = 100  # một lần polling trả tối đa 100 tin mới, tránh trả quá nặng nếu mất kết nối lâu
GIOI_HAN_NOI_DUNG = 2000  # tin nhắn tối đa 2000 ký tự (cột NoiDung kiểu TEXT không tự giới hạn)
LOI_GUI_TIN = 'Không thể gửi tin nhắn. Vui lòng thử lại.'  # luồng ngoại lệ 5a của UC8.2
LOI_TAI_LICH_SU = 'Không thể tải lịch sử trao đổi. Vui lòng thực hiện lại.'  # luồng ngoại lệ 2a của UC8.3
LOI_KHOI_TAO = 'Không thể khởi tạo cuộc trò chuyện. Vui lòng thực hiện lại.'  # luồng ngoại lệ 2a của UC8.1
SO_ANH_TOI_DA = 5  # mỗi tin nhắn kèm tối đa 5 ảnh
GIOI_HAN_ANH = 5 * 1024 * 1024  # mỗi ảnh tối đa 5 MB (chat không cần bản gốc chất lượng cao như bàn giao ảnh)
DINH_DANG_ANH = {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp'}  # định dạng cho phép và đuôi file lưu
THOI_HAN_ANH_THANG = 6  # ảnh trong cuộc trò chuyện chỉ lưu 6 tháng kể từ lúc gửi (chưa chốt cho gửi video nên chỉ có ảnh)
THOI_HAN_ANH_NGAY = 183  # 6 tháng tính tròn bằng 183 ngày, dùng để so sánh với ThoiGianGui
LOI_TIM = 'Không thể tìm tin nhắn. Vui lòng thử lại.'  # báo lỗi khi tìm trong cuộc trò chuyện (bước 7)
GIOI_HAN_TU_KHOA_TIM = 100  # từ khóa tìm tối đa 100 ký tự
TOI_DA_KET_QUA_TIM = 100  # trả tối đa 100 kết quả, nhiều hơn thì báo "100+"
TOI_DA_QUET_TIN = 5000  # mỗi lần tìm chỉ quét 5000 tin gần nhất để không nặng máy chủ
SO_TIN_NGU_CANH_TIM = 10  # nhảy tới một tin cũ thì tải kèm 10 tin ngay phía trước để người dùng thấy ngữ cảnh
TOI_DA_TIN_NHAY = 1000  # nhảy tới tin cũ xa hơn 1000 tin thì yêu cầu kéo lên tải dần
NHAN_KHACH_HANG = 'Khách hàng'  # nhãn vai trò hiển thị
NHAN_NHIEP_ANH_GIA = 'Nhiếp ảnh gia'  # nhãn vai trò hiển thị


def la_khach_hang(user):  # True nếu người dùng đã đăng nhập VÀ thuộc nhóm Khách hàng
    return bool(user.is_authenticated and user.groups.filter(name=VaiTro.KHACH_HANG).exists())  # nhóm = vai trò (README)


def la_nhiep_anh_gia(user):  # True nếu người dùng đã đăng nhập VÀ thuộc nhóm Nhiếp ảnh gia
    return bool(user.is_authenticated and user.groups.filter(name=VaiTro.NHIEP_ANH_GIA).exists())  # nhóm = vai trò


def duoc_dung_tro_chuyen(user):  # ai được dùng mục Tin nhắn: Khách hàng, hoặc Nhiếp ảnh gia đã được duyệt hồ sơ
    if la_khach_hang(user):  # Khách hàng
        return True  # được dùng
    return bool(la_nhiep_anh_gia(user) and user.trang_thai_ho_so == TrangThaiHoSo.DA_DUYET)  # chưa duyệt chỉ thấy "Hồ sơ của tôi"


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


def duong_dan_cuoc_tro_chuyen(ma_cuoc):  # đường dẫn màn hình cuộc trò chuyện (SC8.2, UC8.2)
    try:  # P11 đã đặt name='chi_tiet_cuoc_tro_chuyen'; giữ try để các test cũ của P10 vẫn chạy với urlconf thử
        return reverse('chi_tiet_cuoc_tro_chuyen', args=[ma_cuoc])  # có thì trả về
    except NoReverseMatch:  # urlconf không có URL này
        return None  # view P10 tự xử lý


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
            for nguoi in (khach, nag.MaTaiKhoan):  # cả hai người trong cuộc đều có hàng trạng thái ngay từ đầu
                ThamGia.objects.get_or_create(MaCuocTroChuyen=moi, MaNguoiDung=nguoi)  # chưa xem tin nào (MaTinDaXemCuoi = 0)
    except IntegrityError:  # hai lần bấm cùng lúc: bên kia đã tạo trước, ràng buộc UNIQUE chặn lần này
        return CuocTroChuyen.objects.get(MaKhachHang=khach, MaNhiepAnhGia=nag), False  # lấy cuộc trò chuyện bên kia vừa tạo
    return moi, True  # tạo mới thành công


# ---------------------------------------------------------------------------------------------
# P11 - UC8.2 và UC8.3
# ---------------------------------------------------------------------------------------------

def lay_cuoc_cua_nguoi_dung(user, ma_cuoc):  # lấy cuộc trò chuyện nếu user là người trong cuộc, ngược lại báo 404
    cuoc = get_object_or_404(  # không có cuộc này thì 404
        CuocTroChuyen.objects.select_related('MaKhachHang', 'MaNhiepAnhGia__MaTaiKhoan'),  # nạp sẵn hai người trong cuộc, đỡ truy vấn thêm
        pk=ma_cuoc,  # theo mã cuộc trò chuyện
    )  # hết get_object_or_404
    la_khach = cuoc.MaKhachHang_id == user.pk  # user là Khách hàng của cuộc này
    la_nag = cuoc.MaNhiepAnhGia.MaTaiKhoan_id == user.pk  # user là tài khoản của Nhiếp ảnh gia trong cuộc này
    if not (la_khach or la_nag):  # người ngoài cuộc trò chuyện
        raise Http404('Không tìm thấy cuộc trò chuyện.')  # trả 404 (không báo 403) để không lộ việc cuộc này có tồn tại
    if la_nag and not duoc_dung_tro_chuyen(user):  # Nhiếp ảnh gia chưa được duyệt hồ sơ
        raise Http404('Không tìm thấy cuộc trò chuyện.')  # theo README: chỉ được dùng "Hồ sơ của tôi"
    return cuoc  # hợp lệ


def thong_tin_nag(nag):  # thông tin Nhiếp ảnh gia dạng giống thong_tin_doi_phuong (dùng khi chưa có cuộc trò chuyện)
    tai_khoan = nag.MaTaiKhoan  # tài khoản User
    try:  # đọc đường dẫn ảnh đại diện
        anh = nag.AnhDaiDien.url if nag.AnhDaiDien else ''  # có ảnh thì lấy .url
    except ValueError:  # file ảnh lỗi
        anh = ''  # dùng chữ cái đầu
    ten = tai_khoan.get_full_name() or tai_khoan.get_username()  # họ tên hoặc tên đăng nhập
    return {'ten': ten, 'anh': anh, 'chu_cai': ten[:1].upper(), 'ho_so': duong_dan_ho_so(nag.pk), 'vai_tro': NHAN_NHIEP_ANH_GIA}  # gói cho template


def thong_tin_doi_phuong(cuoc, user):  # tên, ảnh, chữ cái đầu và link hồ sơ của người ở phía bên kia cuộc trò chuyện
    if cuoc.MaKhachHang_id == user.pk:  # user là Khách hàng -> đối phương là Nhiếp ảnh gia
        nag = cuoc.MaNhiepAnhGia  # hồ sơ Nhiếp ảnh gia
        tai_khoan = nag.MaTaiKhoan  # tài khoản User của Nhiếp ảnh gia
        try:  # đọc đường dẫn ảnh đại diện
            anh = nag.AnhDaiDien.url if nag.AnhDaiDien else ''  # có ảnh thì lấy .url, không thì để trống
        except ValueError:  # file ảnh lỗi
            anh = ''  # dùng chữ cái đầu thay thế
        ho_so = duong_dan_ho_so(nag.pk)  # Khách hàng được xem hồ sơ công khai của Nhiếp ảnh gia
        vai_tro = NHAN_NHIEP_ANH_GIA  # đối phương là Nhiếp ảnh gia
    else:  # user là Nhiếp ảnh gia -> đối phương là Khách hàng
        tai_khoan = cuoc.MaKhachHang  # tài khoản Khách hàng
        anh = ''  # Khách hàng không có ảnh đại diện trong CSDL
        ho_so = ''  # Khách hàng không có trang hồ sơ công khai
        vai_tro = NHAN_KHACH_HANG  # đối phương là Khách hàng
    ten = tai_khoan.get_full_name() or tai_khoan.get_username()  # ưu tiên họ tên, không có thì dùng tên đăng nhập
    return {'ten': ten, 'anh': anh, 'chu_cai': ten[:1].upper(), 'ho_so': ho_so, 'vai_tro': vai_tro}  # gói lại cho template


def _nap_tin(truy_van):  # nạp sẵn ảnh đính kèm và tin được trả lời, tránh truy vấn lặp cho từng tin
    return truy_van.select_related('MaTinTraLoi').prefetch_related('dinh_kem', 'MaTinTraLoi__dinh_kem')  # 1 truy vấn cho mỗi quan hệ


def lay_tin_gan_nhat(cuoc, so_luong=SO_TIN_MOI_LAN, sau_ma=0):  # UC8.3: các tin gần nhất; sau_ma = mã tin đã xóa phía mình (chỉ lấy tin có mã lớn hơn)
    moi_nhat = list(_nap_tin(cuoc.tin_nhan.filter(MaTinNhan__gt=sau_ma)).order_by('-MaTinNhan')[:so_luong + 1])  # lấy dư 1 tin để biết còn tin cũ hơn không
    con_cu = len(moi_nhat) > so_luong  # còn tin cũ hơn phần đang hiện
    danh_sach = moi_nhat[:so_luong]  # chỉ giữ đúng số lượng cần hiện
    danh_sach.reverse()  # đảo lại: cũ trước, mới sau (đúng thứ tự đọc)
    return danh_sach, con_cu  # trả về danh sách và cờ còn tin cũ


def lay_tin_cu_hon(cuoc, truoc, so_luong=SO_TIN_MOI_LAN, sau_ma=0):  # UC8.3: tải thêm khi kéo lên đầu; sau_ma = mã tin đã xóa phía mình
    cu_hon = list(_nap_tin(cuoc.tin_nhan.filter(MaTinNhan__lt=truoc, MaTinNhan__gt=sau_ma)).order_by('-MaTinNhan')[:so_luong + 1])  # các tin có mã nhỏ hơn tin đầu đang hiện
    con_cu = len(cu_hon) > so_luong  # còn tin cũ hơn nữa
    danh_sach = cu_hon[:so_luong]  # giữ đúng số lượng
    danh_sach.reverse()  # cũ trước, mới sau
    return danh_sach, con_cu  # trả về danh sách và cờ


def lay_tin_moi_hon(cuoc, sau, toi_da=SO_TIN_MOI_TOI_DA):  # UC8.2: polling, chỉ lấy tin có mã lớn hơn tin cuối trình duyệt đang có
    return list(_nap_tin(cuoc.tin_nhan.filter(MaTinNhan__gt=sau)).order_by('MaTinNhan')[:toi_da])  # cũ trước, mới sau


def lam_sach_noi_dung(noi_dung):  # chuẩn hóa nội dung người dùng nhập
    chuoi = (noi_dung or '').replace('\r\n', '\n').replace('\r', '\n')  # đổi mọi kiểu xuống dòng về \n
    return chuoi.strip()  # bỏ khoảng trắng và dòng trống ở hai đầu


def kho_anh_chat():  # nơi cất ảnh chat: thư mục RIÊNG không công khai, cùng cách với delivery (kho_anh)
    goc = getattr(settings, 'PRIVATE_MEDIA_ROOT', settings.BASE_DIR / 'private_media')  # mặc định BASE_DIR/private_media
    return FileSystemStorage(location=goc)  # kho lưu file


def _kiem_tra_anh(tep):  # kiểm tra một file tải lên có đúng là ảnh hợp lệ; trả về đuôi file sẽ lưu
    ten = os.path.basename(tep.name or 'anh')[:80]  # tên để báo lỗi
    if tep.size > GIOI_HAN_ANH:  # quá nặng
        raise ValidationError(f'Mỗi ảnh tối đa {GIOI_HAN_ANH // (1024 * 1024)} MB: {ten}')  # báo lỗi
    try:  # đọc thử bằng Pillow, không tin phần đuôi file hay Content-Type do trình duyệt gửi
        with Image.open(tep) as hinh:  # mở ảnh
            dinh_dang = hinh.format  # JPEG, PNG, WEBP...
            hinh.verify()  # kiểm tra file không hỏng
    except Exception:  # không phải ảnh hoặc file hỏng
        raise ValidationError(f'"{ten}" không phải ảnh hợp lệ.')  # báo lỗi
    finally:  # luôn chạy
        tep.seek(0)  # đưa con trỏ về đầu để lát nữa lưu đủ file
    if dinh_dang not in DINH_DANG_ANH:  # định dạng lạ (GIF, SVG, BMP...)
        raise ValidationError('Chỉ nhận ảnh JPG, PNG hoặc WEBP.')  # báo lỗi
    return DINH_DANG_ANH[dinh_dang]  # đuôi file theo định dạng thật


def gui_tin_nhan(cuoc, nguoi_gui, noi_dung, ds_anh=None, ma_tra_loi=None):  # UC8.2: lưu một tin nhắn (chữ, ảnh hoặc cả hai, có thể trả lời một tin)
    ds_anh = list(ds_anh or [])  # các file ảnh tải lên
    noi_dung = lam_sach_noi_dung(noi_dung)  # làm sạch trước khi kiểm tra
    if not noi_dung and not ds_anh:  # không có chữ cũng không có ảnh
        raise ValidationError('Vui lòng nhập nội dung tin nhắn.')  # báo lỗi cho người dùng
    if len(noi_dung) > GIOI_HAN_NOI_DUNG:  # tin quá dài
        raise ValidationError(f'Tin nhắn tối đa {GIOI_HAN_NOI_DUNG} ký tự.')  # báo lỗi cho người dùng
    if len(ds_anh) > SO_ANH_TOI_DA:  # quá nhiều ảnh
        raise ValidationError(f'Mỗi tin nhắn tối đa {SO_ANH_TOI_DA} ảnh.')  # báo lỗi
    duoi = [_kiem_tra_anh(tep) for tep in ds_anh]  # kiểm tra từng ảnh TRƯỚC khi lưu bất cứ thứ gì
    tra_loi = None  # tin được trả lời
    if ma_tra_loi:  # có trả lời
        tra_loi = TinNhan.objects.filter(pk=ma_tra_loi, MaCuocTroChuyen=cuoc, DaThuHoi=False).first()  # phải cùng cuộc và chưa thu hồi
        if tra_loi is None:  # không hợp lệ
            raise ValidationError('Không thể trả lời tin nhắn này.')  # báo lỗi
    tin_anh = TinNhan(MaCuocTroChuyen=cuoc, MaNguoiGui=nguoi_gui, NoiDung='', MaTinTraLoi=tra_loi) if ds_anh else None  # tin chứa ảnh (không có chữ); đang trả lời một tin thì phần trích dẫn gắn vào tin này (góp ý C1)
    tin_chu = TinNhan(MaCuocTroChuyen=cuoc, MaNguoiGui=nguoi_gui, NoiDung=noi_dung, MaTinTraLoi=None if ds_anh else tra_loi) if noi_dung else None  # tin chứa chữ; nếu đã có tin ảnh đi kèm thì KHÔNG gắn trích dẫn lần nữa
    cac_tin = [t for t in (tin_anh, tin_chu) if t is not None]  # vừa ảnh vừa chữ thì TÁCH thành hai tin riêng (ảnh trước, chữ sau) để trả lời và thu hồi được từng phần
    for t in cac_tin:  # kiểm tra từng tin
        t.full_clean()  # gọi clean() của model: người gửi phải là Khách hàng hoặc Nhiếp ảnh gia của cuộc này
    kho = kho_anh_chat()  # kho ảnh
    da_luu = []  # các file đã ghi ra ổ đĩa (để xóa nếu giao dịch lỗi)
    try:  # lưu tin và ảnh
        with transaction.atomic():  # gói trong giao dịch
            for nguoi in (cuoc.MaKhachHang, cuoc.MaNhiepAnhGia.MaTaiKhoan):  # đảm bảo CẢ HAI người có hàng THAMGIA TRƯỚC khi có tin mới (cuộc cũ chưa có thì tin cũ coi như đã đọc)
                lay_tham_gia(cuoc, nguoi)  # tạo nếu chưa có
            for t in cac_tin:  # lưu lần lượt; mã tin tăng dần nên tin ảnh luôn đứng trước tin chữ
                t.save()  # INSERT, ThoiGianGui do Django tự điền
            for tep, dd in zip(ds_anh, duoi):  # lưu từng ảnh
                ten_luu = kho.save(f'chat/{cuoc.pk}/{uuid.uuid4().hex}{dd}', tep)  # tên file ngẫu nhiên trong thư mục của cuộc
                da_luu.append(ten_luu)  # nhớ để dọn nếu lỗi
                DinhKemTinNhan.objects.create(MaTinNhan=tin_anh, DuongDanFile=ten_luu, TenGoc=os.path.basename(tep.name or 'anh')[:255], KichThuoc=tep.size)  # ghi vào DB
            ThamGia.objects.filter(MaCuocTroChuyen=cuoc).update(DaAn=False)  # có tin mới thì cuộc trò chuyện đang ẩn của cả hai bên tự hiện lại
            ThamGia.objects.filter(MaCuocTroChuyen=cuoc, MaNguoiDung=nguoi_gui).update(MaTinDaXemCuoi=cac_tin[-1].pk, DanhDauChuaDoc=False)  # người gửi coi như đã xem tới tin của chính mình
    except Exception:  # bất kỳ lỗi nào: DB đã tự hoàn tác, còn file thì phải tự xóa
        for ten_luu in da_luu:  # các file đã ghi
            try:  # xóa từng file
                kho.delete(ten_luu)  # xóa
            except OSError:  # không xóa được thì bỏ qua
                pass
        raise  # báo lỗi lên view
    return cac_tin[-1]  # trả về tin cuối cùng vừa lưu (view chỉ cần mã này; chat.js sẽ lấy cả hai tin bằng polling)


def ngu_canh_danh_sach(user, chi_an=False):  # dữ liệu cột trái mà MỌI trang chat đều phải có: hộp thư và chi tiết dùng chung, tránh quên truyền biến
    loi = ''  # thông báo lỗi nếu không tải được danh sách
    try:  # truy vấn danh sách
        cac_cuoc = danh_sach_cuoc(user, chi_an)  # các cuộc trò chuyện của người dùng (chi_an=True: tab Đã ẩn)
    except DatabaseError:  # lỗi bất ngờ
        cac_cuoc, loi = [], LOI_TAI_LICH_SU  # danh sách rỗng kèm báo lỗi
    return {  # gói cho template _danh_sach_cuoc.html
        'cac_cuoc': cac_cuoc,  # danh sách
        'loi': loi,  # lỗi tải danh sách
        'la_khach': la_khach_hang(user),  # chọn câu chữ theo vai trò
        'chi_an': chi_an,  # đang xem tab Đã ẩn
        'tong_chua_doc': sum(1 for c in cac_cuoc if c['chua_doc']),  # số cuộc đang có tin chưa đọc (hiện trên nhãn tab "Chưa đọc")
    }  # hết gói


def danh_sach_cuoc(user, chi_an=False):  # cột trái "Tin nhắn": các cuộc của user; ghim lên đầu, rồi cuộc có tin mới nhất; chi_an=True chỉ lấy các cuộc đã ẩn (bước 4)
    if la_khach_hang(user):  # Khách hàng
        loc = Q(MaKhachHang=user)  # các cuộc do mình khởi tạo
    else:  # Nhiếp ảnh gia
        loc = Q(MaNhiepAnhGia__MaTaiKhoan=user)  # các cuộc có tài khoản của mình
    for cuoc in CuocTroChuyen.objects.filter(loc).exclude(tham_gia__MaNguoiDung=user).select_related('MaKhachHang', 'MaNhiepAnhGia__MaTaiKhoan'):  # cuộc cũ (tạo trước khi có THAMGIA) chưa có hàng của mình
        lay_tham_gia(cuoc, user)  # tạo hàng, tin cũ coi như đã đọc
    tg = ThamGia.objects.filter(MaCuocTroChuyen=OuterRef('pk'), MaNguoiDung=user)  # hàng trạng thái của CHÍNH MÌNH trong từng cuộc
    tin_cuoi = TinNhan.objects.filter(MaCuocTroChuyen=OuterRef('pk'), MaTinNhan__gt=OuterRef('xoa')).order_by('-MaTinNhan')  # tin mới nhất còn hiện với mình (bỏ phần đã xóa)
    chua_doc = (  # đếm tin của người kia mà mình chưa xem
        TinNhan.objects.filter(MaCuocTroChuyen=OuterRef('pk'), MaTinNhan__gt=OuterRef('da_xem'))  # mới hơn tin đã xem
        .filter(MaTinNhan__gt=OuterRef('xoa'))  # và chưa bị xóa phía mình
        .exclude(MaNguoiGui=user)  # tin do mình gửi không tính
        .values('MaCuocTroChuyen').annotate(n=Count('pk')).values('n')  # gom theo cuộc, lấy số đếm
    )  # hết truy vấn đếm
    cac_cuoc = (  # dựng truy vấn
        CuocTroChuyen.objects.filter(loc)  # lọc theo người dùng
        .select_related('MaKhachHang', 'MaNhiepAnhGia__MaTaiKhoan')  # nạp sẵn hai người trong cuộc
        .annotate(  # thêm cột tính toán: trạng thái riêng của mình
            da_xem=Coalesce(Subquery(tg.values('MaTinDaXemCuoi')[:1]), 0),  # mã tin đã xem
            xoa=Coalesce(Subquery(tg.values('XoaDenMaTin')[:1]), 0),  # mã tin đã xóa phía mình
            danh_dau=Subquery(tg.values('DanhDauChuaDoc')[:1]),  # tự đánh dấu chưa đọc
            da_an=Subquery(tg.values('DaAn')[:1]),  # đang ẩn
            da_ghim=Subquery(tg.values('DaGhim')[:1]),  # đang ghim
        )  # hết annotate lần 1 (các cột sau cần dùng các cột trên nên tách ra)
        .annotate(  # thêm cột tính toán: tin cuối và số chưa đọc
            noi_dung_cuoi=Subquery(tin_cuoi.values('NoiDung')[:1]),  # nội dung tin cuối
            nguoi_gui_cuoi=Subquery(tin_cuoi.values('MaNguoiGui_id')[:1]),  # người gửi tin cuối
            luc_cuoi=Coalesce(Subquery(tin_cuoi.values('ThoiGianGui')[:1]), 'NgayTao', output_field=DateTimeField()),  # giờ tin cuối, chưa có tin thì lấy giờ tạo
            so_chua_doc=Coalesce(Subquery(chua_doc), 0),  # số tin chưa đọc
            ma_tin_hien=Subquery(tin_cuoi.values('MaTinNhan')[:1]),  # mã tin cuối còn hiện với mình (NULL nếu không còn tin nào)
            thu_hoi_cuoi=Subquery(tin_cuoi.values('DaThuHoi')[:1]),  # tin cuối đã thu hồi chưa
        )  # hết annotate lần 2
        .annotate(so_anh_cuoi=Subquery(  # số ảnh đính kèm của tin cuối
            DinhKemTinNhan.objects.filter(MaTinNhan=OuterRef('ma_tin_hien')).values('MaTinNhan').annotate(n=Count('pk')).values('n')[:1]
        ))  # hết annotate lần 3
        .filter(da_an=chi_an)  # cột trái thường chỉ hiện cuộc KHÔNG ẩn
        .exclude(Q(xoa__gt=0) & Q(ma_tin_hien__isnull=True))  # cuộc đã xóa phía mình và chưa có tin mới thì biến mất khỏi danh sách
        .order_by('-da_ghim', '-luc_cuoi', '-pk')  # ghim lên đầu, trong mỗi nhóm cuộc mới nhất trước
    )  # hết truy vấn
    ket_qua = []  # danh sách đưa cho template
    for cuoc in cac_cuoc:  # duyệt từng cuộc
        doi_phuong = thong_tin_doi_phuong(cuoc, user)  # người ở phía bên kia
        cua_toi = cuoc.nguoi_gui_cuoi == user.pk  # tin cuối do chính mình gửi
        if cuoc.thu_hoi_cuoi:  # tin cuối đã thu hồi: TUYỆT ĐỐI không đưa nội dung ra
            xem_truoc = 'Bạn đã thu hồi một tin nhắn' if cua_toi else 'Tin nhắn đã bị thu hồi'  # câu thay thế
        elif cuoc.noi_dung_cuoi:  # có chữ
            xem_truoc = cuoc.noi_dung_cuoi  # nội dung
        elif cuoc.so_anh_cuoi:  # chỉ có ảnh
            xem_truoc = '[Ảnh]'  # nhãn thay thế
        else:  # chưa có tin
            xem_truoc = ''  # template hiện "Chưa có tin nhắn"
        ket_qua.append({  # gói dữ liệu một dòng
            'ma': cuoc.pk,  # mã cuộc trò chuyện (để tạo link)
            'ten': doi_phuong['ten'],  # tên đối phương
            'anh': doi_phuong['anh'],  # ảnh đối phương
            'chu_cai': doi_phuong['chu_cai'],  # chữ cái đầu khi không có ảnh
            'noi_dung': xem_truoc,  # dòng xem trước (đã xử lý tin thu hồi và tin chỉ có ảnh), rỗng nếu chưa có tin
            'thu_hoi': bool(cuoc.thu_hoi_cuoi),  # tin cuối đã thu hồi (template không in "Bạn:")
            'cua_toi': cua_toi,  # tin cuối do chính mình gửi
            'luc': cuoc.luc_cuoi,  # giờ tin cuối
            'so_chua_doc': cuoc.so_chua_doc,  # số tin chưa đọc (hiện ở huy hiệu)
            'danh_dau': bool(cuoc.danh_dau),  # tự đánh dấu chưa đọc
            'chua_doc': cuoc.so_chua_doc > 0 or bool(cuoc.danh_dau),  # in đậm dòng và lọt vào bộ lọc "Chưa đọc"
            'da_ghim': bool(cuoc.da_ghim),  # đang ghim
        })  # hết gói
    return ket_qua  # trả về danh sách


# ---------------------------------------------------------------------------------------------
# Nâng cấp chat, bước 1 đến 3: trạng thái riêng từng người (đã xem, chưa đọc)
# ---------------------------------------------------------------------------------------------

def ma_tin_cuoi(cuoc):  # mã tin lớn nhất của cuộc (0 nếu chưa có tin)
    tin = cuoc.tin_nhan.order_by('-MaTinNhan').values_list('MaTinNhan', flat=True).first()  # tin mới nhất
    return tin or 0  # chưa có tin thì 0


def lay_tham_gia(cuoc, user):  # lấy hàng trạng thái của user trong cuộc; chưa có thì tạo (cuộc cũ tạo trước khi có THAMGIA)
    tham_gia, _ = ThamGia.objects.get_or_create(  # lấy hoặc tạo
        MaCuocTroChuyen=cuoc, MaNguoiDung=user,  # theo cặp (cuộc, người)
        defaults={'MaTinDaXemCuoi': ma_tin_cuoi(cuoc)},  # tạo muộn thì các tin có sẵn coi như đã đọc, tránh báo "chưa đọc" hàng loạt
    )  # hết get_or_create
    return tham_gia  # trả về hàng trạng thái


def nguoi_con_lai(cuoc, user):  # User ở phía bên kia của cuộc (đối phương)
    if cuoc.MaKhachHang_id == user.pk:  # mình là Khách hàng
        return cuoc.MaNhiepAnhGia.MaTaiKhoan  # đối phương là tài khoản Nhiếp ảnh gia
    return cuoc.MaKhachHang  # mình là Nhiếp ảnh gia: đối phương là Khách hàng


def danh_dau_da_xem(cuoc, user, den_ma, mo_trang=False):  # ghi nhận user đã xem tới tin có mã den_ma
    den_ma = min(int(den_ma), ma_tin_cuoi(cuoc))  # không cho khai báo vượt quá tin thật sự có
    tham_gia = lay_tham_gia(cuoc, user)  # hàng trạng thái của mình
    if den_ma > tham_gia.MaTinDaXemCuoi:  # chỉ ghi khi tiến lên (không bao giờ lùi)
        ThamGia.objects.filter(pk=tham_gia.pk).update(MaTinDaXemCuoi=den_ma)  # lưu mã đã xem
    if mo_trang:  # mở trang cuộc trò chuyện: coi như đã đọc, bỏ luôn dấu "chưa đọc" tự đánh
        ThamGia.objects.filter(pk=tham_gia.pk).update(DanhDauChuaDoc=False)  # xóa dấu
    return max(den_ma, tham_gia.MaTinDaXemCuoi)  # trả về mốc đã xem hiện tại


def chuyen_danh_dau_chua_doc(cuoc, user):  # nút "Đánh dấu chưa đọc / đã đọc" ở ba chấm; trả về trạng thái MỚI (True = đang chưa đọc)
    tham_gia = lay_tham_gia(cuoc, user)  # hàng trạng thái của mình
    dang_chua_doc = tham_gia.DanhDauChuaDoc or ma_tin_cuoi_cua_doi_phuong(cuoc, user) > tham_gia.MaTinDaXemCuoi  # đang hiện là chưa đọc (do tự đánh dấu hoặc do có tin mới)
    if dang_chua_doc:  # đang chưa đọc -> chuyển thành đã đọc
        ThamGia.objects.filter(pk=tham_gia.pk).update(DanhDauChuaDoc=False, MaTinDaXemCuoi=ma_tin_cuoi(cuoc))  # đã xem hết
        return False  # trạng thái mới: đã đọc
    ThamGia.objects.filter(pk=tham_gia.pk).update(DanhDauChuaDoc=True)  # đang đã đọc -> đánh dấu chưa đọc
    return True  # trạng thái mới: chưa đọc


def ma_tin_cuoi_cua_doi_phuong(cuoc, user):  # mã tin lớn nhất do ĐỐI PHƯƠNG gửi (0 nếu chưa có)
    tin = cuoc.tin_nhan.exclude(MaNguoiGui=user).order_by('-MaTinNhan').values_list('MaTinNhan', flat=True).first()  # tin cuối của đối phương
    return tin or 0  # chưa có thì 0


def doi_phuong_da_xem_toi(cuoc, user):  # mã tin lớn nhất mà ĐỐI PHƯƠNG đã xem (để hiện "Đã xem" dưới tin của mình)
    return lay_tham_gia(cuoc, nguoi_con_lai(cuoc, user)).MaTinDaXemCuoi  # mốc đã xem của đối phương


# ---------------------------------------------------------------------------------------------
# Nâng cấp chat, bước 4 đến 6: ghim, ẩn, xóa, ảnh, thu hồi
# ---------------------------------------------------------------------------------------------

def chuyen_ghim(cuoc, user):  # Ghim / Bỏ ghim; trả về trạng thái MỚI (True = đang ghim)
    tham_gia = lay_tham_gia(cuoc, user)  # hàng trạng thái của mình
    moi = not tham_gia.DaGhim  # đảo trạng thái
    ThamGia.objects.filter(pk=tham_gia.pk).update(DaGhim=moi, GhimLuc=timezone.now() if moi else None)  # lưu
    return moi  # trạng thái mới


def chuyen_an(cuoc, user):  # Ẩn / Bỏ ẩn cuộc trò chuyện; trả về trạng thái MỚI (True = đang ẩn)
    tham_gia = lay_tham_gia(cuoc, user)  # hàng trạng thái của mình
    moi = not tham_gia.DaAn  # đảo trạng thái
    ThamGia.objects.filter(pk=tham_gia.pk).update(DaAn=moi)  # lưu (ẩn thì giữ nguyên ghim và lịch sử; có tin mới sẽ tự hiện lại)
    return moi  # trạng thái mới


def xoa_cuoc_phia_minh(cuoc, user):  # "Xóa cuộc trò chuyện": chỉ xóa PHÍA MÌNH, người kia vẫn thấy toàn bộ
    tham_gia = lay_tham_gia(cuoc, user)  # hàng trạng thái của mình
    ma = ma_tin_cuoi(cuoc)  # mốc: mọi tin có mã <= ma sẽ không hiện cho mình nữa
    ThamGia.objects.filter(pk=tham_gia.pk).update(XoaDenMaTin=ma, MaTinDaXemCuoi=ma, DaAn=False, DaGhim=False, GhimLuc=None, DanhDauChuaDoc=False)  # có tin mới thì cuộc tự hiện lại
    return True  # đã xóa


def thu_hoi_tin(cuoc, user, ma_tin):  # thu hồi một tin: chỉ NGƯỜI GỬI, nội dung vẫn giữ trong DB để Quản trị viên xem khi có tranh chấp
    tin = cuoc.tin_nhan.filter(pk=ma_tin).first()  # tin phải thuộc cuộc này
    if tin is None:  # không có
        raise Http404('Không tìm thấy tin nhắn.')  # 404
    if tin.MaNguoiGui_id != user.pk:  # không phải tin của mình
        raise PermissionDenied('Chỉ người gửi mới thu hồi được tin nhắn.')  # 403
    if not tin.DaThuHoi:  # chưa thu hồi
        TinNhan.objects.filter(pk=tin.pk).update(DaThuHoi=True, ThuHoiLuc=timezone.now())  # đánh dấu, KHÔNG xóa nội dung
    return tin  # trả về tin


def tin_da_thu_hoi(cuoc, tu_ma):  # các tin đã thu hồi có mã >= tu_ma (chat.js dùng để cập nhật các bong bóng đang hiện)
    return list(cuoc.tin_nhan.filter(DaThuHoi=True, MaTinNhan__gte=tu_ma).values_list('MaTinNhan', flat=True))  # danh sách mã


def han_luu_anh():  # mốc thời gian cũ nhất còn được lưu ảnh: ảnh của tin gửi trước mốc này đã hết hạn
    return timezone.now() - timedelta(days=THOI_HAN_ANH_NGAY)  # bây giờ lùi 183 ngày (6 tháng)


def anh_het_han(tin):  # True nếu ảnh trong tin đã quá 6 tháng kể từ lúc gửi (không còn xem được)
    return tin.ThoiGianGui < han_luu_anh()  # so giờ gửi với mốc hết hạn


def lay_anh_chia_se(cuoc, sau_ma=0, gioi_han=300):  # ảnh hiện ở cột phải: mới nhất trước, bỏ ảnh của tin đã thu hồi, phần đã xóa phía mình và ảnh quá 6 tháng
    return list(DinhKemTinNhan.objects.select_related('MaTinNhan').filter(  # nạp sẵn tin để lấy giờ gửi, không tốn truy vấn lặp
        MaTinNhan__MaCuocTroChuyen=cuoc, MaTinNhan__MaTinNhan__gt=sau_ma, MaTinNhan__DaThuHoi=False,  # đúng cuộc, chưa xóa, chưa thu hồi
        MaTinNhan__ThoiGianGui__gte=han_luu_anh(),  # còn trong hạn lưu 6 tháng
    ).order_by('-MaDinhKem')[:gioi_han])  # mới nhất trước, tối đa gioi_han ảnh


def nhom_anh_theo_thang(ds_anh):  # chia danh sách ảnh (mới nhất trước) thành từng tháng giống Messenger: [{khoa, nhan, anh}]
    nam_nay = timezone.localtime().year  # năm hiện tại, tháng của năm nay chỉ ghi "Tháng 11"
    nhom = []  # kết quả
    for dk in ds_anh:  # duyệt từng ảnh
        luc = timezone.localtime(dk.MaTinNhan.ThoiGianGui)  # giờ gửi theo giờ địa phương
        khoa = '%d-%02d' % (luc.year, luc.month)  # khóa tháng, vd 2026-11 (chat.js dùng cùng cách đặt khóa)
        if not nhom or nhom[-1]['khoa'] != khoa:  # sang tháng mới thì mở nhóm mới
            nhan = 'Tháng %d' % luc.month if luc.year == nam_nay else 'Tháng %d/%d' % (luc.month, luc.year)  # tháng của năm khác ghi kèm năm
            nhom.append({'khoa': khoa, 'nhan': nhan, 'anh': []})  # nhóm trống
        nhom[-1]['anh'].append(dk)  # xếp ảnh vào nhóm cuối
    return nhom  # hết


# ----- góp ý kiểm thử chéo D2, case C2: link bấm được trong tin và mục "Liên kết" ở cột phải -----
MAU_LIEN_KET = re.compile(r'(?<!\w)(?:https?://|www\.)[^\s<>"\']+', re.IGNORECASE)  # chuỗi bắt đầu bằng http://, https:// hoặc www. và chạy tới khi gặp khoảng trắng hoặc < > " '
KY_TU_CUOI_LIEN_KET = '.,;:!?)]}'  # dấu câu dính ở cuối (vd "xem https://a.com.") không thuộc về link
TOI_DA_LIEN_KET = 100  # cột phải hiện tối đa 100 liên kết
TOI_DA_QUET_LIEN_KET = 300  # mỗi lần chỉ quét 300 tin có chứa link gần nhất


def tim_lien_ket(noi_dung):  # tìm các link trong một tin; trả về [{bat_dau, ket_thuc, href, hien_thi}] theo thứ tự xuất hiện
    ket_qua = []  # danh sách link tìm được
    for khop in MAU_LIEN_KET.finditer(noi_dung or ''):  # duyệt từng chuỗi giống link
        chu = khop.group(0).rstrip(KY_TU_CUOI_LIEN_KET)  # bỏ dấu câu dính cuối
        if chu.lower() in ('http://', 'https://', 'www.'):  # chỉ còn phần mở đầu thì không phải link
            continue  # bỏ qua
        href = chu if chu.lower().startswith('http') else 'https://' + chu  # www.abc.com thì thêm https:// (chỉ http, https mới được bấm, không có javascript:)
        hien_thi = re.sub(r'^https?://', '', chu, flags=re.IGNORECASE).rstrip('/')  # chữ ngắn gọn cho cột phải, bỏ http(s)://
        ket_qua.append({'bat_dau': khop.start(), 'ket_thuc': khop.start() + len(chu), 'href': href, 'hien_thi': hien_thi})  # ghi vị trí để template cắt đúng chỗ
    return ket_qua  # trả về danh sách


def lay_lien_ket_chia_se(cuoc, sau_ma=0, gioi_han=TOI_DA_LIEN_KET):  # link hiện ở cột phải: mới nhất trước, bỏ tin đã thu hồi và phần đã xóa phía mình, mỗi link chỉ một lần
    truy_van = cuoc.tin_nhan.filter(DaThuHoi=False, MaTinNhan__gt=sau_ma).filter(  # đúng cuộc, chưa thu hồi, chưa xóa phía mình
        Q(NoiDung__icontains='http') | Q(NoiDung__icontains='www.')  # chỉ lấy tin có thể chứa link cho nhẹ
    ).order_by('-MaTinNhan').values_list('MaTinNhan', 'NoiDung')[:TOI_DA_QUET_LIEN_KET]  # mới nhất trước, chỉ 2 cột
    da_co = set()  # các link đã lấy (không lặp)
    ket_qua = []  # danh sách đưa cho template
    for ma, noi_dung in truy_van:  # duyệt từ tin mới đến cũ
        for lk in tim_lien_ket(noi_dung):  # từng link trong tin
            if lk['href'] in da_co:  # đã có link này (ở tin mới hơn)
                continue  # bỏ qua
            da_co.add(lk['href'])  # ghi nhớ
            ket_qua.append({'ma_tin': ma, 'url': lk['href'], 'hien_thi': lk['hien_thi']})  # ma_tin để chat.js gỡ link khi tin bị thu hồi
            if len(ket_qua) >= gioi_han:  # đủ số lượng
                return ket_qua  # dừng
    return ket_qua  # trả về danh sách


def mo_anh_chat(user, ma_dinh_kem):  # trang xem ảnh: chỉ hai người trong cuộc, không xem được ảnh đã thu hồi hoặc đã xóa phía mình
    dinh_kem = get_object_or_404(DinhKemTinNhan.objects.select_related('MaTinNhan'), pk=ma_dinh_kem)  # không có thì 404
    tin = dinh_kem.MaTinNhan  # tin chứa ảnh
    cuoc = lay_cuoc_cua_nguoi_dung(user, tin.MaCuocTroChuyen_id)  # người ngoài cuộc bị 404
    if tin.DaThuHoi or anh_het_han(tin) or tin.pk <= lay_tham_gia(cuoc, user).XoaDenMaTin:  # đã thu hồi, quá 6 tháng hoặc đã xóa phía mình
        raise Http404('Không tìm thấy ảnh.')  # 404
    return dinh_kem, kho_anh_chat()  # ảnh và kho chứa


# ----- bước 7: tìm trong cuộc trò chuyện -----
def _bo_dau_ky_tu(ky):  # một ký tự thành đúng MỘT ký tự thường không dấu (giữ nguyên độ dài chuỗi để tính vị trí)
    if ky in ('đ', 'Đ'):  # đ không tách dấu được bằng unicode nên xử lý riêng
        return 'd'  # đ -> d
    goc = ''.join(c for c in unicodedata.normalize('NFD', ky) if not unicodedata.combining(c))  # tách dấu rồi bỏ dấu
    return (goc or ky).lower()[:1]  # lấy đúng 1 ký tự thường


def bo_dau(chuoi):  # "Phạnh" -> "phanh": chuỗi không dấu, thường, cùng độ dài với chuỗi gốc
    return ''.join(_bo_dau_ky_tu(ky) for ky in chuoi)  # ghép từng ký tự đã bỏ dấu


def _trich_doan(noi_dung, vi_tri, do_dai):  # cắt đoạn ngắn quanh chỗ khớp để hiện trong danh sách kết quả
    dau = max(0, vi_tri - 25)  # lấy trước chỗ khớp 25 ký tự
    cuoi = min(len(noi_dung), vi_tri + do_dai + 45)  # lấy sau chỗ khớp 45 ký tự
    doan = ' '.join(noi_dung[dau:cuoi].split())  # gộp xuống dòng và khoảng trắng thừa thành một dòng
    return ('…' if dau > 0 else '') + doan + ('…' if cuoi < len(noi_dung) else '')  # thêm … nếu bị cắt


def tim_trong_cuoc(cuoc, user, tu_khoa):  # tìm tin có chứa từ khóa (không phân biệt hoa thường và dấu); trả (danh sách kết quả mới nhất trước, có bị cắt bớt không)
    tu = bo_dau((tu_khoa or '').strip()[:GIOI_HAN_TU_KHOA_TIM])  # từ khóa đã chuẩn hóa
    if not tu:  # từ khóa rỗng
        return [], False  # không có kết quả
    sau_ma = lay_tham_gia(cuoc, user).XoaDenMaTin  # phần đã xóa phía mình không được tìm ra
    truy_van = cuoc.tin_nhan.filter(DaThuHoi=False, MaTinNhan__gt=sau_ma).exclude(NoiDung='').order_by('-MaTinNhan').values_list(  # tin đã thu hồi và tin chỉ có ảnh không có chữ để tìm
        'MaTinNhan', 'NoiDung', 'ThoiGianGui', 'MaNguoiGui_id')[:TOI_DA_QUET_TIN]  # chỉ lấy 4 cột, tối đa 5000 tin gần nhất
    ket_qua = []  # danh sách kết quả
    bi_cat = False  # có nhiều hơn mức tối đa không
    for ma, noi_dung, luc, ma_gui in truy_van:  # duyệt từ tin mới đến cũ
        vi_tri = bo_dau(noi_dung).find(tu)  # tìm trên bản không dấu
        if vi_tri == -1:  # không khớp
            continue  # sang tin kế
        if len(ket_qua) >= TOI_DA_KET_QUA_TIM:  # đã đủ 100 mà vẫn còn khớp
            bi_cat = True  # báo còn nữa
            break  # dừng
        ket_qua.append({  # thêm một kết quả
            'id': ma,  # mã tin, chat.js dùng để nhảy tới tin
            'trich': _trich_doan(noi_dung, vi_tri, len(tu)),  # đoạn trích quanh chỗ khớp
            'luc': timezone.localtime(luc).strftime('%d/%m/%Y %H:%M'),  # giờ gửi
            'cua_toi': ma_gui == user.pk,  # tin của chính mình thì ghi "Bạn:"
        })
    return ket_qua, bi_cat  # trả kết quả


def lay_tin_den_tin(cuoc, ma_tin, truoc, sau_ma=0):  # tải các tin từ (ma_tin - 10 tin) tới trước tin đầu đang hiện, để nhảy tới một tin cũ chưa tải; trả (danh sách, còn tin cũ hơn), danh sách None nếu quá xa
    gan = list(cuoc.tin_nhan.filter(MaTinNhan__lt=ma_tin, MaTinNhan__gt=sau_ma).order_by('-MaTinNhan').values_list('MaTinNhan', flat=True)[:SO_TIN_NGU_CANH_TIM])  # 10 tin ngay trước tin cần tới
    bat_dau = gan[-1] if gan else ma_tin  # mã tin đầu của đoạn cần tải
    danh_sach = list(_nap_tin(cuoc.tin_nhan.filter(MaTinNhan__gte=max(bat_dau, sau_ma + 1), MaTinNhan__lt=truoc)).order_by('MaTinNhan')[:TOI_DA_TIN_NHAY + 1])  # đoạn liền mạch, cũ trước mới sau
    if len(danh_sach) > TOI_DA_TIN_NHAY:  # quá dài
        return None, False  # báo quá xa
    con_cu = bool(danh_sach) and cuoc.tin_nhan.filter(MaTinNhan__lt=danh_sach[0].pk, MaTinNhan__gt=sau_ma).exists()  # còn tin cũ hơn đoạn vừa tải không
    return danh_sach, con_cu  # trả kết quả
