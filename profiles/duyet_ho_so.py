# =====================================================================
# profiles/duyet_ho_so.py  -  K7: Duyệt hồ sơ Nhiếp ảnh gia (UC1.5, Khoa)
#
# Gồm: form Quản trị viên nhập quyết định + hàm xử lý xu_ly_duyet_ho_so().
# Ba quyết định (đúng đặc tả UC1.5):
#   phe_duyet          -> lượt duyệt 'Đã duyệt'      -> User.trang_thai_ho_so = 'Đã duyệt' (hiển thị công khai); thông báo web + Email
#   yeu_cau_chinh_sua  -> lượt duyệt 'Yêu cầu chỉnh sửa' (bắt buộc nhập nội dung) -> hồ sơ GIỮ 'Chờ duyệt'; thông báo web
#   tu_choi            -> lượt duyệt 'Đã từ chối'    (bắt buộc nhập lý do)         -> User.trang_thai_ho_so = 'Đã từ chối'; thông báo web
# DuyetHoSo.save() (K1) tự đồng bộ User.trang_thai_ho_so trong cùng giao dịch, nên ở đây chỉ cần gán kết quả rồi save().
# =====================================================================
import logging

from django import forms
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.permissions import lay_vai_tro
from bookings.services import gui_email_sau_commit      # Email gửi SAU commit + ghi TrangThaiGuiEmail (của Tuyền)
from core.constants import KetQuaDuyetHoSo, TrangThaiHoSo, VaiTro
from notifications.services import gui_thong_bao
from profiles.models import DuyetHoSo

logger = logging.getLogger(__name__)

PHE_DUYET = 'phe_duyet'
YEU_CAU_CHINH_SUA = 'yeu_cau_chinh_sua'
TU_CHOI = 'tu_choi'

# Giá trị gửi lên từ form -> kết quả lưu trong DUYETHOSO.KetQua. Chỉ nhận đúng 3 khóa này, giá trị lạ bị từ chối.
KET_QUA_THEO_HANH_DONG = {
    PHE_DUYET: KetQuaDuyetHoSo.DA_DUYET,
    YEU_CAU_CHINH_SUA: KetQuaDuyetHoSo.YEU_CAU_CHINH_SUA,
    TU_CHOI: KetQuaDuyetHoSo.DA_TU_CHOI,
}
CAN_NOI_DUNG = (YEU_CAU_CHINH_SUA, TU_CHOI)      # hai quyết định bắt buộc nhập nội dung gửi Nhiếp ảnh gia
DO_DAI_NOI_DUNG_TOI_DA = 1000                    # NoiDungPhanHoi là VARCHAR(1000)


class DuyetHoSoLoi(Exception):
    """Lỗi nghiệp vụ có câu báo tiếng Việt sẵn để hiện cho Quản trị viên."""

    def __init__(self, thong_bao):
        super().__init__(thong_bao)
        self.thong_bao = thong_bao


class QuyetDinhDuyetForm(forms.Form):
    """Quyết định của Quản trị viên. Chọn một thao tác rồi bấm 'Xác nhận' (đây là bước xác nhận của UC1.5)."""

    hanh_dong = forms.ChoiceField(
        label='Quyết định',
        choices=[(PHE_DUYET, 'Phê duyệt'), (YEU_CAU_CHINH_SUA, 'Yêu cầu chỉnh sửa'), (TU_CHOI, 'Từ chối')],
        widget=forms.RadioSelect,
        error_messages={'required': 'Vui lòng chọn một quyết định.',
                        'invalid_choice': 'Quyết định không hợp lệ. Vui lòng chọn lại.'})
    noi_dung = forms.CharField(
        label='Nội dung gửi Nhiếp ảnh gia', required=False, max_length=DO_DAI_NOI_DUNG_TOI_DA,
        widget=forms.Textarea(attrs={'rows': 4, 'maxlength': DO_DAI_NOI_DUNG_TOI_DA}),
        help_text='Bắt buộc khi chọn "Yêu cầu chỉnh sửa" (ghi rõ cần sửa gì) hoặc "Từ chối" (ghi lý do). '
                  'Tối đa 1000 ký tự.',
        error_messages={'max_length': 'Nội dung tối đa 1000 ký tự.'})

    def clean(self):
        du_lieu = super().clean()
        hanh_dong = du_lieu.get('hanh_dong')
        # CharField tự cắt dấu cách hai đầu nên "chỉ toàn dấu cách" cũng thành rỗng và bị chặn ở đây.
        if hanh_dong in CAN_NOI_DUNG and not du_lieu.get('noi_dung'):
            cau = 'cần chỉnh sửa' if hanh_dong == YEU_CAU_CHINH_SUA else 'lý do từ chối'
            self.add_error('noi_dung', f'Vui lòng nhập nội dung {cau} để gửi cho Nhiếp ảnh gia.')
        return du_lieu


class BoLocDuyetForm(forms.Form):
    """Tìm kiếm và bộ lọc của danh sách (GET). Mỗi nhóm lọc chọn được nhiều mục (như trang Tìm kiếm Nhiếp ảnh gia):
    trong một nhóm là 'hoặc', giữa các nhóm là 'và'. Giá trị sai/lạ trên URL bị bỏ qua chứ không gây lỗi trang."""

    q = forms.CharField(label='Từ khóa (tên hoặc email Nhiếp ảnh gia)', required=False, max_length=100,
                        widget=forms.TextInput(attrs={'placeholder': 'Tìm theo tên hoặc email Nhiếp ảnh gia',
                                                      'autocomplete': 'off', 'type': 'search'}))
    tu_ngay = forms.DateField(label='Nộp từ ngày', required=False,
                              widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
                              error_messages={'invalid': 'Ngày bắt đầu không hợp lệ.'})
    den_ngay = forms.DateField(label='Nộp đến ngày', required=False,
                               widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
                               error_messages={'invalid': 'Ngày kết thúc không hợp lệ.'})
    trang_thai = forms.MultipleChoiceField(label='Trạng thái hồ sơ', required=False, widget=forms.CheckboxSelectMultiple,
                                           choices=TrangThaiHoSo.CHOICES)
    lan_nop = forms.MultipleChoiceField(label='Lần nộp', required=False, widget=forms.CheckboxSelectMultiple,
                                        choices=[('dau', 'Nộp lần đầu'), ('nop_lai', 'Nộp lại')])
    ket_qua = forms.MultipleChoiceField(label='Kết quả xử lý', required=False, widget=forms.CheckboxSelectMultiple,
                                        choices=KetQuaDuyetHoSo.CHOICES)
    sap_xep = forms.ChoiceField(label='Sắp xếp', required=False, choices=[('cu', 'Cũ nhất trước'), ('moi', 'Mới nhất trước')])

    def clean(self):
        du_lieu = super().clean()
        tu, den = du_lieu.get('tu_ngay'), du_lieu.get('den_ngay')
        if tu and den and tu > den:
            self.add_error('den_ngay', 'Ngày kết thúc phải sau hoặc cùng ngày bắt đầu.')   # den_ngay bị bỏ, chỉ lọc từ ngày bắt đầu
        return du_lieu


def so_bo_loc_dang_dung(du_lieu, da_xu_ly):
    """Số nhóm/mục lọc đang chọn (hiện trên nút 'Bộ lọc'): mỗi mục tích chọn tính 1, khoảng ngày tính 1.
    Nhóm 'Kết quả xử lý' chỉ có ở tab Đã xử lý nên chỉ đếm ở đó."""
    nhom = ['trang_thai', 'lan_nop'] + (['ket_qua'] if da_xu_ly else [])
    so = sum(len(du_lieu.get(k) or []) for k in nhom)
    return so + (1 if (du_lieu.get('tu_ngay') or du_lieu.get('den_ngay')) else 0)


def loc_luot_duyet(queryset, du_lieu, da_xu_ly):
    """Áp dụng tìm kiếm + bộ lọc (du_lieu = cleaned_data) lên queryset DuyetHoSo; trả về queryset đã lọc và sắp xếp.
    da_xu_ly=True: tab 'Đã xử lý' (có lọc theo kết quả, sắp theo thời điểm duyệt); False: tab 'Chờ xử lý' (theo thời điểm nộp).
    Tìm kiếm: mỗi từ khóa (cách nhau bởi dấu cách) phải khớp họ, tên, email hoặc tên đăng nhập, nên 'Lê Khôi' cũng tìm được.
    Lọc ngày theo ThoiDiemNop, tính theo múi giờ của dự án (cả ngày bắt đầu và ngày kết thúc đều được tính)."""
    tk = 'MaNhiepAnhGia__MaTaiKhoan__'
    for tu in (du_lieu.get('q') or '').split():
        queryset = queryset.filter(
            Q(**{tk + 'first_name__icontains': tu}) | Q(**{tk + 'last_name__icontains': tu})
            | Q(**{tk + 'email__icontains': tu}) | Q(**{tk + 'username__icontains': tu}))
    if du_lieu.get('tu_ngay'):
        queryset = queryset.filter(ThoiDiemNop__date__gte=du_lieu['tu_ngay'])
    if du_lieu.get('den_ngay'):
        queryset = queryset.filter(ThoiDiemNop__date__lte=du_lieu['den_ngay'])
    if du_lieu.get('trang_thai'):
        queryset = queryset.filter(**{tk + 'trang_thai_ho_so__in': du_lieu['trang_thai']})
    lan_nop = set(du_lieu.get('lan_nop') or [])
    if lan_nop == {'dau'}:                       # chọn cả hai = không lọc
        queryset = queryset.filter(LanNop=1)
    elif lan_nop == {'nop_lai'}:
        queryset = queryset.filter(LanNop__gt=1)
    if da_xu_ly and du_lieu.get('ket_qua'):
        queryset = queryset.filter(KetQua__in=du_lieu['ket_qua'])
    moi_truoc = (du_lieu.get('sap_xep') or ('moi' if da_xu_ly else 'cu')) == 'moi'
    cot = 'ThoiDiemDuyet' if da_xu_ly else 'ThoiDiemNop'
    return queryset.order_by(f'-{cot}', '-pk') if moi_truoc else queryset.order_by(cot, 'pk')


def _noi_dung_thong_bao(hanh_dong, noi_dung):
    """(tiêu đề, nội dung) gửi cho Nhiếp ảnh gia theo quyết định."""
    if hanh_dong == PHE_DUYET:
        return ('Hồ sơ của bạn đã được duyệt',
                'Chúc mừng! Hồ sơ nhiếp ảnh gia của bạn đã được phê duyệt và hiển thị công khai. '
                'Bạn có thể quản lý Portfolio, gói dịch vụ, lịch khả dụng và nhận Booking từ Khách hàng.')
    if hanh_dong == YEU_CAU_CHINH_SUA:
        return ('Hồ sơ của bạn cần chỉnh sửa',
                f'Quản trị viên yêu cầu bạn chỉnh sửa hồ sơ: {noi_dung}\nVui lòng cập nhật và gửi lại hồ sơ.')
    return ('Hồ sơ của bạn chưa được phê duyệt', f'Lý do: {noi_dung}')


def xu_ly_duyet_ho_so(ma_duyet, quan_tri_vien, hanh_dong, noi_dung=''):
    """Ghi quyết định của Quản trị viên cho một lượt duyệt đang chờ. Trả về (luot_duyet, da_gui_thong_bao).

    Ném DuyetHoSoLoi khi: người gọi không phải Quản trị viên, không có lượt này, lượt đã được xử lý (ví dụ hai Quản trị
    viên cùng mở một hồ sơ: người bấm sau bị chặn, kết quả của người trước giữ nguyên), quyết định lạ, thiếu nội dung.
    Lỗi database (DatabaseError) KHÔNG bắt ở đây: view bắt và báo 'không thể cập nhật kết quả' (ngoại lệ 3c của UC1.5).
    da_gui_thong_bao=False nghĩa là kết quả ĐÃ lưu nhưng thông báo web không tạo được (ngoại lệ 3d); view cảnh báo."""
    if lay_vai_tro(quan_tri_vien) != VaiTro.QUAN_TRI_VIEN:
        raise DuyetHoSoLoi('Chỉ Quản trị viên mới được duyệt hồ sơ.')
    if hanh_dong not in KET_QUA_THEO_HANH_DONG:
        raise DuyetHoSoLoi('Quyết định không hợp lệ. Vui lòng chọn lại.')
    noi_dung = (noi_dung or '').strip()
    if hanh_dong in CAN_NOI_DUNG and not noi_dung:
        raise DuyetHoSoLoi('Vui lòng nhập nội dung gửi cho Nhiếp ảnh gia.')
    if len(noi_dung) > DO_DAI_NOI_DUNG_TOI_DA:
        raise DuyetHoSoLoi('Nội dung tối đa 1000 ký tự.')

    with transaction.atomic():
        # Khóa dòng (SQLite bỏ qua, MySQL/PostgreSQL có tác dụng) rồi đọc lại để chắc lượt này vẫn đang chờ.
        luot = (DuyetHoSo.objects.select_for_update().select_related('MaNhiepAnhGia__MaTaiKhoan')
                .filter(pk=ma_duyet).first())
        if luot is None:
            raise DuyetHoSoLoi('Không tìm thấy lượt duyệt hồ sơ này.')
        if luot.KetQua is not None:
            raise DuyetHoSoLoi(f'Hồ sơ này đã được xử lý ("{luot.KetQua}"). Vui lòng tải lại danh sách.')
        moi_nhat = (DuyetHoSo.objects.filter(MaNhiepAnhGia_id=luot.MaNhiepAnhGia_id)
                    .order_by('-LanNop').values_list('LanNop', flat=True).first())
        if luot.LanNop != moi_nhat:                     # lượt cũ: Nhiếp ảnh gia đã nộp lại, lượt mới mới là lượt cần xử lý
            raise DuyetHoSoLoi('Hồ sơ này đã được nộp lại. Vui lòng tải lại danh sách.')

        luot.MaQuanTriVien = quan_tri_vien
        luot.KetQua = KET_QUA_THEO_HANH_DONG[hanh_dong]
        luot.ThoiDiemDuyet = max(timezone.now(), luot.ThoiDiemNop)      # CHECK: thời điểm duyệt >= thời điểm nộp
        luot.NoiDungPhanHoi = noi_dung or None
        luot.save()             # đồng thời đổi User.trang_thai_ho_so (Đã duyệt / Đã từ chối / giữ Chờ duyệt)

        nag_user = luot.MaNhiepAnhGia.MaTaiKhoan
        tieu_de, noi_dung_tb = _noi_dung_thong_bao(hanh_dong, noi_dung)
        thong_bao = gui_thong_bao(nag_user, tieu_de, noi_dung_tb)
        if thong_bao is None:
            logger.warning('duyet_ho_so: không tạo được thông báo cho hồ sơ #%s', luot.MaNhiepAnhGia_id)
        gui_email_sau_commit(thong_bao, nag_user, tieu_de, noi_dung_tb)
    return luot, thong_bao is not None
