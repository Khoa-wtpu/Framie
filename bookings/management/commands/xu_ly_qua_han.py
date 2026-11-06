# Lệnh chạy định kỳ cho T10:  python manage.py xu_ly_qua_han
#   Chạy một lần rồi thoát (dùng cho Task Scheduler của Windows / cron: lặp mỗi 1 phút).
#   Hoặc để chạy liên tục:     python manage.py xu_ly_qua_han --lap 60     (mỗi 60 giây, Ctrl+C để dừng)
import time

from django.core.management.base import BaseCommand

from bookings.qua_han import xu_ly_qua_han


class Command(BaseCommand):
    help = 'Tự xử lý quá hạn: giữ chỗ 5 phút, đặt cọc 1 ngày, quá giờ chụp chưa xác nhận, thanh toán 60% 2 ngày, xóa ảnh sau 3 ngày mở quyền tải.'

    def add_arguments(self, parser):
        parser.add_argument('--lap', type=int, default=0, metavar='GIAY',
                            help='Lặp lại sau mỗi GIAY giây thay vì chạy một lần.')

    def _chay_mot_lan(self):
        kq = xu_ly_qua_han()
        loi = [k for k, v in kq.items() if v is None]
        self.stdout.write(
            f'Giữ chỗ hết hạn: {kq["giu_cho"] or 0} | Hết hạn đặt cọc: {kq["dat_coc"] or 0} | '
            f'Tự hủy quá giờ chụp: {kq["cho_xac_nhan"] or 0} | '
            f'Quá hạn thanh toán 60%: {kq["thanh_toan_60"] or 0} | Ảnh đã xóa: {kq["xoa_anh"] or 0}')
        if loi:
            self.stderr.write(f'Có việc bị lỗi (xem log): {", ".join(loi)}')

    def handle(self, *args, **opts):
        if opts['lap'] <= 0:
            return self._chay_mot_lan()
        try:
            while True:
                self._chay_mot_lan()
                time.sleep(opts['lap'])
        except KeyboardInterrupt:
            self.stdout.write('Đã dừng.')