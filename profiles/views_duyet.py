# profiles/views_duyet.py - K7: Duyệt hồ sơ Nhiếp ảnh gia (UC1.5, Khoa). Chỉ Quản trị viên.
import logging

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.shortcuts import get_object_or_404, redirect, render

from accounts.permissions import vai_tro_required
from core.constants import TrangThaiHoSo, VaiTro
from profiles.duyet_ho_so import BoLocDuyetForm, DuyetHoSoLoi, loc_luot_duyet, so_bo_loc_dang_dung, PHE_DUYET, QuyetDinhDuyetForm, TU_CHOI, xu_ly_duyet_ho_so
from profiles.models import DuyetHoSo

logger = logging.getLogger(__name__)

SO_MOI_TRANG = 10
TAB_CHO, TAB_DA_XU_LY = 'cho', 'da_xu_ly'


def _ten(nag):
    user = nag.MaTaiKhoan
    return user.get_full_name() or user.email


@vai_tro_required(VaiTro.QUAN_TRI_VIEN)
def danh_sach(request):
    """Màn 'Duyệt hồ sơ': tab 'Chờ xử lý' (lượt chưa có kết quả, cũ nhất lên đầu) và tab 'Đã xử lý'."""
    tab = request.GET.get('tab')
    if tab not in (TAB_CHO, TAB_DA_XU_LY):
        tab = TAB_CHO
    luot_duyet = DuyetHoSo.objects.select_related('MaNhiepAnhGia__MaTaiKhoan', 'MaQuanTriVien')
    so_cho = luot_duyet.filter(KetQua__isnull=True).count()              # số trên tab: tổng, không phụ thuộc bộ lọc
    so_da_xu_ly = luot_duyet.filter(KetQua__isnull=False).count()
    bo_loc = BoLocDuyetForm(request.GET)
    bo_loc.is_valid()                                                    # trường sai bị bỏ khỏi cleaned_data -> coi như không lọc
    du_lieu = bo_loc.cleaned_data
    da_xu_ly = tab == TAB_DA_XU_LY
    goc = luot_duyet.filter(KetQua__isnull=not da_xu_ly)
    ds = loc_luot_duyet(goc, du_lieu, da_xu_ly)
    sap_xep_chon = du_lieu.get('sap_xep') or ('moi' if da_xu_ly else 'cu')
    so_bo_loc = so_bo_loc_dang_dung(du_lieu, da_xu_ly)
    dang_loc = bool(so_bo_loc or du_lieu.get('q'))                       # có tìm kiếm hoặc bộ lọc (sắp xếp thì không tính)
    trang = Paginator(ds, SO_MOI_TRANG).get_page(request.GET.get('page'))       # page sai -> về trang hợp lệ
    return render(request, 'profiles/duyet_ho_so_danh_sach.html', {
        'tab': tab, 'page_obj': trang, 'cac_luot': trang.object_list, 'bo_loc': bo_loc, 'dang_loc': dang_loc, 'so_bo_loc': so_bo_loc, 'sap_xep_chon': sap_xep_chon,
        'so_ket_qua': trang.paginator.count,
        'so_cho': so_cho, 'so_da_xu_ly': so_da_xu_ly, 'trang_thai_cho': TrangThaiHoSo.CHO_DUYET,
        'TAB_CHO': TAB_CHO, 'TAB_DA_XU_LY': TAB_DA_XU_LY,
    })


@vai_tro_required(VaiTro.QUAN_TRI_VIEN)
def chi_tiet(request, ma_duyet):
    """Xem chi tiết một hồ sơ và (nếu lượt đang chờ) ghi quyết định: Phê duyệt / Yêu cầu chỉnh sửa / Từ chối."""
    luot = get_object_or_404(
        DuyetHoSo.objects.select_related('MaNhiepAnhGia__MaTaiKhoan', 'MaQuanTriVien'), pk=ma_duyet)
    nag = luot.MaNhiepAnhGia
    dang_cho = luot.KetQua is None
    form = None
    if dang_cho:
        form = QuyetDinhDuyetForm(request.POST or None)
        if request.method == 'POST' and form.is_valid():
            try:
                _, da_gui = xu_ly_duyet_ho_so(luot.pk, request.user, form.cleaned_data['hanh_dong'],
                                              form.cleaned_data['noi_dung'])
            except DuyetHoSoLoi as loi:                                   # đã có người xử lý trước, v.v.
                messages.error(request, loi.thong_bao)
                return redirect('admin_profile_review')
            except DatabaseError:                                         # ngoại lệ 3c: không cập nhật được kết quả
                logger.exception('duyet_ho_so: lỗi cập nhật lượt %s', luot.pk)
                form.add_error(None, 'Không thể cập nhật kết quả xử lý. Vui lòng thực hiện lại.')
            else:
                hanh_dong = form.cleaned_data['hanh_dong']
                if hanh_dong == PHE_DUYET:
                    messages.success(request, f'Đã phê duyệt hồ sơ của {_ten(nag)}. Hồ sơ đã hiển thị công khai.')
                elif hanh_dong == TU_CHOI:
                    messages.success(request, f'Đã từ chối hồ sơ của {_ten(nag)}.')
                else:
                    messages.success(request, f'Đã gửi yêu cầu chỉnh sửa đến {_ten(nag)}. Hồ sơ vẫn ở trạng thái "Chờ duyệt".')
                if not da_gui:                                            # ngoại lệ 3d: kết quả đã lưu, thông báo thì không
                    messages.warning(request, 'Đã lưu kết quả nhưng chưa gửi được thông báo đến Nhiếp ảnh gia. '
                                              'Nhiếp ảnh gia vẫn xem được nội dung ở trang cập nhật hồ sơ.')
                return redirect('admin_profile_review')
    elif request.method == 'POST':                                        # lượt đã xử lý: không nhận quyết định thứ hai
        messages.info(request, 'Hồ sơ này đã được xử lý.')
        return redirect('admin_profile_review')
    lich_su = (DuyetHoSo.objects.filter(MaNhiepAnhGia=nag, KetQua__isnull=False)
               .exclude(pk=luot.pk).select_related('MaQuanTriVien').order_by('-LanNop'))
    return render(request, 'profiles/duyet_ho_so_chi_tiet.html', {
        'luot': luot, 'nag': nag, 'ten': _ten(nag), 'dang_cho': dang_cho, 'form': form, 'lich_su': lich_su,
        'loai_hinh': nag.loai_hinh_chup.order_by('TenLoaiHinh'),
        'phong_cach': nag.phong_cach.order_by('TenPhongCach'),
        'khu_vuc': nag.khu_vuc.order_by('TenKhuVuc'),
        'trang_thai_cho': TrangThaiHoSo.CHO_DUYET,
    })
