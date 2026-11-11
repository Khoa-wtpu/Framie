# =====================================================================
# search/tro_ly.py  -  E4: Form 5 bước và trang kết quả của Trợ lý chọn Nhiếp ảnh gia (UC2.3, FR-39) (Phanh)
#
#   assistant         /tro-ly/            Form 5 bước. Mỗi bước là một lần mở trang: /tro-ly/?buoc=1 ... ?buoc=5
#   assistant_result  /tro-ly/ket-qua/    Gọi goi_y_nhiep_anh_gia() của Khoa và hiện thẻ kết quả
#
# Quy tắc (E1, mục 2.5):
#   - Chỉ Khách hàng đã đăng nhập (dùng khach_hang_required của bookings/giu_cho.py).
#   - Câu trả lời lưu trong session, khóa 'tro_ly_tra_loi'. Không thêm bảng, không migration.
#   - Session chỉ lưu được JSON, nên ngày lưu thành chuỗi 'YYYY-MM-DD', ngân sách lưu thành chuỗi số ('' = không giới hạn).
#     Trước khi gọi hàm của Khoa mới đổi lại thành date và Decimal (hàm _tra_loi_cho_goi_y).
#   - Mỗi khung giờ là một nút POST tới chon_slot, kèm ma_nhiep_anh_gia (giống trang lich_chon_slot). Không viết lại luồng giữ chỗ.
# =====================================================================
from datetime import date, timedelta  # date: ngày chụp; timedelta: cộng ngày để tính ngày xa nhất được chọn
from decimal import Decimal  # Decimal: ngân sách phải là Decimal, không dùng float (E1, mục 2.2)

from django import forms  # công cụ tạo form (ChoiceField, DateField...)
from django.contrib import messages  # thông báo ngắn hiện ở đầu trang (includes/messages.html)
from django.core.exceptions import ValidationError  # lỗi kiểm tra dữ liệu; hàm của Khoa cũng ném lỗi này
from django.shortcuts import redirect, render  # redirect: chuyển trang; render: hiện template
from django.urls import reverse  # đổi tên URL thành đường dẫn
from django.utils import timezone  # lấy ngày hôm nay theo múi giờ của dự án
from django.views.decorators.http import require_GET, require_http_methods  # giới hạn phương thức HTTP của view

from accounts.permissions import url_trang_chu  # trang tổng quan theo vai trò: nơi nút "Bỏ qua" chuyển tới
from bookings.giu_cho import khach_hang_required  # chỉ cho Khách hàng đã đăng nhập (chưa đăng nhập thì chuyển về login)
from profiles.models import KhuVuc, LoaiHinhChup, PhongCach  # ba danh mục để tạo đáp án chọn sẵn
from search.goi_y import (  # hàm và hằng số của Khoa (E3); KHÔNG tự đặt lại các con số này
    SO_NGAY_CHON_TOI_DA, TOI_DA_PHONG_CACH, goi_y_nhiep_anh_gia, goi_y_noi_tieu_chi, kiem_tra_cau_tra_loi,
)
from search.services import dinh_dang_tien  # đổi số tiền thành chữ, ví dụ 2.000.000đ (cùng cách Khoa đang dùng)


# ---------------------------------------------------------------------
# Hằng số
# ---------------------------------------------------------------------
KHOA_SESSION = 'tro_ly_tra_loi'  # khóa lưu câu trả lời trong session (E1 chốt tên này)
CAC_CAU = ('loai_hinh', 'khu_vuc', 'ngan_sach', 'ngay_chup', 'phong_cach')  # khóa của 5 câu, đúng thứ tự bước 1 đến 5 (trùng khóa hợp đồng E1)
TONG_BUOC = len(CAC_CAU)  # tổng số bước = 5
MUC_NGAN_SACH = (  # 4 mức ngân sách chọn sẵn (E1, mục 2.1): (giá trị lưu, chữ hiện cho khách)
    ('2000000', 'Dưới 2 triệu'),  # mức 1: 2.000.000đ
    ('3000000', 'Dưới 3 triệu'),  # mức 2: 3.000.000đ
    ('5000000', 'Dưới 5 triệu'),  # mức 3: 5.000.000đ
    ('khong', 'Không giới hạn'),  # mức 4: không đặt ngân sách (lưu thành chuỗi rỗng)
)
GIA_TRI_KHONG_GIOI_HAN = 'khong'  # giá trị của mức "Không giới hạn" trong form
NHAN_NGAN_SACH = {Decimal(v): nhan for v, nhan in MUC_NGAN_SACH if v != GIA_TRI_KHONG_GIOI_HAN}  # {Decimal: chữ} để hiện tóm tắt
CHIP_CHUA_CO_DANH_GIA = 'Chưa có đánh giá'  # chuỗi chip Khoa dùng trong goi_y.py; trang kết quả hiện dòng riêng nên bỏ chip này (xem _the_ket_qua)


# ---------------------------------------------------------------------
# Ngày chụp hợp lệ: từ hôm nay đến hôm nay + 29 (khớp luật của goi_y.kiem_tra_cau_tra_loi)
# ---------------------------------------------------------------------
def _ngay_toi_da():  # ngày xa nhất được chọn
    return timezone.localdate() + timedelta(days=SO_NGAY_CHON_TOI_DA - 1)  # hôm nay + 29 (30 ngày tính cả hôm nay)


def _ngay_hop_le(ngay):  # True nếu ngày nằm trong khoảng được chọn
    return timezone.localdate() <= ngay <= _ngay_toi_da()  # không ở quá khứ và không quá hôm nay + 29


THU_VIET = ('T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN')  # nhãn thứ viết tắt, thứ tự theo date.weekday() (0 = thứ Hai)
SO_NGAY_NHANH = 7  # số ngày hiện ở hàng chọn nhanh (từ hôm nay)


def _ngay_nhanh():  # danh sách ngày chọn nhanh cho bước 4: [{'iso','thu','so'}]
    hom_nay = timezone.localdate()  # hôm nay theo múi giờ dự án
    ds = []  # kết quả
    for i in range(SO_NGAY_NHANH):  # 7 ngày liên tiếp
        ngay = hom_nay + timedelta(days=i)  # ngày thứ i kể từ hôm nay
        if ngay > _ngay_toi_da():  # phòng khi hằng của Khoa nhỏ hơn 7 ngày
            break  # không hiện ngày không được chọn
        ds.append({'iso': ngay.isoformat(), 'thu': THU_VIET[ngay.weekday()], 'so': ngay.day})  # một ô ngày
    return ds  # trả danh sách


# ---------------------------------------------------------------------
# Form: mỗi bước một form, mỗi form đúng một ô tên 'dap_an' (để template dùng chung cho cả 5 bước)
# ---------------------------------------------------------------------
class _FormChonMot(forms.Form):  # lớp cha cho các câu "chọn 1 trong danh sách"
    KIEU = 'chon_mot'  # cho template biết cách vẽ: nhóm nút chọn một
    NHAN = ''  # câu hỏi (lớp con điền)
    TB_THIEU = ''  # câu báo khi khách chưa chọn (lớp con điền)
    TB_SAI = ''  # câu báo khi giá trị gửi lên không nằm trong danh sách (lớp con điền)
    GOI_Y = ''  # dòng phụ dưới câu hỏi (giao diện mới; lớp con điền)
    BO_CUC = 'luoi'  # cách xếp đáp án: 'luoi' (ô lớn đánh số) hoặc 'danh_sach' (mỗi đáp án một dòng)
    dap_an = forms.ChoiceField(widget=forms.RadioSelect, choices=())  # ô chọn một, danh sách chọn điền ở __init__

    def lua_chon(self):  # lớp con trả về danh sách [(giá trị, chữ hiện)]
        raise NotImplementedError  # lớp cha không dùng trực tiếp

    def __init__(self, *args, **kwargs):  # chạy mỗi lần tạo form
        super().__init__(*args, **kwargs)  # để Django dựng form như thường
        truong = self.fields['dap_an']  # lấy ô đáp án của form này (mỗi form có bản sao riêng)
        truong.label = self.NHAN  # đặt câu hỏi làm nhãn
        truong.help_text = self.GOI_Y  # dòng phụ hiện dưới câu hỏi
        truong.choices = self.lua_chon()  # đọc danh mục tại thời điểm mở trang, không đọc lúc import
        truong.error_messages['required'] = self.TB_THIEU  # câu báo khi bỏ trống
        truong.error_messages['invalid_choice'] = self.TB_SAI  # câu báo khi chọn giá trị lạ


class BuocLoaiHinhForm(_FormChonMot):  # câu 1
    NHAN = 'Bạn muốn chụp loại hình nào?'  # câu hỏi
    TB_THIEU = 'Vui lòng chọn một loại hình chụp.'  # báo khi bỏ trống
    TB_SAI = 'Loại hình chụp không hợp lệ.'  # báo khi chọn sai
    GOI_Y = 'Chọn một loại hình để Trợ lý gợi ý đúng chuyên môn.'  # dòng phụ

    def lua_chon(self):  # danh sách đáp án lấy từ bảng Loại hình chụp
        return list(LoaiHinhChup.objects.order_by('TenLoaiHinh').values_list('pk', 'TenLoaiHinh'))  # [(mã, tên)]


class BuocKhuVucForm(_FormChonMot):  # câu 2
    NHAN = 'Bạn chụp ở khu vực nào?'  # câu hỏi
    TB_THIEU = 'Vui lòng chọn một khu vực.'  # báo khi bỏ trống
    TB_SAI = 'Khu vực không hợp lệ.'  # báo khi chọn sai
    GOI_Y = 'Nhiếp ảnh gia được lọc theo khu vực hoạt động.'  # dòng phụ

    def lua_chon(self):  # danh sách đáp án lấy từ bảng Khu vực
        return list(KhuVuc.objects.order_by('TenKhuVuc').values_list('pk', 'TenKhuVuc'))  # [(mã, tên)]


class BuocNganSachForm(_FormChonMot):  # câu 3
    NHAN = 'Ngân sách tối đa cho một gói?'  # câu hỏi
    TB_THIEU = 'Vui lòng chọn một mức ngân sách.'  # báo khi bỏ trống
    TB_SAI = 'Mức ngân sách không hợp lệ.'  # báo khi chọn sai
    GOI_Y = 'Chọn mức trần giá gói bạn sẵn sàng chi.'  # dòng phụ
    BO_CUC = 'danh_sach'  # 4 mức ngân sách xếp thành danh sách dọc

    def lua_chon(self):  # 4 mức cố định
        return list(MUC_NGAN_SACH)  # [(giá trị, chữ)]


class BuocNgayForm(forms.Form):  # câu 4
    KIEU = 'ngay'  # cho template biết: vẽ ô chọn ngày bằng form_field.html
    dap_an = forms.DateField(  # ô chọn ngày
        label='Bạn muốn chụp ngày nào?',  # câu hỏi
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),  # ô lịch của trình duyệt, giá trị dạng YYYY-MM-DD
        error_messages={'required': 'Vui lòng chọn ngày chụp.', 'invalid': 'Ngày chụp không hợp lệ.'},  # câu báo lỗi tiếng Việt
    )

    def __init__(self, *args, **kwargs):  # chạy mỗi lần tạo form
        super().__init__(*args, **kwargs)  # để Django dựng form như thường
        truong = self.fields['dap_an']  # ô ngày của form này
        truong.widget.attrs['min'] = timezone.localdate().isoformat()  # trình duyệt chặn chọn ngày quá khứ
        truong.widget.attrs['max'] = _ngay_toi_da().isoformat()  # trình duyệt chặn chọn quá hôm nay + 29
        truong.help_text = f'Chọn từ hôm nay đến {_ngay_toi_da():%d/%m/%Y}.'  # dòng gợi ý dưới ô (form_field.html tự hiện help_text)

    def clean_dap_an(self):  # kiểm tra thêm ở phía máy chủ (trình duyệt chặn được nhưng không tin hoàn toàn)
        ngay = self.cleaned_data['dap_an']  # ngày đã đổi thành date
        if not _ngay_hop_le(ngay):  # ngoài khoảng cho phép
            raise ValidationError(f'Chỉ chọn được ngày từ hôm nay đến {_ngay_toi_da():%d/%m/%Y}.')  # báo lỗi ngay dưới ô
        return ngay  # hợp lệ thì trả lại ngày


class BuocPhongCachForm(forms.Form):  # câu 5
    KIEU = 'chon_nhieu'  # cho template biết: vẽ nhóm nút chọn nhiều
    dap_an = forms.MultipleChoiceField(  # ô chọn nhiều
        label='Bạn thích phong cách nào?',  # câu hỏi
        required=False,  # không bắt buộc: khách được bỏ qua (E1: câu 5 không bắt buộc)
        widget=forms.CheckboxSelectMultiple,  # nhiều hộp tích
        choices=(),  # danh sách điền ở __init__
        help_text=f'Chọn tối đa {TOI_DA_PHONG_CACH} phong cách, hoặc bỏ qua nếu chưa rõ.',  # lấy số từ hằng của Khoa, không gõ cứng
        error_messages={'invalid_choice': 'Phong cách không hợp lệ.'},  # báo khi gửi giá trị lạ
    )

    def __init__(self, *args, **kwargs):  # chạy mỗi lần tạo form
        super().__init__(*args, **kwargs)  # để Django dựng form như thường
        self.fields['dap_an'].choices = list(PhongCach.objects.order_by('TenPhongCach').values_list('pk', 'TenPhongCach'))  # đọc danh mục lúc mở trang

    def clean_dap_an(self):  # giới hạn số phong cách được chọn
        ma = self.cleaned_data['dap_an']  # danh sách mã (dạng chuỗi) khách đã tích
        if len(ma) > TOI_DA_PHONG_CACH:  # tích quá nhiều
            raise ValidationError(f'Chỉ được chọn tối đa {TOI_DA_PHONG_CACH} phong cách.')  # báo lỗi
        return ma  # hợp lệ thì trả lại


CAC_FORM = (BuocLoaiHinhForm, BuocKhuVucForm, BuocNganSachForm, BuocNgayForm, BuocPhongCachForm)  # form của bước 1 đến 5, đúng thứ tự CAC_CAU


# ---------------------------------------------------------------------
# Đọc và ghi session
# ---------------------------------------------------------------------
def _doc_tra_loi(session):  # lấy câu trả lời đang lưu (luôn trả dict, kể cả khi chưa có hoặc dữ liệu hỏng)
    tra_loi = session.get(KHOA_SESSION)  # giá trị thô trong session
    return dict(tra_loi) if isinstance(tra_loi, dict) else {}  # sao chép ra dict mới để sửa thoải mái, không đụng session


def _buoc_dau_thieu(tra_loi):  # số thứ tự (từ 1) của câu đầu tiên chưa trả lời; None nếu đã đủ 5 câu
    for so, khoa in enumerate(CAC_CAU, start=1):  # duyệt 5 câu theo thứ tự
        if khoa not in tra_loi:  # câu này chưa có đáp án
            return so  # báo bước này
    return None  # đủ cả 5 câu


def _doc_buoc(chuoi):  # đổi ?buoc=... thành số 1 đến 5; sai thì về bước 1
    try:  # người dùng có thể sửa URL thành chữ bất kỳ
        buoc = int(chuoi)  # đổi sang số nguyên
    except (TypeError, ValueError):  # None hoặc không phải số
        return 1  # về bước đầu
    return min(max(buoc, 1), TONG_BUOC)  # kẹp trong khoảng 1 đến 5


def _url_buoc(buoc):  # địa chỉ của một bước
    return f"{reverse('assistant')}?buoc={buoc}"  # ví dụ /tro-ly/?buoc=3


def _gia_tri_luu(buoc, du_lieu):  # đổi dữ liệu form (đã kiểm tra) thành kiểu lưu được vào session (JSON)
    if buoc == 3:  # ngân sách
        return '' if du_lieu == GIA_TRI_KHONG_GIOI_HAN else du_lieu  # "Không giới hạn" lưu chuỗi rỗng; còn lại lưu chuỗi số
    if buoc == 4:  # ngày chụp
        return du_lieu.isoformat()  # date -> 'YYYY-MM-DD' (session không lưu được kiểu date)
    if buoc == 5:  # phong cách
        return [int(ma) for ma in du_lieu]  # danh sách chuỗi -> danh sách số
    return int(du_lieu)  # loại hình và khu vực: mã dạng số


def _gia_tri_ban_dau(buoc, gia_tri):  # đổi giá trị trong session ngược lại thành giá trị điền sẵn cho form (khi khách quay lại sửa)
    if buoc == 3:  # ngân sách
        return GIA_TRI_KHONG_GIOI_HAN if gia_tri == '' else gia_tri  # chuỗi rỗng ứng với mức "Không giới hạn"
    if buoc == 4:  # ngày chụp
        try:  # chuỗi trong session có thể hỏng
            return date.fromisoformat(gia_tri)  # 'YYYY-MM-DD' -> date
        except (TypeError, ValueError):  # hỏng thì để trống
            return None  # không điền sẵn
    return gia_tri  # các bước còn lại dùng nguyên giá trị


def _tra_loi_cho_goi_y(tra_loi):  # đổi dữ liệu session thành dict đúng hợp đồng của goi_y_nhiep_anh_gia; None nếu thiếu hoặc hỏng
    if any(khoa not in tra_loi for khoa in CAC_CAU):  # thiếu câu nào
        return None  # chưa đủ để gợi ý
    try:  # dữ liệu session có thể hỏng nên phải bọc lại
        return {  # đúng 5 khóa của hợp đồng E1, mục 2.4
            'loai_hinh': int(tra_loi['loai_hinh']),  # MaLoaiHinh (số nguyên)
            'khu_vuc': int(tra_loi['khu_vuc']),  # MaKhuVuc (số nguyên)
            'ngan_sach': Decimal(str(tra_loi['ngan_sach'])) if tra_loi['ngan_sach'] != '' else None,  # Decimal, hoặc None = không giới hạn
            'ngay_chup': date.fromisoformat(tra_loi['ngay_chup']),  # datetime.date (không phải datetime)
            'phong_cach': [int(ma) for ma in tra_loi['phong_cach']],  # danh sách mã, có thể rỗng
        }  # hết dict
    except (TypeError, ValueError, ArithmeticError):  # ArithmeticError bao gồm decimal.InvalidOperation khi chuỗi số hỏng
        return None  # coi như chưa trả lời, view sẽ đưa khách về hỏi lại


# ---------------------------------------------------------------------
# View 1: form 5 bước
# ---------------------------------------------------------------------
@khach_hang_required  # chưa đăng nhập -> trang đăng nhập; sai vai trò -> 403
@require_http_methods(['GET', 'POST'])  # chỉ nhận mở trang và gửi form
def assistant(request):  # name='assistant', URL /tro-ly/
    tra_loi = _doc_tra_loi(request.session)  # câu trả lời đã lưu
    buoc = _doc_buoc(request.GET.get('buoc'))  # bước đang mở (1 đến 5)
    dau_thieu = _buoc_dau_thieu(tra_loi)  # câu đầu tiên còn thiếu
    if dau_thieu is not None and buoc > dau_thieu:  # khách gõ URL nhảy cóc qua câu chưa trả lời
        return redirect(_url_buoc(dau_thieu))  # đưa về câu còn thiếu đầu tiên
    khoa = CAC_CAU[buoc - 1]  # khóa session của bước này
    lop_form = CAC_FORM[buoc - 1]  # form của bước này

    if request.method == 'POST':  # khách bấm Tiếp tục hoặc Xem gợi ý
        bo_qua_cau_5 = buoc == TONG_BUOC and 'bo_qua' in request.POST  # nút "Chưa rõ, bỏ qua" ở câu 5
        form = lop_form(request.POST)  # form chứa dữ liệu khách vừa gửi
        if bo_qua_cau_5 or form.is_valid():  # bỏ qua câu 5 thì không cần kiểm tra
            tra_loi[khoa] = [] if bo_qua_cau_5 else _gia_tri_luu(buoc, form.cleaned_data['dap_an'])  # bỏ qua = danh sách phong cách rỗng (E1)
            request.session[KHOA_SESSION] = tra_loi  # GÁN LẠI cả dict để Django biết session đã đổi
            if buoc == TONG_BUOC:  # vừa xong câu cuối
                return redirect('assistant_result')  # sang trang kết quả
            return redirect(_url_buoc(buoc + 1))  # sang câu kế tiếp
    else:  # mở trang bằng GET
        ban_dau = {'dap_an': _gia_tri_ban_dau(buoc, tra_loi[khoa])} if khoa in tra_loi else {}  # điền sẵn đáp án cũ nếu khách quay lại sửa
        form = lop_form(initial=ban_dau)  # form trống hoặc điền sẵn

    return render(request, 'search/tro_ly.html', {  # POST sai hoặc GET: hiện form
        'form': form,  # form của bước hiện tại
        'kieu': lop_form.KIEU,  # cách vẽ ô trả lời
        'buoc': buoc,  # số bước hiện tại
        'tong_buoc': TONG_BUOC,  # tổng số bước
        'cac_buoc': list(range(1, TONG_BUOC + 1)),  # [1..5] để vẽ thanh tiến độ
        'bo_cuc': getattr(lop_form, 'BO_CUC', 'luoi'),  # cách xếp đáp án (lưới hoặc danh sách)
        'ngay_nhanh': _ngay_nhanh() if lop_form.KIEU == 'ngay' else [],  # hàng ngày chọn nhanh (chỉ bước 4)
        'toi_da_phong_cach': TOI_DA_PHONG_CACH,  # số phong cách tối đa cho bộ đếm ở bước 5 (lấy từ hằng của Khoa)
        'la_buoc_cuoi': buoc == TONG_BUOC,  # bước cuối có nút "Chưa rõ, bỏ qua" và nút "Xem gợi ý"
        'url_hien_tai': _url_buoc(buoc),  # nơi form gửi tới (giữ ?buoc=...)
        'url_quay_lai': _url_buoc(buoc - 1) if buoc > 1 else '',  # nút Quay lại (bước 1 không có)
        'url_bo_qua': url_trang_chu(request.user),  # nút "Bỏ qua Trợ lý" về trang tổng quan
    })  # hết dict


# ---------------------------------------------------------------------
# View 2: trang kết quả
# ---------------------------------------------------------------------
def _url_anh(nag):  # địa chỉ ảnh đại diện; trả '' nếu chưa có ảnh (tránh lỗi khi lấy .url của ô trống)
    anh = nag.AnhDaiDien  # trường ảnh đại diện của Nhiếp ảnh gia
    try:  # lấy .url có thể báo lỗi nếu trường rỗng
        return anh.url if anh else ''  # có ảnh thì lấy địa chỉ, không thì chuỗi rỗng
    except (ValueError, AttributeError):  # trường rỗng hoặc không phải ImageField
        return ''  # không hiện ảnh


def _the_ket_qua(ket_qua):  # đổi một KetQuaGoiY thành dict đơn giản cho template
    nag = ket_qua.nhiep_anh_gia  # hồ sơ Nhiếp ảnh gia
    tai_khoan = nag.MaTaiKhoan  # tài khoản của họ (goi_y.py đã select_related nên không tốn thêm truy vấn)
    return {  # dữ liệu một thẻ
        'ma': nag.pk,  # mã Nhiếp ảnh gia (gửi kèm khi bấm chọn giờ)
        'ten': tai_khoan.get_full_name() or tai_khoan.username,  # tên hiển thị
        'anh': _url_anh(nag),  # ảnh đại diện
        'url_ho_so': reverse('photographer_detail', args=[nag.pk]),  # trang hồ sơ công khai (tên URL lấy từ profiles/urls_cong_khai.py)
        'diem': ket_qua.diem,  # số nguyên 0-100, hiện "Phù hợp x%"
        'ly_do': [ly for ly in ket_qua.ly_do if ly != CHIP_CHUA_CO_DANH_GIA],  # bỏ chip "Chưa có đánh giá" vì thẻ có dòng riêng (chip có thể bị cắt do giới hạn 3 chip)
        'khung_gio': ket_qua.khung_gio,  # các khung giờ trống hợp lệ, đã xếp theo giờ
        'gia_tu': dinh_dang_tien(ket_qua.gia_tu),  # giá gói rẻ nhất dạng chữ, ví dụ 2.000.000đ
        'diem_tb': ket_qua.diem_tb,  # float thô hoặc None; template phải dùng floatformat:1
        'so_danh_gia': ket_qua.so_danh_gia,  # số lượt đánh giá
    }  # hết dict


NUT_GOI_Y = (  # (từ khóa trong câu gợi ý của Khoa, bước cần sửa, chữ trên nút), xét theo thứ tự
    ('ngày', 4, 'Đổi ngày chụp'),  # "Thử chọn ngày khác" -> bước 4
    ('ngân sách', 3, 'Đổi ngân sách'),  # "Thử nâng ngân sách..." -> bước 3
    ('khu vực', 2, 'Đổi khu vực'),  # "Thử chọn khu vực khác" -> bước 2
    ('loại hình', 1, 'Đổi loại hình'),  # "Thử chọn loại hình khác" -> bước 1
)


def _nut_goi_y(cau):  # ghép một câu gợi ý với nút dẫn tới đúng bước cần sửa; không khớp thì chỉ hiện chữ
    cau_thuong = cau.lower()  # so khớp không phân biệt hoa thường
    for tu_khoa, buoc, nhan in NUT_GOI_Y:  # duyệt từng quy tắc
        if tu_khoa in cau_thuong:  # câu có nhắc tới tiêu chí này
            return {'cau': cau, 'url': _url_buoc(buoc), 'nhan': nhan}  # có nút
    return {'cau': cau, 'url': '', 'nhan': ''}  # không có nút


def _tom_tat(c):  # các dòng "câu hỏi: đáp án" hiện đầu trang kết quả; c là CauTraLoi do kiem_tra_cau_tra_loi trả về
    if c.ngan_sach is None:  # khách chọn không giới hạn
        ngan_sach = 'Không giới hạn'  # chữ hiện
    else:  # có đặt ngân sách
        ngan_sach = NHAN_NGAN_SACH.get(c.ngan_sach) or dinh_dang_tien(c.ngan_sach)  # chữ của mức, không có thì hiện số tiền
    return [  # danh sách (nhãn, giá trị)
        ('Loại hình', c.loai_hinh.TenLoaiHinh),  # câu 1
        ('Khu vực', c.khu_vuc.TenKhuVuc),  # câu 2
        ('Ngân sách', ngan_sach),  # câu 3
        ('Ngày chụp', c.ngay_chup.strftime('%d/%m/%Y')),  # câu 4
        ('Phong cách', ', '.join(p.TenPhongCach for p in c.phong_cach) or 'Chưa rõ'),  # câu 5; rỗng = chưa rõ
    ]  # hết danh sách


@khach_hang_required  # chỉ Khách hàng đã đăng nhập
@require_GET  # trang kết quả chỉ để xem; việc chọn giờ gửi tới chon_slot
def assistant_result(request):  # name='assistant_result', URL /tro-ly/ket-qua/
    tra_loi = _doc_tra_loi(request.session)  # câu trả lời đã lưu
    cau_tra_loi = _tra_loi_cho_goi_y(tra_loi)  # đổi sang đúng kiểu hàm của Khoa
    if cau_tra_loi is None:  # chưa trả lời đủ 5 câu hoặc dữ liệu hỏng
        return redirect(_url_buoc(_buoc_dau_thieu(tra_loi) or 1))  # đưa về câu còn thiếu (hỏng thì về câu 1)
    if not _ngay_hop_le(cau_tra_loi['ngay_chup']):  # ngày đã lưu hôm qua nay thành quá khứ, hoặc đã xa hơn 30 ngày
        messages.warning(request, 'Ngày chụp bạn đã chọn không còn hợp lệ. Vui lòng chọn lại ngày.')  # giải thích vì sao bị hỏi lại
        return redirect(_url_buoc(4))  # về đúng câu hỏi ngày
    try:  # hàm của Khoa ném ValidationError khi đầu vào sai (ghi chú E3)
        c = kiem_tra_cau_tra_loi(cau_tra_loi)  # CauTraLoi có sẵn tên loại hình, khu vực... để hiện tóm tắt
        ket_qua = goi_y_nhiep_anh_gia(cau_tra_loi)  # tối đa 5 kết quả, đã xếp hạng; rỗng = không có ai
        cau_noi_tieu_chi = [] if ket_qua else goi_y_noi_tieu_chi(cau_tra_loi)  # chỉ hỏi gợi ý nới tiêu chí khi kết quả rỗng
    except ValidationError as loi:  # ví dụ loại hình vừa bị xóa khỏi danh mục
        for thong_bao in loi.messages:  # mỗi lỗi một thông báo
            messages.error(request, thong_bao)  # hiện hộp đỏ ở đầu trang kế tiếp
        return redirect(_url_buoc(1))  # hỏi lại từ đầu
    return render(request, 'search/tro_ly_ket_qua.html', {  # hiện trang kết quả
        'cac_the': [_the_ket_qua(k) for k in ket_qua],  # các thẻ Nhiếp ảnh gia
        'cau_noi_tieu_chi': [_nut_goi_y(cau) for cau in cau_noi_tieu_chi],  # các câu gợi ý khi rỗng, mỗi câu kèm nút
        'tom_tat': _tom_tat(c),  # tóm tắt 5 đáp án
        'ngay_chup': c.ngay_chup,  # ngày chụp, hiện ở dòng "Khung giờ trống ngày ..."
        'url_sua': _url_buoc(1),  # nút "Sửa câu trả lời"
        'url_tim_kiem': reverse('search'),  # nút "Tự tìm kiếm" (name='search' có sẵn)
    })  # hết dict
