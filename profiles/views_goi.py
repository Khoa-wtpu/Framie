# profiles/views_goi.py - K6: quản lý gói dịch vụ của nhiếp ảnh gia (UC1.4)
#   /goi-dich-vu/                       danh sách + lọc theo trạng thái   (name='service_packages', khớp menu)
#   /goi-dich-vu/them/                  thêm gói                          (name='goi_them')
#   /goi-dich-vu/<pk>/sua/              sửa gói                           (name='goi_sua')
#   /goi-dich-vu/<pk>/<hanh-dong>/      xác nhận rồi: ngung | ap-dung-lai | an | hien-lai | xoa   (name='goi_hanh_dong')
# Chỉ nhiếp ảnh gia có hồ sơ 'Đã duyệt' mới dùng được; chỉ thấy và sửa gói CỦA MÌNH.
#
# Trạng thái gói:  Đang áp dụng <--> Ngừng áp dụng (Ngừng áp dụng / Áp dụng lại).
#                  Từ Đang áp dụng hoặc Ngừng áp dụng đều Ẩn được; Hiện lại thì gói về đúng trạng thái trước khi ẩn
#                  (lưu ở cột TrangThaiTruocKhiAn).  Chỉ gói "Đang áp dụng" khách mới chọn được khi đặt lịch.
# Danh sách "Tất cả" hiện cả gói Đã ẩn (chữ mờ); thứ tự: Đang áp dụng -> Đã ẩn -> Ngừng áp dụng (cuối cùng).
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from core.constants import LoaiHauKy, TrangThaiGoi
from profiles.decorators import nhiep_anh_gia_da_duyet
from profiles.forms_goi import GoiForm
from profiles.models import GoiDichVu
from search.services import bo_dau

TG = TrangThaiGoi

# Bộ lọc trạng thái ở danh sách.
LOC_TAT_CA = 'tat-ca'
BO_LOC = {
    LOC_TAT_CA: 'Tất cả',
    'dang-ap-dung': TG.DANG_AP_DUNG,
    'ngung-ap-dung': TG.NGUNG_AP_DUNG,
    'da-an': TG.DA_AN,
}
MAU_HUY_HIEU = {TG.DANG_AP_DUNG: 'green', TG.NGUNG_AP_DUNG: 'amber', TG.DA_AN: 'gray'}

# Hành động đổi trạng thái: tên trên đường dẫn -> (các trạng thái được phép, trạng thái mới, tên nút, nút xác nhận,
# câu hỏi, thông báo thành công). Câu hỏi/thông báo là hàm nhận tên gói.
HANH_DONG = {
    'ngung': (
        {TG.DANG_AP_DUNG}, TG.NGUNG_AP_DUNG, 'Ngừng áp dụng', 'Xác nhận ngừng áp dụng', 'danger',
        lambda goi: (f'Gói "{goi.TenGoi}" sẽ hiển thị mờ trên hồ sơ, Khách hàng không thể chọn khi đặt lịch '
                     'và được chuyển xuống cuối danh sách gói dịch vụ. Bạn có thể áp dụng lại bất cứ lúc nào.'),
        lambda goi: f'Đã ngừng áp dụng gói "{goi.TenGoi}".'),
    'ap-dung-lai': (
        {TG.NGUNG_AP_DUNG}, TG.DANG_AP_DUNG, 'Áp dụng lại', 'Xác nhận áp dụng lại', 'primary',
        lambda goi: f'Gói "{goi.TenGoi}" sẽ được áp dụng lại và Khách hàng có thể chọn khi đặt lịch.',
        lambda goi: f'Đã áp dụng lại gói "{goi.TenGoi}".'),
    'an': (
        {TG.DANG_AP_DUNG, TG.NGUNG_AP_DUNG}, TG.DA_AN, 'Ẩn', 'Xác nhận ẩn', 'danger',
        lambda goi: (f'Gói "{goi.TenGoi}" sẽ không hiển thị với Khách hàng nhưng vẫn nằm trong danh sách của bạn (chữ mờ). '
                     f'Khi hiện lại, gói sẽ về trạng thái "{goi.TrangThai}" như hiện tại.'),
        lambda goi: f'Đã ẩn gói "{goi.TenGoi}".'),
    'hien-lai': (
        {TG.DA_AN}, None, 'Hiện lại', 'Xác nhận hiện lại', 'primary',     # trạng thái mới = trạng thái trước khi ẩn
        lambda goi: f'Gói "{goi.TenGoi}" sẽ hiện lại ở trạng thái "{_trang_thai_sau_khi_hien(goi)}".',
        lambda goi: f'Đã hiện lại gói "{goi.TenGoi}" (trạng thái "{_trang_thai_sau_khi_hien(goi)}").'),
}
HANH_DONG_XOA = 'xoa'


def _tien(so):
    return f'{int(so):,}'.replace(',', '.') + 'đ'               # 1500000 -> 1.500.000đ


def _trang_thai_sau_khi_hien(goi):
    """Gói đã ẩn quay về trạng thái trước khi ẩn; không rõ (dữ liệu cũ) thì về Ngừng áp dụng cho an toàn."""
    return goi.TrangThaiTruocKhiAn if goi.TrangThaiTruocKhiAn in (TG.DANG_AP_DUNG, TG.NGUNG_AP_DUNG) else TG.NGUNG_AP_DUNG


def _an_goi(goi):
    """Chuyển gói sang Đã ẩn và nhớ trạng thái cũ để Hiện lại."""
    if goi.TrangThai != TG.DA_AN:
        goi.TrangThaiTruocKhiAn = goi.TrangThai
        goi.TrangThai = TG.DA_AN
        goi.save(update_fields=['TrangThai', 'TrangThaiTruocKhiAn'])


# Thứ tự trong danh sách: Đang áp dụng, rồi Đã ẩn, Ngừng áp dụng nằm cuối cùng.
THU_TU_TRANG_THAI = {TG.DANG_AP_DUNG: 0, TG.DA_AN: 1, TG.NGUNG_AP_DUNG: 2}


def _cau_hoi_xoa(ten, da_co_booking):
    cau_hoi = f'Bạn có chắc muốn xóa gói "{ten}"? Thao tác này không thể hoàn tác.'
    if da_co_booking:
        cau_hoi += (f' Gói này đã có Booking nên sẽ không bị xóa hẳn mà chuyển sang "{TG.DA_AN}" '
                    'để giữ lịch sử đặt lịch.')
    return cau_hoi


def _ve_danh_sach():
    return redirect('service_packages')


@nhiep_anh_gia_da_duyet
def danh_sach_goi(request, nag):
    loc = request.GET.get('trang_thai', LOC_TAT_CA)
    if loc not in BO_LOC:
        loc = LOC_TAT_CA                                    # giá trị lạ trên URL thì dùng mặc định
    tu_khoa = ' '.join(request.GET.get('q', '').split())[:100]
    cac_goi = GoiDichVu.objects.filter(MaNhiepAnhGia=nag).select_related('MaLoaiHinh').order_by('pk')
    if loc != LOC_TAT_CA:
        cac_goi = cac_goi.filter(TrangThai=BO_LOC[loc])
    cac_goi = sorted(cac_goi, key=lambda g: (THU_TU_TRANG_THAI.get(g.TrangThai, 1), g.pk))
    if tu_khoa:                                             # tìm không phân biệt hoa/thường và dấu, theo tên gói hoặc loại hình
        khoa = bo_dau(tu_khoa).casefold()
        cac_goi = [g for g in cac_goi if khoa in bo_dau(f'{g.TenGoi} {g.MaLoaiHinh.TenLoaiHinh}').casefold()]
    co_booking = set(GoiDichVu.objects.filter(pk__in=[g.pk for g in cac_goi], booking__isnull=False)
                     .values_list('pk', flat=True))
    for goi in cac_goi:
        goi.mau = MAU_HUY_HIEU.get(goi.TrangThai, 'gray')
        goi.gia_hien_thi = _tien(goi.Gia)
        goi.hau_ky_hien_thi = (f'Giới hạn {goi.SoAnhHauKyToiDa} ảnh'
                               if goi.LoaiHauKy == LoaiHauKy.GIOI_HAN else goi.LoaiHauKy)
        # Các nút đổi trạng thái theo trạng thái gói; thông tin cho hộp xác nhận (popup) nằm sẵn trong từng nút.
        goi.cac_nut = [{'ma': ma, 'ten': ten, 'tieu_de': ten, 'cau_hoi': hoi(goi),
                        'nut': nut, 'kieu': kieu}
                       for ma, (cho_phep, _moi, ten, nut, kieu, hoi, _ok) in HANH_DONG.items()
                       if goi.TrangThai in cho_phep]
        goi.nut_xoa = {'ma': HANH_DONG_XOA, 'ten': 'Xóa', 'tieu_de': 'Xóa gói dịch vụ',
                       'cau_hoi': _cau_hoi_xoa(goi.TenGoi, goi.pk in co_booking),
                       'nut': 'Xác nhận xóa', 'kieu': 'danger'}
    return render(request, 'profiles/goi_danh_sach.html', {
        'cac_goi': cac_goi, 'loc': loc, 'q': tu_khoa, 'cac_loc': list(BO_LOC.items()),
        'dang_loc': bool(tu_khoa) or loc != LOC_TAT_CA})


@nhiep_anh_gia_da_duyet
def goi_them(request, nag):
    form = GoiForm(request.POST if request.method == 'POST' else None, nag=nag)
    if request.method == 'POST' and form.is_valid():
        goi = form.save()
        messages.success(request, f'Đã thêm gói "{goi.TenGoi}".')
        return _ve_danh_sach()
    return render(request, 'profiles/goi_form.html', {'form': form, 'goi': None,
                                                       'loai_gioi_han': LoaiHauKy.GIOI_HAN})


@nhiep_anh_gia_da_duyet
def goi_sua(request, nag, pk):
    goi = get_object_or_404(GoiDichVu, pk=pk, MaNhiepAnhGia=nag)      # gói của người khác -> 404
    form = GoiForm(request.POST if request.method == 'POST' else None, nag=nag, instance=goi)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Đã lưu gói "{goi.TenGoi}".')
        return _ve_danh_sach()
    return render(request, 'profiles/goi_form.html', {'form': form, 'goi': goi,
                                                       'loai_gioi_han': LoaiHauKy.GIOI_HAN})


@nhiep_anh_gia_da_duyet
def goi_hanh_dong(request, nag, pk, hanh_dong):
    if hanh_dong != HANH_DONG_XOA and hanh_dong not in HANH_DONG:
        raise Http404
    goi = get_object_or_404(GoiDichVu, pk=pk, MaNhiepAnhGia=nag)
    ten = goi.TenGoi

    if hanh_dong == HANH_DONG_XOA:
        da_co_booking = goi.booking.exists()                # Booking giữ khóa ngoại tới gói (PROTECT)
        if request.method == 'POST':
            if da_co_booking:                               # có lịch sử đặt lịch thì không xóa hẳn được: chuyển sang Đã ẩn
                _an_goi(goi)
                messages.info(request, f'Gói "{ten}" đã có Booking nên không thể xóa hẳn, '
                                       f'hệ thống chuyển gói sang "{TG.DA_AN}" để giữ lịch sử.')
            else:
                goi.delete()
                messages.success(request, f'Đã xóa gói "{ten}".')
            return _ve_danh_sach()
        return render(request, 'profiles/goi_xac_nhan.html', {
            'goi': goi, 'tieu_de': 'Xóa gói dịch vụ', 'cau_hoi': _cau_hoi_xoa(ten, da_co_booking),
            'nut': 'Xác nhận xóa', 'kieu_nut': 'danger'})

    cho_phep, moi, tieu_de, nut, kieu, cau_hoi, thanh_cong = HANH_DONG[hanh_dong]
    if goi.TrangThai not in cho_phep:                       # ví dụ gõ tay đường dẫn "an" cho gói đang áp dụng
        messages.error(request, f'Không thể thực hiện "{tieu_de}" với gói đang ở trạng thái "{goi.TrangThai}".')
        return _ve_danh_sach()
    if request.method == 'POST':
        thong_bao = thanh_cong(goi)                         # tạo trước khi đổi trạng thái (câu Hiện lại cần trạng thái cũ)
        if hanh_dong == 'an':
            _an_goi(goi)
        else:
            moi = _trang_thai_sau_khi_hien(goi) if hanh_dong == 'hien-lai' else moi
            goi.TrangThai = moi
            goi.TrangThaiTruocKhiAn = None
            goi.save(update_fields=['TrangThai', 'TrangThaiTruocKhiAn'])
        messages.success(request, thong_bao)
        return _ve_danh_sach()
    return render(request, 'profiles/goi_xac_nhan.html', {
        'goi': goi, 'tieu_de': tieu_de, 'cau_hoi': cau_hoi(goi), 'nut': nut, 'kieu_nut': kieu})
