# search/views.py - K8: màn hình Tìm kiếm & lọc nhiếp ảnh gia (UC2.1 + UC2.2). Không cần đăng nhập.
from django.core.paginator import Paginator
from django.shortcuts import render
from django.urls import NoReverseMatch, reverse

from search.forms import TimKiemForm
from search.services import (SAP_XEP, SAP_XEP_MAC_DINH, SO_MOI_TRANG, dinh_dang_tien,
                             tim_kiem_nhiep_anh_gia)


def _duong_dan_ho_so(ma):
    # Trang hồ sơ công khai là K9 (name='photographer_detail'). Khi K9 chưa có thì thẻ dẫn thẳng tới trang chọn lịch
    # của nhiếp ảnh gia (UC4.1, name='lich_chon_slot'), để Khách vẫn bấm được và đặt lịch. Cả hai chưa có thì thẻ chưa bấm được.
    for ten in ('photographer_detail', 'lich_chon_slot'):
        try:
            return reverse(ten, args=[ma])
        except NoReverseMatch:
            continue
    return ''


def _the(nag):
    user = nag.MaTaiKhoan
    loai = [m.TenLoaiHinh for m in nag.loai_hinh_chup.all()]
    vuc = [m.TenKhuVuc for m in nag.khu_vuc.all()]
    mo_ta = ', '.join(loai[:3]) + (f' +{len(loai) - 3}' if len(loai) > 3 else '')
    if vuc:
        mo_ta += ' · ' + ', '.join(vuc[:2]) + (f' +{len(vuc) - 2}' if len(vuc) > 2 else '')
    return {
        'ma': f'NAG-{nag.pk:04d}',
        'ten': user.get_full_name() or user.username,
        'anh': nag.AnhDaiDien.url if nag.AnhDaiDien else '',
        'mo_ta': mo_ta,
        'gia_tu': dinh_dang_tien(nag.gia_tu) if nag.gia_tu is not None else '',
        'diem': f'{nag.diem_tb:.1f}' if nag.diem_tb is not None else '',
        'so_danh_gia': nag.so_dg,
        'href': _duong_dan_ho_so(nag.pk),
    }


def tim_kiem(request):
    form = TimKiemForm(request.GET)          # luôn gắn dữ liệu từ URL; URL trống thì mọi ô rỗng và vẫn hợp lệ
    sap_xep = request.GET.get('sap_xep')
    ngu_canh = {'form': form, 'loi': [], 'trang': None, 'cac_the': [], 'tong': 0,
                'co_tu_khoa': False, 'so_bo_loc': 0,
                'cach_sap_xep': [(khoa, nhan) for khoa, (nhan, _) in SAP_XEP.items()],
                'sap_xep_chon': sap_xep if sap_xep in SAP_XEP else SAP_XEP_MAC_DINH}
    if not form.is_valid():                  # 4a: thông tin tìm kiếm / tiêu chí lọc không hợp lệ
        ngu_canh['loi'] = [str(e) for loi_o in form.errors.values() for e in loi_o]
        return render(request, 'search/tim_kiem.html', ngu_canh)

    ket_qua = tim_kiem_nhiep_anh_gia(form.cleaned_data)
    trang = Paginator(ket_qua, SO_MOI_TRANG).get_page(request.GET.get('page'))   # page sai -> về trang hợp lệ
    ngu_canh.update(
        trang=trang, cac_the=[_the(n) for n in trang.object_list], tong=trang.paginator.count,
        co_tu_khoa=bool(form.cleaned_data['q']), so_bo_loc=form.so_bo_loc())
    return render(request, 'search/tim_kiem.html', ngu_canh)
