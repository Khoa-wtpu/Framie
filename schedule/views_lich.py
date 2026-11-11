# schedule/views_lich.py - K10: Quản lý lịch khả dụng (UC3.1). Tên URL 'my_calendar' khớp menu Nhiếp ảnh gia (core/navigation.py).
from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from core.constants import TrangThaiSlot
from profiles.decorators import nhiep_anh_gia_da_duyet      # đúng vai trò + hồ sơ "Đã duyệt"; truyền thêm tham số nag
from schedule import quan_ly
from schedule.forms import KhungGioForm
from schedule.quan_ly import CHE_DO_THANG, CHE_DO_TUAN, LichLoi, url_lich


@nhiep_anh_gia_da_duyet
@require_GET
def quan_ly_lich(request, nag):
    """UC3.1 bước 1-2: hiển thị lịch của Nhiếp ảnh gia theo tuần hoặc theo tháng."""
    quan_ly.nha_giu_cho_het_han()     # trạng thái hiển thị phải đúng thời điểm xem: lượt giữ quá hạn phải về "Lịch trống"
    che_do = request.GET.get('che_do')
    if che_do not in (CHE_DO_TUAN, CHE_DO_THANG):
        che_do = CHE_DO_TUAN
    ngay_neo = quan_ly.phan_tich_ngay(request.GET.get('ngay'))
    du_lieu = quan_ly.dung_tuan(nag, ngay_neo) if che_do == CHE_DO_TUAN else quan_ly.dung_thang(nag, ngay_neo)
    hom_nay = quan_ly.bay_gio().date()
    du_lieu.update({
        'che_do': che_do,
        'url_tuan': url_lich(CHE_DO_TUAN, ngay_neo),
        'url_thang': url_lich(CHE_DO_THANG, ngay_neo),
        'url_hom_nay': url_lich(che_do, hom_nay),
        'url_them': _url_them(ngay_neo, hom_nay),
        'chu_thich': [TrangThaiSlot.TRONG, TrangThaiSlot.DANG_GIU, TrangThaiSlot.DA_DAT],
    })
    return render(request, 'schedule/lich_quan_ly.html', du_lieu)


def _url_them(ngay, hom_nay):
    """Nút 'Thêm khung giờ' điền sẵn ngày đang xem (nếu chưa qua)."""
    url = reverse('lich_them')
    return f'{url}?ngay={ngay.isoformat()}' if ngay >= hom_nay else url


@nhiep_anh_gia_da_duyet
@require_http_methods(['GET', 'POST'])
def lich_them(request, nag):
    """UC3.1 bước 3-7 (thêm khung giờ): GET hiện form, POST kiểm tra (bước 4) rồi lưu (bước 6)."""
    if request.method == 'POST':
        form = KhungGioForm(request.POST, nag=nag)
        if form.is_valid():
            try:
                lich = quan_ly.luu_khung_gio_moi(form)
            except LichLoi as loi:                              # ngoại lệ 6a
                form.add_error(None, loi.thong_bao)
            else:
                messages.success(request, quan_ly.TB_THANH_CONG)    # bước 7
                return redirect(url_lich(CHE_DO_TUAN, lich.Ngay))
    else:
        ngay = quan_ly.phan_tich_ngay(request.GET.get('ngay'))
        form = KhungGioForm(nag=nag, initial={'Ngay': ngay} if request.GET.get('ngay') else None)
    return render(request, 'schedule/lich_form.html', {
        'form': form, 'tieu_de': 'Thiết lập khung giờ',
        'url_quay_lai': url_lich(CHE_DO_TUAN, quan_ly.bay_gio().date()),
    })


@nhiep_anh_gia_da_duyet
@require_http_methods(['GET', 'POST'])
def lich_sua(request, nag, pk):
    """UC3.1 bước 3-7 (sửa khung giờ). Chỉ sửa được khung giờ 'Lịch trống' chưa bắt đầu."""
    quan_ly.nha_giu_cho_het_han()        # khung giờ đang "giữ chỗ" quá hạn phải được trả về "Lịch trống" trước khi kiểm tra
    try:
        lich = quan_ly.lay_khung_gio_cua_nag(nag, pk)
        quan_ly.kiem_tra_duoc_sua(lich)
    except LichLoi as loi:
        if loi.khong_tim_thay:
            raise Http404(loi.thong_bao)
        messages.error(request, loi.thong_bao)
        return redirect(url_lich(CHE_DO_TUAN, lich.Ngay))
    url_quay_lai = url_lich(CHE_DO_TUAN, lich.Ngay)
    if request.method == 'POST':
        form = KhungGioForm(request.POST, instance=lich, nag=nag)
        if form.is_valid():
            try:
                lich = quan_ly.luu_khung_gio_sua(nag, form)
            except LichLoi as loi:
                if loi.khong_tim_thay:
                    raise Http404(loi.thong_bao)
                messages.error(request, loi.thong_bao)
                return redirect(url_quay_lai)
            messages.success(request, quan_ly.TB_THANH_CONG)
            return redirect(url_lich(CHE_DO_TUAN, lich.Ngay))
    else:
        form = KhungGioForm(instance=lich, nag=nag)
    return render(request, 'schedule/lich_form.html', {
        'form': form, 'tieu_de': 'Chỉnh sửa khung giờ', 'url_quay_lai': url_quay_lai,
    })


@nhiep_anh_gia_da_duyet
@require_http_methods(['GET', 'POST'])
def lich_xoa(request, nag, pk):
    """Xóa khung giờ. POST = xóa thật (popup xác nhận ở trang lịch gửi vào đây). GET = trang xác nhận dự phòng khi tắt JS."""
    quan_ly.nha_giu_cho_het_han()
    try:
        lich = quan_ly.lay_khung_gio_cua_nag(nag, pk)
    except LichLoi as loi:
        raise Http404(loi.thong_bao)
    url_quay_lai = url_lich(CHE_DO_TUAN, lich.Ngay)
    if request.method == 'POST':
        try:
            ngay = quan_ly.xoa_khung_gio(nag, pk)
        except LichLoi as loi:
            if loi.khong_tim_thay:
                raise Http404(loi.thong_bao)
            messages.error(request, loi.thong_bao)
            return redirect(url_quay_lai)
        messages.success(request, quan_ly.TB_THANH_CONG)
        return redirect(url_lich(CHE_DO_TUAN, ngay))
    try:
        quan_ly.kiem_tra_duoc_xoa(lich)
    except LichLoi as loi:
        messages.error(request, loi.thong_bao)
        return redirect(url_quay_lai)
    return render(request, 'schedule/lich_xoa_xac_nhan.html', {
        'lich': lich, 'nhan_ngay': quan_ly.nhan_ngay(lich.Ngay), 'url_quay_lai': url_quay_lai,
    })
