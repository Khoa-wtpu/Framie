
# bookings/test_nen_qua_han.py
# File kiểm thử các chức năng trong bookings/nen_qua_han.py.
# Mục đích: Đảm bảo luồng nền có thể tự động xử lý các lượt đặt chỗ quá hạn.

# Chạy kiểm thử bằng lệnh:
# python manage.py test bookings.test_nen_qua_han

# Không sử dụng luồng xử lý và database thật.
# Thay vào đó, sử dụng mock để giả lập hàm xu_ly_qua_han và kết nối database.

import threading  # Thư viện quản lý luồng và sự kiện đồng bộ giữa các luồng.
from unittest import mock  # Công cụ giả lập đối tượng, hàm và hành vi trong quá trình kiểm thử.

from django.test import SimpleTestCase, override_settings
# SimpleTestCase: Lớp kiểm thử đơn giản của Django, không cần tạo database thật.
# override_settings: Cho phép thay đổi tạm thời cấu hình settings.py trong từng test.

from bookings import nen_qua_han as nen
# Import module nen_qua_han và đặt bí danh nen để gọi các hàm cần kiểm thử.


class NenQuaHanTest(SimpleTestCase):
    # Khai báo lớp chứa các trường hợp kiểm thử cho chức năng xử lý quá hạn nền.
    # Kế thừa SimpleTestCase để thực hiện kiểm thử mà không cần database thật.

    def tearDown(self):
        # Hàm tearDown được Django tự động gọi sau khi mỗi test kết thúc.
        # Dùng để dọn dẹp tài nguyên và tránh luồng nền còn chạy sang test tiếp theo.

        nen.dung()  # Luôn dừng luồng nền sau mỗi test để tránh ảnh hưởng các test khác.

    def test_mac_dinh_tat_khi_chay_test(self):
        # Kiểm tra luồng nền mặc định bị tắt khi chạy lệnh manage.py test.
        # Mục đích: Tránh tự động tạo luồng nền trong quá trình kiểm thử.

        from django.conf import settings
        # Import settings để truy cập các cấu hình hiện tại của Django.

        self.assertEqual(settings.XU_LY_QUA_HAN_NEN_GIAY, 0)
        # Kiểm tra cấu hình XU_LY_QUA_HAN_NEN_GIAY bằng 0.
        # Nếu bằng 0 thì hệ thống không tự động khởi động luồng nền.

        self.assertFalse(nen.bat_dau())
        # Gọi hàm bat_dau() và kiểm tra kết quả trả về là False.
        # Xác nhận luồng nền không được khởi động khi cấu hình bằng 0.

    @override_settings(XU_LY_QUA_HAN_NEN_GIAY=0)
    # Tạm thời đặt thời gian xử lý nền bằng 0 trong phạm vi test này.
    # Sau khi test kết thúc, Django tự khôi phục cấu hình ban đầu.

    def test_dat_0_thi_khong_mo_luong(self):
        # Kiểm tra khi cấu hình bằng 0 thì chương trình không tạo luồng mới.

        with mock.patch('threading.Thread') as luong:
            # Giả lập lớp threading.Thread.
            # Mọi thao tác tạo luồng trong phạm vi with sẽ được theo dõi,
            # nhưng không thực sự tạo ra một luồng mới.

            self.assertFalse(nen.bat_dau())
            # Gọi hàm bat_dau() và xác nhận kết quả là False.

        luong.assert_not_called()
        # Kiểm tra threading.Thread không được gọi lần nào.
        # Xác nhận chương trình không tạo luồng nền khi cấu hình bằng 0.

    @override_settings(XU_LY_QUA_HAN_NEN_GIAY=0.05)
    # Thiết lập chu kỳ xử lý là 0.05 giây để kiểm thử nhanh.
    # Không cần chờ 60 giây như cấu hình mặc định.

    def test_luong_nen_tu_chay_xu_ly_qua_han_khong_can_ai_mo_web(self):
        # Kiểm tra luồng nền có thể tự động gọi hàm xử lý quá hạn định kỳ.
        # Không cần người dùng gửi request hoặc mở bất kỳ trang web nào.

        du_so_lan = threading.Event()
        # Tạo một sự kiện đồng bộ giữa các luồng.
        # Sự kiện này được bật khi hàm xử lý đã được gọi đủ số lần.

        dem = []
        # Tạo danh sách rỗng để đếm số lần hàm xử lý được gọi.
        # Mỗi lần gọi sẽ thêm một phần tử vào danh sách.

        def gia():
            # Khai báo hàm giả lập thay thế cho xu_ly_qua_han.

            dem.append(1)
            # Thêm một phần tử vào danh sách để ghi nhận một lần thực thi.

            if len(dem) >= 2:
                # Kiểm tra số lần hàm giả lập được gọi đã đạt ít nhất 2 lần chưa.

                du_so_lan.set()
                # Bật sự kiện để thông báo rằng luồng nền đã thực hiện đủ 2 lần.

            return {}
            # Trả về một dictionary rỗng để giả lập kết quả của hàm xử lý.

        with mock.patch('bookings.qua_han.xu_ly_qua_han', side_effect=gia), mock.patch.object(nen, 'connection'):
            # Giả lập hàm xu_ly_qua_han bằng hàm gia().
            # Mỗi khi luồng nền gọi xu_ly_qua_han(), hàm gia() sẽ được thực thi.
            #
            # Đồng thời giả lập đối tượng connection trong module nen_qua_han.
            # Nhờ đó không sử dụng kết nối database thật trong quá trình kiểm thử.

            self.assertTrue(nen.bat_dau())
            # Khởi động luồng nền và kiểm tra kết quả trả về là True.
            # Xác nhận luồng đã được khởi động thành công.

            self.assertTrue(du_so_lan.wait(3), 'luồng nền không chạy xu_ly_qua_han định kỳ')
            # Chờ tối đa 3 giây để sự kiện du_so_lan được bật.
            # Nếu hàm xử lý được gọi đủ 2 lần, wait() trả về True.
            # Nếu hết 3 giây mà chưa đủ 2 lần, wait() trả về False
            # và kiểm thử báo lỗi với thông báo tương ứng.

            nen.dung()
            # Dừng luồng nền sau khi đã xác nhận luồng thực hiện đủ số lần.

        self.assertGreaterEqual(len(dem), 2)
        # Kiểm tra số lần hàm giả lập được gọi lớn hơn hoặc bằng 2.
        # Xác nhận luồng nền thực sự thực hiện xử lý định kỳ,
        # thay vì chỉ khởi động mà không thực hiện công việc.

    @override_settings(XU_LY_QUA_HAN_NEN_GIAY=60)
    # Thiết lập chu kỳ xử lý là 60 giây trong test này.

    def test_goi_bat_dau_hai_lan_chi_mot_luong(self):
        # Kiểm tra gọi bat_dau() nhiều lần cũng chỉ tạo một luồng nền.
        # Tránh trường hợp khởi động trùng lặp khi WSGI và ASGI cùng gọi hàm.

        with mock.patch.object(nen, 'connection'):
            # Giả lập connection để không sử dụng kết nối database thật.

            self.assertTrue(nen.bat_dau())
            # Gọi bat_dau() lần thứ nhất.
            # Kiểm tra luồng nền được khởi động thành công.

            luong = nen._luong
            # Lưu lại đối tượng luồng nền được tạo ở lần gọi thứ nhất.

            self.assertTrue(nen.bat_dau())
            # Gọi bat_dau() lần thứ hai.
            # Vì luồng thứ nhất vẫn đang chạy nên không tạo luồng mới.

            self.assertIs(nen._luong, luong)
            # Kiểm tra đối tượng luồng hiện tại vẫn chính là luồng đã lưu.
            # Xác nhận lần gọi thứ hai không thay thế hoặc tạo luồng khác.

            self.assertEqual(sum(t.name == 'framie-xu-ly-qua-han' for t in threading.enumerate()), 1)
            # threading.enumerate(): Lấy danh sách các luồng hiện đang hoạt động.
            #
            # Điều kiện t.name == 'framie-xu-ly-qua-han':
            # Chỉ chọn những luồng có tên đúng với tên luồng xử lý quá hạn.
            #
            # sum(...): Đếm số luồng thỏa mãn điều kiện.
            #
            # assertEqual(..., 1): Kiểm tra chỉ có đúng một luồng xử lý quá hạn đang chạy.

    def test_loi_trong_xu_ly_khong_lam_chet_luong(self):
        # Kiểm tra khi hàm xử lý quá hạn phát sinh lỗi,
        # chương trình vẫn bắt lỗi và đóng kết nối database.

        with mock.patch('bookings.qua_han.xu_ly_qua_han', side_effect=RuntimeError('hỏng')), \
                mock.patch.object(nen, 'connection') as kn, self.assertLogs(nen.logger, 'ERROR'):
            # Giả lập hàm xu_ly_qua_han phát sinh ngoại lệ RuntimeError('hỏng').
            #
            # Giả lập connection và đặt bí danh kn để theo dõi các thao tác
            # trên kết nối database, đặc biệt là phương thức close().
            #
            # assertLogs(nen.logger, 'ERROR'):
            # Kiểm tra trong quá trình thực thi có phát sinh log ở mức ERROR
            # hoặc mức nghiêm trọng hơn hay không.
            # Điều này xác nhận lỗi đã được ghi nhận vào hệ thống log.

            nen._chay_mot_vong()
            # Gọi trực tiếp hàm xử lý một vòng.
            # Hàm xu_ly_qua_han giả lập sẽ phát sinh RuntimeError.
            # Khối except trong _chay_mot_vong() phải bắt lỗi và ghi log.
            # Khối finally vẫn phải thực hiện đóng kết nối.

        kn.close.assert_called_once()
        # Kiểm tra phương thức close() được gọi đúng một lần.
        # Xác nhận kết nối database luôn được đóng kể cả khi xử lý xảy ra lỗi.
