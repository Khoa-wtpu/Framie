# chat/services.py - P10 (UC8.1) và P11 (UC8.2, UC8.3): logic nghiệp vụ. View và template chỉ gọi các hàm ở đây.
from django.core.exceptions import ValidationError  # lỗi dữ liệu không hợp lệ (tin rỗng, tin quá dài)
from django.db import DatabaseError, IntegrityError, transaction  # IntegrityError: lỗi trùng khóa; transaction: gói lệnh lưu cho an toàn
from django.db.models import DateTimeField, OuterRef, Q, Subquery  # Q: điều kiện OR; Subquery/OuterRef: lấy tin cuối của từng cuộc
from django.db.models.functions import Coalesce  # lấy giá trị đầu tiên khác NULL
from django.http import Http404  # lỗi "không tìm thấy trang"
from django.shortcuts import get_object_or_404  # tìm đối tượng hoặc báo 404
from django.urls import NoReverseMatch, reverse  # đổi tên URL (name=...) thành đường dẫn

from chat.models import CuocTroChuyen, TinNhan  # bảng cuộc trò chuyện và bảng tin nhắn (Module 8)
from core.constants import TrangThaiHoSo, VaiTro  # tên vai trò và tên trạng thái hồ sơ, không tự gõ chữ tiếng Việt

SO_TIN_MOI_LAN = 30  # mỗi lần tải: 30 tin gần nhất, kéo lên trên thì tải thêm 30 tin cũ hơn (giống Messenger)
SO_TIN_MOI_TOI_DA = 100  # một lần polling trả tối đa 100 tin mới, tránh trả quá nặng nếu mất kết nối lâu
GIOI_HAN_NOI_DUNG = 2000  # tin nhắn tối đa 2000 ký tự (cột NoiDung kiểu TEXT không tự giới hạn)
LOI_GUI_TIN = 'Không thể gửi tin nhắn. Vui lòng thử lại.'  # luồng ngoại lệ 5a của UC8.2
LOI_TAI_LICH_SU = 'Không thể tải lịch sử trao đổi. Vui lòng thực hiện lại.'  # luồng ngoại lệ 2a của UC8.3
LOI_KHOI_TAO = 'Không thể khởi tạo cuộc trò chuyện. Vui lòng thực hiện lại.'  # luồng ngoại lệ 2a của UC8.1
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


def lay_tin_gan_nhat(cuoc, so_luong=SO_TIN_MOI_LAN):  # UC8.3: các tin gần nhất để hiện khi mở cuộc trò chuyện
    moi_nhat = list(cuoc.tin_nhan.order_by('-MaTinNhan')[:so_luong + 1])  # lấy dư 1 tin để biết còn tin cũ hơn không
    con_cu = len(moi_nhat) > so_luong  # còn tin cũ hơn phần đang hiện
    danh_sach = moi_nhat[:so_luong]  # chỉ giữ đúng số lượng cần hiện
    danh_sach.reverse()  # đảo lại: cũ trước, mới sau (đúng thứ tự đọc)
    return danh_sach, con_cu  # trả về danh sách và cờ còn tin cũ


def lay_tin_cu_hon(cuoc, truoc, so_luong=SO_TIN_MOI_LAN):  # UC8.3: tải thêm khi người dùng kéo lên đầu danh sách
    cu_hon = list(cuoc.tin_nhan.filter(MaTinNhan__lt=truoc).order_by('-MaTinNhan')[:so_luong + 1])  # các tin có mã nhỏ hơn tin đầu đang hiện
    con_cu = len(cu_hon) > so_luong  # còn tin cũ hơn nữa
    danh_sach = cu_hon[:so_luong]  # giữ đúng số lượng
    danh_sach.reverse()  # cũ trước, mới sau
    return danh_sach, con_cu  # trả về danh sách và cờ


def lay_tin_moi_hon(cuoc, sau, toi_da=SO_TIN_MOI_TOI_DA):  # UC8.2: polling, chỉ lấy tin có mã lớn hơn tin cuối trình duyệt đang có
    return list(cuoc.tin_nhan.filter(MaTinNhan__gt=sau).order_by('MaTinNhan')[:toi_da])  # cũ trước, mới sau


def lam_sach_noi_dung(noi_dung):  # chuẩn hóa nội dung người dùng nhập
    chuoi = (noi_dung or '').replace('\r\n', '\n').replace('\r', '\n')  # đổi mọi kiểu xuống dòng về \n
    return chuoi.strip()  # bỏ khoảng trắng và dòng trống ở hai đầu


def gui_tin_nhan(cuoc, nguoi_gui, noi_dung):  # UC8.2: lưu một tin nhắn vào lịch sử trao đổi
    noi_dung = lam_sach_noi_dung(noi_dung)  # làm sạch trước khi kiểm tra
    if not noi_dung:  # tin rỗng
        raise ValidationError('Vui lòng nhập nội dung tin nhắn.')  # báo lỗi cho người dùng
    if len(noi_dung) > GIOI_HAN_NOI_DUNG:  # tin quá dài
        raise ValidationError(f'Tin nhắn tối đa {GIOI_HAN_NOI_DUNG} ký tự.')  # báo lỗi cho người dùng
    tin = TinNhan(MaCuocTroChuyen=cuoc, MaNguoiGui=nguoi_gui, NoiDung=noi_dung)  # dựng tin nhắn (chưa lưu)
    tin.full_clean()  # gọi clean() của model: người gửi phải là Khách hàng hoặc Nhiếp ảnh gia của cuộc này
    with transaction.atomic():  # gói trong giao dịch
        tin.save()  # INSERT, ThoiGianGui do Django tự điền
    return tin  # trả về tin vừa lưu


def ngu_canh_danh_sach(user):  # dữ liệu cột trái mà MỌI trang chat đều phải có: hộp thư và chi tiết dùng chung, tránh quên truyền biến
    loi = ''  # thông báo lỗi nếu không tải được danh sách
    try:  # truy vấn danh sách
        cac_cuoc = danh_sach_cuoc(user)  # các cuộc trò chuyện của người dùng
    except DatabaseError:  # lỗi bất ngờ
        cac_cuoc, loi = [], LOI_TAI_LICH_SU  # danh sách rỗng kèm báo lỗi
    return {  # gói cho template _danh_sach_cuoc.html
        'cac_cuoc': cac_cuoc,  # danh sách
        'loi': loi,  # lỗi tải danh sách
        'la_khach': la_khach_hang(user),  # chọn câu chữ theo vai trò
    }  # hết gói


def danh_sach_cuoc(user):  # màn hình danh sách "Tin nhắn": các cuộc trò chuyện của user, cuộc có tin mới nhất lên đầu
    if la_khach_hang(user):  # Khách hàng
        loc = Q(MaKhachHang=user)  # các cuộc do mình khởi tạo
    else:  # Nhiếp ảnh gia
        loc = Q(MaNhiepAnhGia__MaTaiKhoan=user)  # các cuộc có tài khoản của mình
    tin_cuoi = TinNhan.objects.filter(MaCuocTroChuyen=OuterRef('pk')).order_by('-MaTinNhan')  # tin mới nhất của từng cuộc
    cac_cuoc = (  # dựng truy vấn
        CuocTroChuyen.objects.filter(loc)  # lọc theo người dùng
        .select_related('MaKhachHang', 'MaNhiepAnhGia__MaTaiKhoan')  # nạp sẵn hai người trong cuộc
        .annotate(  # thêm 3 cột tính toán
            noi_dung_cuoi=Subquery(tin_cuoi.values('NoiDung')[:1]),  # nội dung tin cuối
            nguoi_gui_cuoi=Subquery(tin_cuoi.values('MaNguoiGui_id')[:1]),  # người gửi tin cuối
            luc_cuoi=Coalesce(Subquery(tin_cuoi.values('ThoiGianGui')[:1]), 'NgayTao', output_field=DateTimeField()),  # giờ tin cuối, chưa có tin thì lấy giờ tạo
        )  # hết annotate
        .order_by('-luc_cuoi', '-pk')  # mới nhất lên đầu
    )  # hết truy vấn
    ket_qua = []  # danh sách đưa cho template
    for cuoc in cac_cuoc:  # duyệt từng cuộc
        doi_phuong = thong_tin_doi_phuong(cuoc, user)  # người ở phía bên kia
        ket_qua.append({  # gói dữ liệu một dòng
            'ma': cuoc.pk,  # mã cuộc trò chuyện (để tạo link)
            'ten': doi_phuong['ten'],  # tên đối phương
            'anh': doi_phuong['anh'],  # ảnh đối phương
            'chu_cai': doi_phuong['chu_cai'],  # chữ cái đầu khi không có ảnh
            'noi_dung': cuoc.noi_dung_cuoi or '',  # nội dung tin cuối, rỗng nếu chưa có tin
            'cua_toi': cuoc.nguoi_gui_cuoi == user.pk,  # tin cuối do chính mình gửi
            'luc': cuoc.luc_cuoi,  # giờ tin cuối
        })  # hết gói
    return ket_qua  # trả về danh sách
