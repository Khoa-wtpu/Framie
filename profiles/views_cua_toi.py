# profiles/views_cua_toi.py - K3b: "Hồ sơ của tôi & trạng thái duyệt" (SC1.2, Khoa). Chỉ Nhiếp ảnh gia.
# Trang này chỉ XEM và dẫn sang trang cập nhật của K4 (name='cap_nhat_ho_so'). Sau khi gửi lại ở K4 sẽ quay về đây.
# Trạng thái hiển thị lấy từ LƯỢT DUYỆT MỚI NHẤT (không chỉ User.trang_thai_ho_so), vì hồ sơ bị "Yêu cầu chỉnh sửa"
# vẫn là 'Chờ duyệt' ở User nhưng đã được sửa và nộp lại (giống ho_so_dang_cho_duyet của K4).
from django.shortcuts import render
from django.utils import timezone

from accounts.permissions import vai_tro_required
from core.constants import KetQuaDuyetHoSo, TrangThaiHoSo, VaiTro
from profiles.models import DuyetHoSo, NhiepAnhGia

# Bốn trạng thái của màn SC1.2
CHO_DUYET = 'cho_duyet'                 # lượt mới nhất chưa có kết quả
CAN_CHINH_SUA = 'can_chinh_sua'         # Quản trị viên yêu cầu chỉnh sửa (hồ sơ vẫn 'Chờ duyệt')
DA_TU_CHOI = 'da_tu_choi'
DA_DUYET = 'da_duyet'


def xac_dinh_trang_thai(luot_moi_nhat):
    """Trả về một trong 4 hằng số trên theo lượt duyệt mới nhất (None = chưa có lượt nào -> coi như đang chờ)."""
    if luot_moi_nhat is None or luot_moi_nhat.KetQua is None:
        return CHO_DUYET
    if luot_moi_nhat.KetQua == KetQuaDuyetHoSo.YEU_CAU_CHINH_SUA:
        return CAN_CHINH_SUA
    if luot_moi_nhat.KetQua == KetQuaDuyetHoSo.DA_TU_CHOI:
        return DA_TU_CHOI
    return DA_DUYET


# Chữ hiển thị theo trạng thái: (câu mô tả dưới tiêu đề, nhãn nút, nút có dùng được không, câu trong khung Thao tác)
NOI_DUNG = {
    CHO_DUYET: ('Hồ sơ đang được Quản trị viên xem xét. Bạn chỉ có thể theo dõi trạng thái hồ sơ cho đến khi được duyệt.',
                'Cập nhật hồ sơ', False,
                'Hồ sơ đang chờ Quản trị viên xử lý nên chưa thể chỉnh sửa. Bạn có thể cập nhật sau khi có kết quả.'),
    CAN_CHINH_SUA: ('Quản trị viên đã yêu cầu chỉnh sửa hồ sơ. Hồ sơ vẫn ở trạng thái "Chờ duyệt" cho đến khi bạn cập nhật và gửi lại.',
                    'Cập nhật hồ sơ', True, 'Chỉnh sửa hồ sơ và gửi lại để Quản trị viên xem xét.'),
    DA_TU_CHOI: ('Hồ sơ chưa được phê duyệt. Vui lòng xem lý do, chỉnh sửa và nộp lại hồ sơ.',
                 'Chỉnh sửa & nộp lại hồ sơ', True, 'Chỉnh sửa hồ sơ và gửi lại để Quản trị viên xem xét.'),
    DA_DUYET: ('Hồ sơ đã được phê duyệt và hiển thị công khai trên FRAMIE.',
               'Cập nhật hồ sơ', True, 'Cập nhật hồ sơ sẽ đưa hồ sơ về "Chờ duyệt" để Quản trị viên xem xét lại.'),
}


def _noi(danh_sach, mac_dinh='Chưa chọn'):
    ten = [str(x) for x in danh_sach]
    return ', '.join(ten) if ten else mac_dinh


@vai_tro_required(VaiTro.NHIEP_ANH_GIA)        # chưa đăng nhập -> trang đăng nhập; vai trò khác -> 403
def ho_so_cua_toi(request):
    nag = (NhiepAnhGia.objects.select_related('MaTaiKhoan').filter(MaTaiKhoan=request.user).first())
    if nag is None:                             # chưa tạo hồ sơ (ví dụ tài khoản tạo thủ công): trang báo trống, không chuyển đi
        return render(request, 'profiles/ho_so_cua_toi.html', {'chua_co_ho_so': True})
    luot = DuyetHoSo.objects.filter(MaNhiepAnhGia=nag).order_by('-LanNop').first()
    trang_thai = xac_dinh_trang_thai(luot)
    mo_ta, nhan_nut, nut_dung_duoc, cau_thao_tac = NOI_DUNG[trang_thai]
    user = nag.MaTaiKhoan
    # Khung thông báo đầu trang (chỉ có khi có nội dung từ Quản trị viên hoặc khi đã duyệt)
    thong_bao = None
    if trang_thai == CHO_DUYET:
        thong_bao = ('info', 'Hồ sơ đang chờ duyệt', 'Các chức năng dành cho Nhiếp ảnh gia đã được duyệt tạm thời bị giới hạn.', None)
    elif trang_thai == CAN_CHINH_SUA:
        thong_bao = ('warning', 'Nội dung Quản trị viên yêu cầu chỉnh sửa', luot.NoiDungPhanHoi or '', luot.ThoiDiemDuyet)
    elif trang_thai == DA_TU_CHOI:
        thong_bao = ('danger', 'Lý do từ chối', luot.NoiDungPhanHoi or '', luot.ThoiDiemDuyet)
    else:
        thong_bao = ('success', 'Hồ sơ đã được duyệt', 'Bạn có thể sử dụng đầy đủ chức năng Nhiếp ảnh gia.', None)
    return render(request, 'profiles/ho_so_cua_toi.html', {
        'nag': nag, 'user_nag': user,
        'ten': user.get_full_name() or user.email,
        'ma': f'NAG-{nag.pk:04d}',
        'trang_thai_user': user.trang_thai_ho_so or TrangThaiHoSo.CHO_DUYET,
        'mo_ta': mo_ta, 'nhan_nut': nhan_nut, 'nut_dung_duoc': nut_dung_duoc, 'cau_thao_tac': cau_thao_tac,
        'thong_bao': thong_bao, 'trang_thai': trang_thai,
        'nut_dam': trang_thai in (CAN_CHINH_SUA, DA_TU_CHOI),        # theo wireframe: nút đặc khi cần hành động ngay
        'loai_hinh': _noi(nag.loai_hinh_chup.order_by('TenLoaiHinh')),
        'phong_cach': _noi(nag.phong_cach.order_by('TenPhongCach')),
        'khu_vuc': _noi(nag.khu_vuc.order_by('TenKhuVuc')),
    })
