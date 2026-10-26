# =====================================================================
# profiles/services.py  -  K2: hàm dùng chung về hồ sơ nhiếp ảnh gia (Khoa)
# Người dùng hàm này: Tuyền (trang chủ - "Nhiếp ảnh gia nổi bật").
#
#   nhiep_anh_gia_noi_bat(so_luong=3, diem_toi_thieu=4) -> list[dict]
# =====================================================================
from django.db.models import Avg, Count

from core.constants import TrangThaiHoSo
from profiles.models import NhiepAnhGia
from schedule.services import dem_khung_gio_trong


def nhiep_anh_gia_noi_bat(so_luong=3, diem_toi_thieu=4):
    """Danh sách nhiếp ảnh gia nổi bật cho trang chủ (mặc định 3 người).

    Điều kiện: hồ sơ 'Đã duyệt' và điểm đánh giá trung bình >= diem_toi_thieu (4 -> 5 sao).
    Xếp: điểm trung bình giảm dần, rồi số lượt đánh giá giảm dần, rồi mã tăng dần (kết quả ổn định).

    Mỗi phần tử là một dict, dùng thẳng trong template:
        nhiep_anh_gia   : đối tượng NhiepAnhGia
        ten             : tên hiển thị
        anh_dai_dien    : ImageField ảnh đại diện (dùng .url)
        anh_portfolio   : ảnh bìa project mới nhất; nếu chưa có project thì dùng ảnh đại diện
        loai_hinh       : chuỗi "Cưới, Chân dung"
        khu_vuc         : chuỗi "TP.HCM, Đà Lạt"
        diem_trung_binh : số, làm tròn 1 chữ số (ví dụ 4.8)
        so_danh_gia     : số lượt đánh giá
        so_khung_gio_trong : số khung giờ trống trong 7 ngày tới
    """
    ds = (NhiepAnhGia.objects
          .filter(MaTaiKhoan__trang_thai_ho_so=TrangThaiHoSo.DA_DUYET)
          .select_related('MaTaiKhoan')
          .annotate(diem_tb=Avg('danh_gias__Diem'), so_dg=Count('danh_gias'))
          .filter(diem_tb__gte=diem_toi_thieu)
          .order_by('-diem_tb', '-so_dg', 'pk')[:so_luong])

    ket_qua = []
    for nag in ds:
        user = nag.MaTaiKhoan
        project = nag.projects.order_by('-NgayTao').first()
        ket_qua.append({
            'nhiep_anh_gia': nag,
            'ten': user.get_full_name() or user.username,
            'anh_dai_dien': nag.AnhDaiDien,
            'anh_portfolio': project.AnhBia if project else nag.AnhDaiDien,
            'loai_hinh': ', '.join(nag.loai_hinh_chup.values_list('TenLoaiHinh', flat=True)),
            'khu_vuc': ', '.join(nag.khu_vuc.values_list('TenKhuVuc', flat=True)),
            'diem_trung_binh': round(nag.diem_tb, 1),
            'so_danh_gia': nag.so_dg,
            'so_khung_gio_trong': dem_khung_gio_trong(nag, 7),
        })
    return ket_qua