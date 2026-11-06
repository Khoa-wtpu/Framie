# notifications/management/commands/thu_email_mau.py - P9: gửi thử các email mẫu cho một tài khoản
import time  # đo tổng thời gian gửi (yêu cầu dưới 1 phút)

from django.contrib.auth import get_user_model  # lấy model User của project
from django.core.management.base import BaseCommand, CommandError  # lớp cha của lệnh và lỗi báo ra Terminal

from notifications.mau_email import MAU, SU_KIEN  # nội dung mẫu ở bước 1
from notifications.services import gui_thong_bao_kem_email  # hàm chính của P9


class Command(BaseCommand):  # mỗi lệnh manage.py là một lớp tên Command
    help = 'Gửi thử email mẫu P9. Ví dụ: python manage.py thu_email_mau --user kh01'  # hiện khi gõ help

    def add_arguments(self, parser):  # khai báo tham số của lệnh
        parser.add_argument('--user', required=True, help='username người nhận thử')  # bắt buộc có --user

    def handle(self, *args, **options):  # hàm chạy khi gõ lệnh
        try:  # tìm tài khoản theo username
            nguoi = get_user_model().objects.get(username=options['user'])  # lấy đúng một người
        except get_user_model().DoesNotExist:  # không có username này
            raise CommandError(f"Không có tài khoản '{options['user']}'")  # báo lỗi rõ ràng rồi dừng
        bat_dau = time.monotonic()  # ghi giờ bắt đầu
        for ma_su_kien, (tieu_de, noi_dung) in SU_KIEN.items():  # duyệt từng sự kiện
            tb = gui_thong_bao_kem_email(nguoi, tieu_de, noi_dung.format(**MAU))  # điền chỗ trống rồi gửi web và email
            if tb is None:  # không tạo được thông báo
                self.stdout.write(f'{ma_su_kien}: LỖI, không tạo được thông báo')  # in lỗi
                continue  # sang sự kiện kế
            tb.refresh_from_db()  # đọc lại để thấy TrangThaiGuiEmail vừa được ghi
            self.stdout.write(f'{ma_su_kien}: {tb.TrangThaiGuiEmail}')  # in kết quả từng sự kiện
        self.stdout.write(f'Xong sau {time.monotonic() - bat_dau:.1f} giây.')  # in tổng thời gian