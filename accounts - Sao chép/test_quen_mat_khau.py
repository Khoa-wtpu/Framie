# =====================================================================
# accounts/test_quen_mat_khau.py  -  test cho P6: Quên mật khẩu (Phanh)
# Chạy: python manage.py test accounts
# =====================================================================
from datetime import timedelta  # khoảng thời gian, dùng để giả lập mã quá hạn
from unittest import mock  # mock: giả lập hàm gửi email bị lỗi

from django.core import mail  # mail.outbox: hộp thư giả, Django tự dùng khi chạy test
from django.test import TestCase  # mỗi test chạy trên DB tạm
from django.utils import timezone  # giờ hiện tại có múi giờ

from accounts.models import User, YeuCauDatLaiMatKhau  # model User và lượt yêu cầu
from accounts.services import (  # các hàm cần kiểm tra trực tiếp
    KQ_KHONG_CON_HIEU_LUC, tao_yeu_cau_dat_lai, xac_thuc_ma,
)
from core.constants import TrangThaiDatLaiMatKhau as TT  # 4 trạng thái lượt yêu cầu

MAT_KHAU_CU = 'Cu#Matkhau1'  # mật khẩu hiện tại của tài khoản thử
MAT_KHAU_MOI = 'Moi#Matkhau2'  # mật khẩu mới hợp lệ (8+ ký tự, hoa, thường, số, đặc biệt)
URL_1 = '/quen-mat-khau/'  # bước 1
URL_2 = '/quen-mat-khau/xac-thuc/'  # bước 2
URL_3 = '/quen-mat-khau/dat-lai/'  # bước 3


class QuenMatKhauTests(TestCase):  # nhóm test của P6

    def setUp(self):  # chạy trước MỖI test: tạo một tài khoản để quên mật khẩu
        self.user = User.objects.create_user(  # tạo User thật
            username='an@example.com', email='an@example.com', password=MAT_KHAU_CU,  # username = email như P4
            so_dien_thoai='0900000001', first_name='An', last_name='Nguyễn Văn',  # các cột bắt buộc
        )  # hết tạo User

    def gui_email(self, email='an@example.com'):  # bước 1: gửi email xin mã, trả về lượt yêu cầu vừa tạo
        self.client.post(URL_1, {'email': email})  # gửi form bước 1
        return YeuCauDatLaiMatKhau.objects.latest('MaYeuCauDatLai')  # lượt mới nhất

    def xac_thuc(self, ma):  # bước 2: nhập mã
        return self.client.post(URL_2, {'ma': ma})  # gửi form bước 2

    def lui_thoi_gian(self, yeu_cau, phut=20):  # giả lập "đã quá hạn" bằng cách kéo lùi mốc thời gian của lượt
        bay_gio = timezone.now()  # giờ hiện tại
        cap_nhat = {'ThoiDiemGui': bay_gio - timedelta(minutes=phut), 'ThoiDiemHetHan': bay_gio - timedelta(minutes=phut - 10)}  # giữ ràng buộc HetHan > Gui
        yeu_cau.refresh_from_db()  # đọc lại trạng thái mới nhất
        if yeu_cau.ThoiDiemXacThuc:  # nếu đã xác thực thì giờ xác thực cũng phải nằm trong khoảng [Gui, HetHan]
            cap_nhat['ThoiDiemXacThuc'] = bay_gio - timedelta(minutes=phut - 5)  # giữ ràng buộc CSDL
        YeuCauDatLaiMatKhau.objects.filter(pk=yeu_cau.pk).update(**cap_nhat)  # ghi thẳng vào CSDL
        yeu_cau.refresh_from_db()  # đọc lại để biến yeu_cau có giá trị mới

    def den_buoc_3(self):  # đi nhanh qua bước 1 và 2, trả về lượt yêu cầu đã xác thực
        yeu_cau = self.gui_email()  # bước 1
        self.xac_thuc(yeu_cau.OtpXacThuc)  # bước 2 với mã đúng
        yeu_cau.refresh_from_db()  # đọc lại trạng thái
        return yeu_cau  # trả về

    # ---------------- Bước 1: nhập email ----------------
    def test_mo_trang_quen_mat_khau(self):  # GET bước 1 phải hiện form
        res = self.client.get(URL_1)  # mở trang
        self.assertEqual(res.status_code, 200)  # mở được
        self.assertContains(res, 'Email đã đăng ký')  # có ô email

    def test_email_chua_dang_ky(self):  # email lạ phải báo rõ và không tạo lượt, không gửi email
        res = self.client.post(URL_1, {'email': 'la@example.com'})  # gửi email chưa đăng ký
        self.assertContains(res, 'Email này chưa được đăng ký.')  # câu báo đúng đặc tả
        self.assertEqual(YeuCauDatLaiMatKhau.objects.count(), 0)  # không tạo lượt
        self.assertEqual(len(mail.outbox), 0)  # không gửi email

    def test_gui_ma_thanh_cong(self):  # luồng chính bước 1
        res = self.client.post(URL_1, {'email': 'an@example.com'})  # gửi email đã đăng ký
        self.assertRedirects(res, URL_2)  # sang bước 2
        yeu_cau = YeuCauDatLaiMatKhau.objects.get()  # đúng một lượt
        self.assertEqual(yeu_cau.TrangThai, TT.CHO_XAC_THUC)  # trạng thái Chờ xác thực
        self.assertRegex(yeu_cau.OtpXacThuc, r'^[0-9]{6}$')  # mã đúng 6 chữ số
        thoi_han = yeu_cau.ThoiDiemHetHan - yeu_cau.ThoiDiemGui  # thời hạn của mã
        self.assertLessEqual(thoi_han, timedelta(minutes=10))  # tối đa 10 phút
        self.assertGreater(thoi_han, timedelta(minutes=9, seconds=50))  # và đúng khoảng 10 phút
        self.assertEqual(len(mail.outbox), 1)  # đúng một email
        self.assertEqual(mail.outbox[0].to, ['an@example.com'])  # gửi đúng người
        self.assertIn(yeu_cau.OtpXacThuc, mail.outbox[0].body)  # email chứa mã

    def test_email_khac_hoa_thuong_van_tim_thay(self):  # AN@Example.com vẫn là tài khoản an@example.com
        res = self.client.post(URL_1, {'email': 'AN@Example.COM'})  # gõ hoa thường lộn xộn
        self.assertRedirects(res, URL_2)  # vẫn sang bước 2

    def test_gui_email_loi_khong_cho_sang_buoc_2(self):  # gửi lỗi thì phải báo lỗi và hủy lượt
        with mock.patch('accounts.services.send_mail', side_effect=OSError('SMTP down')), \
                self.assertLogs('accounts.services', level='ERROR'):  # giả lập máy chủ email hỏng và hứng dòng log lỗi
            res = self.client.post(URL_1, {'email': 'an@example.com'})  # gửi
        self.assertEqual(res.status_code, 200)  # ở lại bước 1
        self.assertContains(res, 'Không gửi được email lúc này.')  # báo lỗi
        self.assertEqual(YeuCauDatLaiMatKhau.objects.get().TrangThai, TT.HET_HAN)  # lượt bị hủy vì không ai nhận được mã

    def test_yeu_cau_moi_lam_ma_cu_het_han(self):  # xin mã lần hai thì mã lần một mất hiệu lực
        lan_1 = self.gui_email()  # xin mã lần 1
        lan_2 = self.gui_email()  # xin mã lần 2
        lan_1.refresh_from_db()  # đọc lại lượt 1
        self.assertEqual(lan_1.TrangThai, TT.HET_HAN)  # lượt 1 hết hạn
        self.assertEqual(lan_2.TrangThai, TT.CHO_XAC_THUC)  # lượt 2 còn dùng được

    def test_link_quay_lai_dang_nhap(self):  # feedback P6-3: link phải trỏ đúng trang đăng nhập, không được rỗng
        res = self.client.get(URL_1)  # mở trang bước 1
        self.assertContains(res, 'href="/dang-nhap/"')  # có link tới trang đăng nhập

    def test_form_khong_con_js_viet_trong_html(self):  # feedback P6-2: JS phải nằm trong file tĩnh, không viết trong thuộc tính HTML
        res = self.client.get(URL_1)  # mở trang bước 1
        self.assertNotContains(res, 'onsubmit')  # không còn onsubmit viết thẳng trong thẻ form
        self.assertContains(res, 'data-chong-bam-doi')  # form được đánh dấu để file JS xử lý
        self.assertContains(res, 'accounts/js/dat_lai_mat_khau.js')  # và trang nạp đúng file JS tĩnh

    def test_da_dang_nhap_bi_chuyen_di(self):  # người đã đăng nhập không cần quên mật khẩu
        self.client.force_login(self.user)  # đăng nhập thẳng
        self.assertEqual(self.client.get(URL_1).status_code, 302)  # bị chuyển đi

    # ---------------- Bước 2: nhập mã ----------------
    def test_ma_dung(self):  # nhập đúng mã thì sang bước 3
        yeu_cau = self.gui_email()  # bước 1
        res = self.xac_thuc(yeu_cau.OtpXacThuc)  # nhập đúng mã
        self.assertRedirects(res, URL_3)  # sang bước 3
        yeu_cau.refresh_from_db()  # đọc lại
        self.assertEqual(yeu_cau.TrangThai, TT.DA_XAC_THUC)  # trạng thái Đã xác thực
        self.assertIsNotNone(yeu_cau.ThoiDiemXacThuc)  # có ghi giờ xác thực

    def test_ma_sai(self):  # nhập sai mã phải báo rõ, vẫn Chờ xác thực
        yeu_cau = self.gui_email()  # bước 1
        sai = '000000' if yeu_cau.OtpXacThuc != '000000' else '111111'  # một mã chắc chắn khác mã thật
        res = self.xac_thuc(sai)  # nhập sai
        self.assertContains(res, 'Mã xác thực không đúng.')  # câu báo
        self.assertContains(res, 'còn 4 lần thử')  # báo số lần còn lại
        yeu_cau.refresh_from_db()  # đọc lại
        self.assertEqual(yeu_cau.TrangThai, TT.CHO_XAC_THUC)  # vẫn Chờ xác thực

    def test_sai_qua_5_lan_bi_huy(self):  # sai 5 lần thì lượt bị hủy, kể cả khi lần 6 nhập đúng
        yeu_cau = self.gui_email()  # bước 1
        sai = '000000' if yeu_cau.OtpXacThuc != '000000' else '111111'  # mã chắc chắn sai
        for _ in range(5):  # nhập sai 5 lần
            res = self.xac_thuc(sai)  # nhập sai
        self.assertRedirects(res, URL_1)  # lần thứ 5 bị đưa về bước 1
        yeu_cau.refresh_from_db()  # đọc lại
        self.assertEqual(yeu_cau.TrangThai, TT.HET_HAN)  # lượt bị hủy
        self.assertRedirects(self.xac_thuc(yeu_cau.OtpXacThuc), URL_1)  # mã đúng cũng không còn tác dụng

    def test_ma_het_han(self):  # quá 10 phút thì báo hết hạn
        yeu_cau = self.gui_email()  # bước 1
        self.lui_thoi_gian(yeu_cau)  # giả lập đã quá hạn
        res = self.client.post(URL_2, {'ma': yeu_cau.OtpXacThuc}, follow=True)  # nhập mã ĐÚNG nhưng quá hạn, đi theo chuyển trang
        self.assertContains(res, 'Mã xác thực đã hết hạn.')  # câu báo
        yeu_cau.refresh_from_db()  # đọc lại
        self.assertEqual(yeu_cau.TrangThai, TT.HET_HAN)  # trạng thái Hết hạn

    def test_ma_sai_dinh_dang(self):  # không phải 6 chữ số thì báo lỗi định dạng, không tính là lần sai
        self.gui_email()  # bước 1
        for ma in ('12345', '1234567', 'abcdef', '12 456'):  # thiếu, thừa, chữ, có cách
            with self.subTest(ma=ma):  # báo riêng từng giá trị
                res = self.xac_thuc(ma)  # nhập
                self.assertContains(res, 'Mã xác thực gồm đúng 6 chữ số.')  # câu báo
        self.assertEqual(self.client.session['dat_lai_so_lan_sai'], 0)  # bộ đếm lần sai vẫn bằng 0

    def test_vao_thang_buoc_2_va_3_khi_chua_qua_buoc_1(self):  # không có phiên thì bị đưa về bước 1
        self.assertRedirects(self.client.get(URL_2), URL_1)  # bước 2
        self.assertRedirects(self.client.get(URL_3), URL_1)  # bước 3

    def test_vao_buoc_3_khi_chua_nhap_ma(self):  # đã xin mã nhưng chưa nhập thì không được đặt mật khẩu
        self.gui_email()  # bước 1 xong, chưa nhập mã
        self.assertRedirects(self.client.get(URL_3), URL_1)  # bị đưa về bước 1
        res = self.client.post(URL_3, {'mat_khau_moi': MAT_KHAU_MOI})  # cố đặt mật khẩu thẳng
        self.assertRedirects(res, URL_1)  # vẫn bị chặn
        self.user.refresh_from_db()  # đọc lại User
        self.assertTrue(self.user.check_password(MAT_KHAU_CU))  # mật khẩu cũ còn nguyên

    # ---------------- Bước 3: đặt mật khẩu mới ----------------
    def test_dat_lai_thanh_cong(self):  # luồng chính bước 3
        yeu_cau = self.den_buoc_3()  # đi qua bước 1 và 2
        res = self.client.post(URL_3, {'mat_khau_moi': MAT_KHAU_MOI})  # nhập mật khẩu mới hợp lệ
        self.assertRedirects(res, '/dang-nhap/')  # chuyển sang đăng nhập
        yeu_cau.refresh_from_db()  # đọc lại
        self.assertEqual(yeu_cau.TrangThai, TT.DA_DAT_LAI)  # trạng thái Đã đặt lại mật khẩu
        self.user.refresh_from_db()  # đọc lại User
        self.assertTrue(self.user.check_password(MAT_KHAU_MOI))  # mật khẩu mới đúng
        self.assertFalse(self.user.check_password(MAT_KHAU_CU))  # mật khẩu cũ hết hiệu lực
        self.assertNotEqual(self.user.password, MAT_KHAU_MOI)  # lưu dạng băm, không lưu mật khẩu thô

    def test_dang_nhap_bang_mat_khau_moi(self):  # đăng nhập thật bằng mật khẩu mới, mật khẩu cũ bị từ chối
        self.den_buoc_3()  # đi qua bước 1 và 2
        self.client.post(URL_3, {'mat_khau_moi': MAT_KHAU_MOI})  # đặt mật khẩu mới
        self.client.logout()  # chắc chắn chưa đăng nhập
        cu = self.client.post('/dang-nhap/', {'username': 'an@example.com', 'password': MAT_KHAU_CU})  # thử mật khẩu cũ
        self.assertEqual(cu.status_code, 200)  # ở lại trang đăng nhập
        self.assertNotIn('_auth_user_id', self.client.session)  # chưa đăng nhập được
        moi = self.client.post('/dang-nhap/', {'username': 'an@example.com', 'password': MAT_KHAU_MOI})  # thử mật khẩu mới
        self.assertEqual(moi.status_code, 302)  # đăng nhập thành công
        self.assertIn('_auth_user_id', self.client.session)  # đã có phiên

    def test_phien_dang_nhap_cu_mat_hieu_luc(self):  # đang đăng nhập ở máy khác thì sau khi đổi mật khẩu bị đăng xuất
        may_khac = self.client_class()  # một trình duyệt khác
        may_khac.force_login(self.user)  # trình duyệt đó đang đăng nhập
        self.assertEqual(may_khac.get('/dang-xuat/').status_code, 200)  # trước khi đổi: vào được trang chỉ dành cho người đã đăng nhập
        self.den_buoc_3()  # trình duyệt chính đi qua bước 1 và 2
        self.client.post(URL_3, {'mat_khau_moi': MAT_KHAU_MOI})  # đặt mật khẩu mới
        self.assertEqual(may_khac.get('/dang-xuat/').status_code, 302)  # sau khi đổi: bị đưa về trang đăng nhập

    def test_mat_khau_yeu_bi_tu_choi(self):  # mỗi kiểu thiếu một luật; mật khẩu cũ vẫn còn
        yeu_cau = self.den_buoc_3()  # đi qua bước 1 và 2
        for yeu in ('Ab#1xyz', 'moi#matkhau2', 'MOI#MATKHAU2', 'Moi#Matkhau', 'Moi1Matkhau2', 'Matkhẩu123'):  # ngắn, thiếu hoa, thiếu thường, thiếu số, thiếu ký tự đặc biệt, chữ có dấu không phải ký tự đặc biệt
            with self.subTest(mat_khau=yeu):  # báo riêng từng mật khẩu
                res = self.client.post(URL_3, {'mat_khau_moi': yeu})  # gửi
                self.assertEqual(res.status_code, 200)  # ở lại bước 3
                self.assertTrue(res.context['form'].errors.get('mat_khau_moi'))  # ô mật khẩu có lỗi
        yeu_cau.refresh_from_db()  # đọc lại
        self.assertEqual(yeu_cau.TrangThai, TT.DA_XAC_THUC)  # lượt vẫn chờ đặt mật khẩu
        self.user.refresh_from_db()  # đọc lại User
        self.assertTrue(self.user.check_password(MAT_KHAU_CU))  # mật khẩu cũ chưa đổi

    def test_loi_mat_khau_chi_hien_mot_lan(self):  # feedback P6-1: mỗi câu lỗi mật khẩu chỉ được hiện đúng 1 lần
        self.den_buoc_3()  # đi qua bước 1 và 2
        res = self.client.post(URL_3, {'mat_khau_moi': 'moi#matkhau2'})  # mật khẩu thiếu chữ hoa
        self.assertContains(res, 'Mật khẩu phải có ít nhất một chữ hoa.', count=1)  # câu báo xuất hiện đúng 1 lần

    def test_mat_khau_giong_email_bi_tu_choi(self):  # luật giống thông tin cá nhân của Django cũng áp dụng
        self.den_buoc_3()  # đi qua bước 1 và 2
        res = self.client.post(URL_3, {'mat_khau_moi': 'An@example1'})  # mật khẩu lấy từ email
        self.assertTrue(res.context['form'].errors.get('mat_khau_moi'))  # bị từ chối

    def test_het_han_giua_buoc_2_va_3(self):  # xác thực xong nhưng để quá hạn mới nhập mật khẩu
        yeu_cau = self.den_buoc_3()  # đi qua bước 1 và 2
        self.lui_thoi_gian(yeu_cau)  # giả lập đã quá hạn
        res = self.client.post(URL_3, {'mat_khau_moi': MAT_KHAU_MOI})  # nhập mật khẩu hợp lệ
        self.assertRedirects(res, URL_1)  # bị đưa về bước 1
        yeu_cau.refresh_from_db()  # đọc lại
        self.assertEqual(yeu_cau.TrangThai, TT.HET_HAN)  # Hết hạn
        self.user.refresh_from_db()  # đọc lại User
        self.assertTrue(self.user.check_password(MAT_KHAU_CU))  # mật khẩu không bị đổi

    def test_khong_dung_lai_luot_da_hoan_tat(self):  # lượt đã Đã đặt lại mật khẩu thì mã không còn tác dụng
        yeu_cau = self.den_buoc_3()  # đi qua bước 1 và 2
        self.client.post(URL_3, {'mat_khau_moi': MAT_KHAU_MOI})  # hoàn tất
        yeu_cau.refresh_from_db()  # đọc lại
        self.assertEqual(xac_thuc_ma(yeu_cau, yeu_cau.OtpXacThuc), KQ_KHONG_CON_HIEU_LUC)  # mã đúng cũng bị từ chối
        self.assertEqual(self.client.get(URL_3).status_code, 302)  # và không vào lại được bước 3

    def test_moi_luot_chi_co_mot_ma_con_dung_duoc(self):  # hàm tạo lượt phải đóng mọi lượt cũ của cùng User
        tao_yeu_cau_dat_lai(self.user)  # lượt 1
        tao_yeu_cau_dat_lai(self.user)  # lượt 2
        tao_yeu_cau_dat_lai(self.user)  # lượt 3
        con_dung = YeuCauDatLaiMatKhau.objects.filter(TrangThai=TT.CHO_XAC_THUC).count()  # đếm lượt còn Chờ xác thực
        self.assertEqual(con_dung, 1)  # chỉ còn đúng một
