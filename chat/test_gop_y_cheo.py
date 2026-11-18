# chat/test_gop_y_cheo.py - test cho góp ý kiểm thử chéo D2 (C1: tách tin chữ + ảnh; C2: link bấm được và mục Liên kết). Test MỚI, không sửa test cũ. Chạy: python manage.py test chat.test_gop_y_cheo
from django.urls import reverse  # đổi name thành đường dẫn

from chat import services  # hàm nghiệp vụ
from chat.models import TinNhan  # bảng tin nhắn
from chat.test_nang_cap import CoSoAnh, _tao_anh  # dùng lại lớp nền (thư mục ảnh tạm, khách, nhiếp ảnh gia, cuộc trò chuyện) và hàm tạo ảnh giả
from chat.test_trao_doi import AJAX  # tiêu đề giả lập yêu cầu ngầm của chat.js


class TachTinChuVaAnhTests(CoSoAnh):  # C1: gửi đồng thời chữ và ảnh thì tách thành hai tin riêng
    def gui(self, noi_dung, ds_anh, tra_loi=None):  # POST như chat.js (gửi ngầm)
        self.client.force_login(self.khach)  # Khách hàng đăng nhập
        du_lieu = {'noi_dung': noi_dung, 'anh': ds_anh}  # nội dung và ảnh
        if tra_loi:  # có trả lời một tin
            du_lieu['tra_loi'] = tra_loi  # mã tin gốc
        return self.client.post(self.url_gui, du_lieu, **AJAX)  # multipart

    def test_chu_kem_anh_tach_hai_tin(self):  # một lần gửi, hai tin
        r = self.gui('xin chao', [_tao_anh()])  # vừa chữ vừa ảnh
        self.assertEqual(r.status_code, 200)  # thành công
        cac_tin = list(TinNhan.objects.filter(MaCuocTroChuyen=self.cuoc).order_by('MaTinNhan'))  # các tin theo thứ tự
        self.assertEqual(len(cac_tin), 2)  # đúng hai tin
        self.assertEqual(cac_tin[0].NoiDung, '')  # tin đầu: chỉ ảnh
        self.assertEqual(cac_tin[0].dinh_kem.count(), 1)  # có một ảnh
        self.assertEqual(cac_tin[1].NoiDung, 'xin chao')  # tin sau: chỉ chữ
        self.assertEqual(cac_tin[1].dinh_kem.count(), 0)  # không có ảnh
        self.assertEqual(r.json()['id'], cac_tin[1].pk)  # view trả mã tin cuối cùng

    def test_chi_chu_hoac_chi_anh_van_la_mot_tin(self):  # không làm đổi cách cũ
        self.gui('chi chu', [])  # chỉ chữ
        self.gui('', [_tao_anh()])  # chỉ ảnh
        self.assertEqual(TinNhan.objects.filter(MaCuocTroChuyen=self.cuoc).count(), 2)  # mỗi lần một tin

    def test_tra_loi_gan_vao_tin_anh(self):  # trích dẫn chỉ gắn một lần, vào tin ảnh
        goc = services.gui_tin_nhan(self.cuoc, self.nag.MaTaiKhoan, 'tin goc')  # tin để trả lời
        self.gui('tra loi kem anh', [_tao_anh()], tra_loi=goc.pk)  # trả lời bằng chữ + ảnh
        tin_anh = TinNhan.objects.filter(MaCuocTroChuyen=self.cuoc, dinh_kem__isnull=False).get()  # tin ảnh
        tin_chu = TinNhan.objects.get(MaCuocTroChuyen=self.cuoc, NoiDung='tra loi kem anh')  # tin chữ
        self.assertEqual(tin_anh.MaTinTraLoi_id, goc.pk)  # tin ảnh có trích dẫn
        self.assertIsNone(tin_chu.MaTinTraLoi_id)  # tin chữ không trích dẫn lần nữa

    def test_thu_hoi_tin_chu_khong_mat_anh(self):  # thu hồi từng phần
        self.gui('se thu hoi', [_tao_anh()])  # gửi chữ + ảnh
        tin_anh = TinNhan.objects.filter(MaCuocTroChuyen=self.cuoc, dinh_kem__isnull=False).get()  # tin ảnh
        tin_chu = TinNhan.objects.get(MaCuocTroChuyen=self.cuoc, NoiDung='se thu hoi')  # tin chữ
        services.thu_hoi_tin(self.cuoc, self.khach, tin_chu.pk)  # thu hồi tin chữ
        tin_anh.refresh_from_db()  # nạp lại
        tin_chu.refresh_from_db()  # nạp lại
        self.assertTrue(tin_chu.DaThuHoi)  # chữ đã thu hồi
        self.assertFalse(tin_anh.DaThuHoi)  # ảnh vẫn còn


class LienKetTests(CoSoAnh):  # C2: link bấm được và mục Liên kết ở cột phải
    def mo_trang(self):  # mở cuộc trò chuyện bằng Khách hàng
        self.client.force_login(self.khach)  # đăng nhập
        return self.client.get(self.url_trang)  # trang chat

    def test_tim_lien_ket_bo_dau_cau_cuoi(self):  # dấu chấm cuối câu không thuộc link
        ds = services.tim_lien_ket('xem https://example.com/a?b=1. nhe, va www.abc.vn!')  # hai link
        self.assertEqual([x['href'] for x in ds], ['https://example.com/a?b=1', 'https://www.abc.vn'])  # www được thêm https://

    def test_link_trong_tin_bam_duoc(self):  # thẻ <a> mở tab mới
        services.gui_tin_nhan(self.cuoc, self.khach, 'xem https://example.com/a?b=1&c=2 nhe')  # tin có link
        r = self.mo_trang()  # mở trang
        self.assertContains(r, 'href="https://example.com/a?b=1&amp;c=2"')  # href đã escape
        self.assertContains(r, 'target="_blank"')  # mở tab mới
        self.assertContains(r, 'rel="noopener noreferrer nofollow"')  # an toàn

    def test_khong_tao_link_nguy_hiem(self):  # javascript: và thẻ HTML không thành link
        services.gui_tin_nhan(self.cuoc, self.khach, 'javascript:alert(1) <script>alert(2)</script>')  # chữ nguy hiểm
        r = self.mo_trang()  # mở trang
        self.assertNotContains(r, 'href="javascript')  # không có link javascript
        self.assertNotContains(r, '<script>alert(2)')  # thẻ script bị escape

    def test_cot_phai_co_muc_lien_ket(self):  # link hiện ở cột phải, mỗi link một lần
        services.gui_tin_nhan(self.cuoc, self.khach, 'a https://example.com/x')  # link lần 1
        services.gui_tin_nhan(self.cuoc, self.khach, 'b https://example.com/x')  # cùng link lần 2
        r = self.mo_trang()  # mở trang
        self.assertContains(r, 'chat-lien-ket__muc', count=1)  # chỉ một dòng trong danh sách

    def test_tin_thu_hoi_khong_con_link_o_cot_phai(self):  # thu hồi thì link biến mất
        tin = services.gui_tin_nhan(self.cuoc, self.khach, 'c https://example.com/bi-thu-hoi')  # tin có link
        services.thu_hoi_tin(self.cuoc, self.khach, tin.pk)  # thu hồi
        r = self.mo_trang()  # mở trang
        self.assertNotContains(r, 'bi-thu-hoi')  # không còn lộ link
        self.assertContains(r, 'Chưa có liên kết nào')  # hiện câu rỗng

    def test_polling_tra_link_cua_tin_moi(self):  # chat.js nhận link để thêm vào cột phải
        tin = services.gui_tin_nhan(self.cuoc, self.khach, 'd https://example.com/moi')  # tin có link
        self.client.force_login(self.khach)  # đăng nhập
        r = self.client.get(reverse('tin_nhan_moi', args=[self.cuoc.pk]), {'sau': tin.pk - 1}, **AJAX)  # lấy tin mới hơn mã trước đó
        du_lieu = r.json()  # JSON
        tin_json = [t for t in du_lieu['tin_nhan'] if t['id'] == tin.pk][0]  # tin vừa gửi
        self.assertEqual(tin_json['lk'][0]['url'], 'https://example.com/moi')  # có link
