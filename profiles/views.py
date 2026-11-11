# profiles/views.py - K3, K4 (Khoa)
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch, reverse

from accounts.permissions import vai_tro_required
from core.constants import KetQuaDuyetHoSo, VaiTro
from profiles.forms import CapNhatHoSoForm, NhiepAnhGiaForm, ho_so_dang_cho_duyet
from profiles.models import DuyetHoSo, NhiepAnhGia

# ---------------------------------------------------------------------
# K4 - Cập nhật hồ sơ cá nhân (UC1.2). Đây là trang THẬT, không phải trang thử.
# ---------------------------------------------------------------------
def _ve_ho_so_cua_toi():
    # Đích quay về = trang "Hồ sơ của tôi" khi trang đó có (name='photographer_profile' trong menu);
    # chưa có thì về trang tạm sau đăng nhập.
    try:
        return redirect(reverse('photographer_profile'))
    except NoReverseMatch:
        return redirect('trang_tam')


def _thong_bao_trang_thai(nag):
    # Khung thông báo đầu trang theo kết quả của lượt duyệt gần nhất: (mức độ, tiêu đề, nội dung).
    luot = (DuyetHoSo.objects.filter(MaNhiepAnhGia=nag, KetQua__isnull=False)
            .order_by('-LanNop').first())
    if luot is None:
        return None
    if luot.KetQua == KetQuaDuyetHoSo.YEU_CAU_CHINH_SUA:
        return ('warning', 'Quản trị viên yêu cầu chỉnh sửa hồ sơ', luot.NoiDungPhanHoi or '')
    if luot.KetQua == KetQuaDuyetHoSo.DA_TU_CHOI:
        return ('danger', 'Hồ sơ chưa được phê duyệt', luot.NoiDungPhanHoi or '')
    return ('info', 'Hồ sơ của bạn đang hiển thị công khai',
            'Sau khi gửi lại, hồ sơ chuyển về "Chờ duyệt" để Quản trị viên xem xét lại.')


@vai_tro_required(VaiTro.NHIEP_ANH_GIA)       # chỉ Nhiếp ảnh gia; sai vai trò -> 403
def cap_nhat_ho_so(request):
    nag = NhiepAnhGia.objects.select_related('MaTaiKhoan').filter(MaTaiKhoan=request.user).first()
    if nag is None:                           # tiền điều kiện UC1.2: hồ sơ đã được tạo
        messages.info(request, 'Bạn chưa có hồ sơ nên chưa thể cập nhật.')
        return _ve_ho_so_cua_toi()
    if ho_so_dang_cho_duyet(nag):             # đang chờ duyệt: chỉ được theo dõi
        messages.info(request, 'Hồ sơ đang chờ Quản trị viên duyệt. '
                               'Bạn có thể cập nhật sau khi có kết quả.')
        return _ve_ho_so_cua_toi()
    form = CapNhatHoSoForm(request.POST or None, request.FILES or None, instance=nag)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Đã gửi lại hồ sơ thành công. '
                                  'Hồ sơ chuyển sang trạng thái "Chờ duyệt" để Quản trị viên xem xét.')
        return _ve_ho_so_cua_toi()
    return render(request, 'profiles/cap_nhat_ho_so.html', {
        'form': form,
        'thong_bao_trang_thai': _thong_bao_trang_thai(nag),
        'huy_url': _ve_ho_so_cua_toi().url,
    })
