# chat/management/commands/don_anh_chat.py - dọn ảnh chat quá 6 tháng: xóa file ảnh khỏi thư mục riêng, GIỮ bản ghi để lịch sử tin nhắn vẫn đủ
from django.core.management.base import BaseCommand  # lớp nền của mọi lệnh manage.py

from chat import services  # lấy mốc hết hạn và kho ảnh chat
from chat.models import DinhKemTinNhan  # bảng ảnh đính kèm


class Command(BaseCommand):  # chạy: python manage.py don_anh_chat
    help = 'Xóa file ảnh trong chat đã quá 6 tháng kể từ lúc gửi (bản ghi vẫn giữ). Thêm --chi-xem để chỉ đếm, không xóa.'  # mô tả khi gõ --help

    def add_arguments(self, parser):  # khai báo tham số
        parser.add_argument('--chi-xem', action='store_true', help='Chỉ đếm số ảnh sẽ xóa, không xóa thật.')  # chạy thử an toàn

    def handle(self, *args, **tuy_chon):  # phần chạy chính
        chi_xem = tuy_chon['chi_xem']  # True nếu chỉ xem trước
        kho = services.kho_anh_chat()  # thư mục riêng chứa ảnh chat
        het_han = DinhKemTinNhan.objects.filter(MaTinNhan__ThoiGianGui__lt=services.han_luu_anh())  # ảnh của tin gửi trước mốc 6 tháng
        da_xoa, dung_luong, khong_con_file = 0, 0, 0  # bộ đếm
        for dk in het_han.iterator():  # duyệt từng ảnh, không nạp hết vào bộ nhớ
            if not kho.exists(dk.DuongDanFile):  # file đã bị xóa từ lần dọn trước
                khong_con_file += 1  # chỉ đếm
                continue  # sang ảnh kế
            dung_luong += dk.KichThuoc  # cộng dung lượng sẽ giải phóng
            da_xoa += 1  # đếm ảnh
            if not chi_xem:  # chạy thật
                kho.delete(dk.DuongDanFile)  # xóa file, bản ghi vẫn giữ
        dong = 'Sẽ xóa' if chi_xem else 'Đã xóa'  # câu báo cáo
        self.stdout.write('%s %d ảnh quá hạn (%.1f MB). %d ảnh đã dọn từ trước.' % (dong, da_xoa, dung_luong / 1048576, khong_con_file))  # in kết quả
