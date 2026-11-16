# =====================================================================
# core/management/commands/nap_khu_vuc.py   (task F1)
# Lệnh nạp RIÊNG cho bảng KHUVUC: đủ 34 đơn vị cấp tỉnh (Quyết định 19/2025/QĐ-TTg).
#
#   python manage.py nap_khu_vuc              nạp / cập nhật
#   python manage.py nap_khu_vuc --chi-xem    chỉ báo sẽ làm gì, không ghi database
#
# An toàn khi chạy nhiều lần và KHÔNG xóa bất cứ dữ liệu nào:
#   1. Khu vực mang tên cũ (TP. Hồ Chí Minh, TP.HCM, Đà Lạt, Nha Trang) được ĐỔI TÊN thành
#      tên mới (Hồ Chí Minh, Lâm Đồng, Khánh Hòa), nên hồ sơ Nhiếp ảnh gia đang gắn với
#      chúng vẫn giữ nguyên liên kết. Nếu tên mới đã có sẵn thì KHÔNG đổi, chỉ báo để xử lý tay.
#   2. Khu vực nào trong 34 chưa có thì được tạo thêm.
#   3. Khu vực khác không thuộc 34 (do bạn tự thêm) được giữ nguyên, chỉ liệt kê ra.
# Danh sách tên nằm ở core/du_lieu_khu_vuc.py.
# =====================================================================
from django.core.management.base import BaseCommand
from django.db import transaction

from core.du_lieu_khu_vuc import DANH_SACH_34, TEN_34, TEN_CU_SANG_MOI
from profiles.models import KhuVuc


class Command(BaseCommand):
    help = 'Nạp 34 đơn vị cấp tỉnh vào bảng Khu vực (đổi tên khu vực cũ, thêm khu vực thiếu, không xóa gì).'

    def add_arguments(self, parser):
        parser.add_argument('--chi-xem', action='store_true',
                            help='Chỉ hiển thị việc sẽ làm, không ghi vào database.')

    def handle(self, *args, **opts):
        chi_xem = opts['chi_xem']
        doi_ten, khong_doi, da_tao, da_co = [], [], [], []
        with transaction.atomic():
            ten_hien_co = set(KhuVuc.objects.values_list('TenKhuVuc', flat=True))

            # 1) Đổi tên khu vực cũ -> tên mới (giữ liên kết với hồ sơ Nhiếp ảnh gia)
            for cu, moi in TEN_CU_SANG_MOI.items():
                if cu not in ten_hien_co:
                    continue
                if moi in ten_hien_co:
                    khong_doi.append((cu, moi))
                    continue
                doi_ten.append((cu, moi))
                ten_hien_co.discard(cu)
                ten_hien_co.add(moi)
                if not chi_xem:
                    KhuVuc.objects.filter(TenKhuVuc=cu).update(TenKhuVuc=moi)

            # 2) Thêm khu vực còn thiếu
            for _, ten, _ in DANH_SACH_34:
                if ten in ten_hien_co:
                    da_co.append(ten)
                else:
                    da_tao.append(ten)
                    if not chi_xem:
                        KhuVuc.objects.create(TenKhuVuc=ten)

            # 3) Khu vực ngoài danh sách: chỉ liệt kê
            la = sorted(ten_hien_co - set(TEN_34))
            tong = KhuVuc.objects.count() if not chi_xem else None

        tien_to = '[CHỈ XEM] ' if chi_xem else ''
        self.stdout.write(self.style.SUCCESS(f'{tien_to}Khu vực: 34 đơn vị cấp tỉnh (Quyết định 19/2025/QĐ-TTg).'))
        self.stdout.write(f'  Đã có sẵn : {len(da_co)}')
        self.stdout.write(f'  Tạo mới   : {len(da_tao)}')
        self.stdout.write(f'  Đổi tên   : {len(doi_ten)}' + ''.join(f'\n      {cu} -> {moi}' for cu, moi in doi_ten))
        if khong_doi:
            self.stdout.write(self.style.WARNING(
                '  Không đổi tên được vì tên mới đã tồn tại (hãy gộp tay trong trang quản trị nếu cần):'
                + ''.join(f'\n      {cu} (giữ nguyên), đã có {moi}' for cu, moi in khong_doi)))
        if la:
            self.stdout.write(self.style.WARNING(
                '  Khu vực ngoài danh sách 34 (giữ nguyên, không xóa): ' + ', '.join(la)))
        if tong is not None:
            self.stdout.write(f'  Tổng số khu vực trong database: {tong}')
