# search/test_tro_ly.py - E4: form 5 bước và trang kết quả của Trợ lý. Chạy: python manage.py test search.test_tro_ly
# Dùng lại hàm tạo dữ liệu của Khoa (GoiYTestCase trong test_goi_y.py): tao_nag, tao_slot, cau...
from datetime import timedelta  # cộng trừ ngày để thử biên hôm nay + 29 / + 30

from django.contrib.auth.models import Group  # nhóm quyền: Khách hàng phải thuộc nhóm mới vào được Trợ lý
from django.urls import reverse  # đổi tên URL thành đường dẫn
from django.utils import timezone  # ngày hôm nay theo múi giờ dự án

from accounts.permissions import url_trang_chu  # trang tổng quan: đích của nút "Bỏ qua"
from core.constants import VaiTro  # tên vai trò
from schedule.models import LichKhaDung  # khung giờ, để kiểm tra nút chọn giờ
from search.test_goi_y import GoiYTestCase  # lớp nền của Khoa (không có test riêng nên import không chạy lại test cũ)

KHOA = 'tro_ly_tra_loi'  # khóa session, đúng như E1


class TroLyTestCase(GoiYTestCase):  # lớp nền cho các test của E4
    def setUp(self):  # chạy trước mỗi test
        super().setUp()  # tạo loại hình, khu vực, phong cách, self.khach, self.ngay (hôm nay + 5)
        nhom_khach, _ = Group.objects.get_or_create(name=VaiTro.KHACH_HANG)  # nhóm Khách hàng
        self.khach.groups.add(nhom_khach)  # self.khach của Khoa chưa có nhóm nên thêm vào
        self.client.force_login(self.khach)  # đăng nhập sẵn bằng Khách hàng (không cần băm mật khẩu)
        self.url = reverse('assistant')  # /tro-ly/
        self.url_kq = reverse('assistant_result')  # /tro-ly/ket-qua/

    def dat_session(self, **sua):  # ghi sẵn đủ 5 câu trả lời vào session; sua = các câu muốn đổi
        tra_loi = {  # dạng lưu trong session (JSON): số, chuỗi, danh sách
            'loai_hinh': self.cuoi.pk, 'khu_vuc': self.hcm.pk, 'ngan_sach': '',  # '' = không giới hạn
            'ngay_chup': self.ngay.isoformat(), 'phong_cach': [],  # ngày dạng chuỗi
        }  # hết dict
        tra_loi.update(sua)  # đổi các câu theo yêu cầu của test
        phien = self.client.session  # lấy session của client test
        phien[KHOA] = tra_loi  # ghi vào session
        phien.save()  # lưu lại

    def buoc(self, so, **du_lieu):  # gửi POST cho một bước
        return self.client.post(f'{self.url}?buoc={so}', du_lieu)  # trả về phản hồi


# =====================================================================
# Quyền truy cập
# =====================================================================
class QuyenTest(TroLyTestCase):
    def test_chua_dang_nhap_bi_chuyen_ve_login(self):  # người lạ không vào được
        self.client.logout()  # đăng xuất
        for url in (self.url, self.url_kq):  # cả hai trang
            r = self.client.get(url)  # mở trang
            self.assertEqual(r.status_code, 302)  # bị chuyển trang
            self.assertIn(reverse('login'), r.url)  # về trang đăng nhập

    def test_nhiep_anh_gia_bi_403(self):  # sai vai trò
        nag = self.tao_nag()  # tạo một Nhiếp ảnh gia
        self.client.force_login(nag.MaTaiKhoan)  # đăng nhập bằng tài khoản đó
        for url in (self.url, self.url_kq):  # cả hai trang
            self.assertEqual(self.client.get(url).status_code, 403)  # bị từ chối


# =====================================================================
# Form 5 bước
# =====================================================================
class FormBuocTest(TroLyTestCase):
    def test_buoc_1_hien_cau_hoi_va_dap_an_tu_danh_muc(self):
        r = self.client.get(self.url)  # mở bước 1
        self.assertEqual(r.status_code, 200)  # vào được
        self.assertContains(r, 'Câu 1/5')  # hiện tiến độ
        self.assertContains(r, 'Bạn muốn chụp loại hình nào?')  # hiện câu hỏi
        self.assertContains(r, 'Cưới')  # đáp án lấy từ danh mục Loại hình
        self.assertContains(r, 'Chân dung')  # đáp án thứ hai
        self.assertContains(r, url_trang_chu(self.khach))  # nút "Bỏ qua Trợ lý" về trang tổng quan

    def test_buoc_sai_hoac_qua_lon_thi_ve_buoc_dau_con_thieu(self):
        self.assertEqual(self.client.get(f'{self.url}?buoc=abc').status_code, 200)  # chữ bất kỳ -> coi như bước 1
        r = self.client.get(f'{self.url}?buoc=99')  # số quá lớn
        self.assertRedirects(r, f'{self.url}?buoc=1')  # chưa trả lời gì nên bị đưa về bước 1

    def test_khong_nhay_coc_qua_cau_chua_tra_loi(self):
        r = self.client.get(f'{self.url}?buoc=3')  # mở thẳng câu 3
        self.assertRedirects(r, f'{self.url}?buoc=1')  # bị đưa về câu 1

    def test_luu_cau_1_vao_session_dang_so(self):
        r = self.buoc(1, dap_an=self.cuoi.pk)  # chọn Cưới
        self.assertRedirects(r, f'{self.url}?buoc=2')  # sang câu 2
        self.assertEqual(self.client.session[KHOA]['loai_hinh'], self.cuoi.pk)  # lưu mã dạng số

    def test_bo_trong_thi_bao_loi_va_khong_luu(self):
        r = self.buoc(1)  # không chọn gì
        self.assertEqual(r.status_code, 200)  # ở lại trang
        self.assertContains(r, 'Vui lòng chọn một loại hình chụp.')  # báo lỗi
        self.assertNotIn(KHOA, self.client.session)  # chưa lưu gì

    def test_gia_tri_la_bi_tu_choi(self):
        r = self.buoc(1, dap_an=9999)  # mã loại hình không có
        self.assertContains(r, 'Loại hình chụp không hợp lệ.')  # báo lỗi

    def test_cau_3_cac_muc_ngan_sach(self):
        for gia_tri, luu in (('2000000', '2000000'), ('3000000', '3000000'), ('5000000', '5000000'), ('khong', '')):  # 4 mức
            with self.subTest(gia_tri=gia_tri):  # báo riêng từng mức
                self.dat_session()  # có sẵn câu 1 và 2
                r = self.buoc(3, dap_an=gia_tri)  # chọn mức
                self.assertRedirects(r, f'{self.url}?buoc=4')  # sang câu 4
                self.assertEqual(self.client.session[KHOA]['ngan_sach'], luu)  # "Không giới hạn" lưu thành chuỗi rỗng

    def test_cau_3_muc_la_bi_tu_choi(self):
        self.dat_session()  # có sẵn câu 1 và 2
        r = self.buoc(3, dap_an='1000')  # mức không có trong danh sách
        self.assertContains(r, 'Mức ngân sách không hợp lệ.')  # báo lỗi

    def test_cau_4_ngay_bien_hom_nay_29_duoc_30_bi_tu_choi(self):
        hom_nay = timezone.localdate()  # hôm nay
        self.dat_session()  # có sẵn các câu trước
        r = self.buoc(4, dap_an=(hom_nay + timedelta(days=29)).isoformat())  # hôm nay + 29
        self.assertRedirects(r, f'{self.url}?buoc=5')  # được
        self.assertEqual(self.client.session[KHOA]['ngay_chup'], (hom_nay + timedelta(days=29)).isoformat())  # lưu dạng chuỗi
        for sai in (hom_nay + timedelta(days=30), hom_nay - timedelta(days=1)):  # ngày thứ 31 và quá khứ
            with self.subTest(ngay=sai):  # báo riêng từng ngày
                r = self.buoc(4, dap_an=sai.isoformat())  # gửi ngày sai
                self.assertEqual(r.status_code, 200)  # ở lại trang
                self.assertContains(r, 'Chỉ chọn được ngày từ hôm nay đến')  # báo lỗi
        self.assertEqual(self.client.session[KHOA]['ngay_chup'], (hom_nay + timedelta(days=29)).isoformat())  # ngày sai không ghi đè

    def test_cau_4_ngay_khong_hop_le(self):
        self.dat_session()  # có sẵn các câu trước
        self.assertContains(self.buoc(4, dap_an='khong-phai-ngay'), 'Ngày chụp không hợp lệ.')  # chữ bất kỳ
        self.assertContains(self.buoc(4), 'Vui lòng chọn ngày chụp.')  # bỏ trống

    def test_cau_4_o_ngay_co_min_max(self):
        self.dat_session()  # có sẵn các câu trước
        r = self.client.get(f'{self.url}?buoc=4')  # mở câu 4
        self.assertContains(r, f'min="{timezone.localdate().isoformat()}"')  # trình duyệt chặn quá khứ
        self.assertContains(r, f'max="{(timezone.localdate() + timedelta(days=29)).isoformat()}"')  # và chặn quá hôm nay + 29

    def test_cau_5_chon_hai_phong_cach(self):
        self.dat_session()  # có sẵn các câu trước
        r = self.buoc(5, dap_an=[self.s1.pk, self.s2.pk])  # chọn 2 phong cách
        self.assertRedirects(r, self.url_kq)  # sang trang kết quả
        self.assertEqual(self.client.session[KHOA]['phong_cach'], [self.s1.pk, self.s2.pk])  # lưu danh sách số

    def test_cau_5_chon_qua_3_bi_tu_choi(self):
        self.dat_session()  # có sẵn các câu trước
        r = self.buoc(5, dap_an=[self.s1.pk, self.s2.pk, self.s3.pk, self.s4.pk])  # 4 phong cách
        self.assertContains(r, 'Chỉ được chọn tối đa 3 phong cách.')  # báo lỗi (số 3 lấy từ hằng của Khoa)

    def test_cau_5_bo_qua_luu_danh_sach_rong_ke_ca_khi_da_tich(self):
        self.dat_session(phong_cach=[self.s1.pk])  # đang có đáp án cũ
        r = self.buoc(5, bo_qua='1', dap_an=[self.s2.pk])  # bấm "Chưa rõ, bỏ qua"
        self.assertRedirects(r, self.url_kq)  # sang kết quả
        self.assertEqual(self.client.session[KHOA]['phong_cach'], [])  # bỏ qua = rỗng

    def test_quay_lai_sua_thi_dien_san_dap_an_cu(self):
        self.dat_session(loai_hinh=self.chan_dung.pk)  # đã chọn Chân dung
        r = self.client.get(self.url)  # quay lại câu 1
        self.assertRegex(r.content.decode(), rf'value="{self.chan_dung.pk}"[^>]*\bchecked\b')  # đáp án cũ được tích sẵn (không phụ thuộc thứ tự thuộc tính)
    def test_di_het_5_buoc_tu_session_trong_den_ket_qua(self):
        self.tao_nag()  # có một Nhiếp ảnh gia phù hợp
        self.assertRedirects(self.buoc(1, dap_an=self.cuoi.pk), f'{self.url}?buoc=2')  # câu 1
        self.assertRedirects(self.buoc(2, dap_an=self.hcm.pk), f'{self.url}?buoc=3')  # câu 2
        self.assertRedirects(self.buoc(3, dap_an='khong'), f'{self.url}?buoc=4')  # câu 3
        self.assertRedirects(self.buoc(4, dap_an=self.ngay.isoformat()), f'{self.url}?buoc=5')  # câu 4
        r = self.buoc(5, bo_qua='1')  # câu 5: bỏ qua
        self.assertRedirects(r, self.url_kq)  # sang kết quả
        self.assertContains(self.client.get(self.url_kq), 'Phù hợp 88%')  # tổng 80: 30+20+20=70 -> 87,5 -> 88


# =====================================================================
# Trang kết quả
# =====================================================================
class KetQuaTest(TroLyTestCase):
    def test_chua_tra_loi_thi_ve_cau_dau(self):
        self.assertRedirects(self.client.get(self.url_kq), f'{self.url}?buoc=1')  # chưa có gì trong session

    def test_session_thieu_cau_thi_ve_dung_cau_thieu(self):
        self.dat_session()  # đủ 5 câu
        phien = self.client.session  # lấy session
        du_lieu = dict(phien[KHOA])  # sao chép
        del du_lieu['ngan_sach']  # xóa câu 3
        phien[KHOA] = du_lieu  # ghi lại
        phien.save()  # lưu
        self.assertRedirects(self.client.get(self.url_kq), f'{self.url}?buoc=3')  # bị đưa về câu 3

    def test_session_hong_thi_hoi_lai(self):
        self.dat_session(ngay_chup='abc')  # chuỗi ngày hỏng
        self.assertRedirects(self.client.get(self.url_kq), f'{self.url}?buoc=1')  # hỏi lại từ đầu, không báo lỗi 500

    def test_ngay_da_luu_nay_thanh_qua_khu_thi_hoi_lai_cau_4(self):
        self.dat_session(ngay_chup=(timezone.localdate() - timedelta(days=1)).isoformat())  # ngày hôm qua
        r = self.client.get(self.url_kq, follow=True)  # đi theo chuyển hướng
        self.assertEqual(r.redirect_chain[-1][0], f'{self.url}?buoc=4')  # về câu 4
        self.assertContains(r, 'Ngày chụp bạn đã chọn không còn hợp lệ.')  # có giải thích

    def test_hien_the_day_du(self):
        self.tao_nag(danh_gia=[5, 4, 5])  # tb 4,667 -> tổng 80: (30+20+20+9,33)/80 = 99,17 -> 99
        self.dat_session()  # trả lời mặc định (Cưới, TP.HCM, không giới hạn, bỏ qua phong cách)
        r = self.client.get(self.url_kq)  # mở kết quả
        self.assertContains(r, 'Phù hợp 99%')  # phần trăm
        self.assertContains(r, 'B A')  # tên hiển thị theo get_full_name() của dự án (họ đứng trước)
        self.assertContains(r, '2.000.000đ')  # giá gói rẻ nhất
        self.assertContains(r, 'Chụp Cưới')  # chip lý do
        self.assertContains(r, '09:00–12:00')  # khung giờ trống 9h-12h (nút chọn giờ)
        self.assertNotContains(r, '4.6666')  # diem_tb phải qua floatformat, không hiện float thô
        self.assertContains(r, '(3 đánh giá)')  # số lượt đánh giá

    def test_nut_chon_gio_post_toi_chon_slot_kem_ma_nhiep_anh_gia(self):
        nag = self.tao_nag()  # có sẵn một khung giờ 9h-12h
        lich = LichKhaDung.objects.get(MaNhiepAnhGia=nag)  # khung giờ đó
        self.dat_session()  # trả lời mặc định
        r = self.client.get(self.url_kq)  # mở kết quả
        self.assertContains(r, f'action="{reverse("chon_slot", args=[lich.pk])}"')  # form POST tới chon_slot
        self.assertContains(r, f'name="ma_nhiep_anh_gia" value="{nag.pk}"')  # kèm mã Nhiếp ảnh gia
        self.assertContains(r, 'csrfmiddlewaretoken')  # có mã chống giả mạo

    def test_chua_co_danh_gia_hien_dong_rieng_va_khong_lap_chip(self):
        self.tao_nag(cach=[self.s1, self.s2, self.s3])  # chưa có đánh giá, khớp cả 3 phong cách (chip dễ bị cắt vì tối đa 3 chip)
        self.dat_session(phong_cach=[self.s1.pk, self.s2.pk, self.s3.pk])  # khách chọn 3 phong cách
        r = self.client.get(self.url_kq)  # mở kết quả
        self.assertContains(r, 'Chưa có đánh giá', count=1)  # đúng một dòng riêng trong thẻ, không lặp
        for the in r.context['cac_the']:  # mọi thẻ
            self.assertNotIn('Chưa có đánh giá', the['ly_do'])  # chip này đã bị bỏ để khỏi trùng

    def test_khong_gioi_han_thi_khong_co_chip_ngan_sach(self):
        self.tao_nag(goi=[(self.cuoi, 99000000, 60)])  # gói rất đắt
        self.dat_session()  # không giới hạn
        r = self.client.get(self.url_kq)  # mở kết quả
        self.assertEqual(r.status_code, 200)  # vẫn hiện bình thường
        self.assertNotContains(r, 'trong ngân sách')  # không có chip ngân sách

    def test_ket_qua_rong_hien_man_hinh_va_goi_y(self):
        self.dat_session()  # không có Nhiếp ảnh gia nào
        r = self.client.get(self.url_kq)  # mở kết quả
        self.assertEqual(r.status_code, 200)  # vẫn là trang bình thường
        self.assertContains(r, 'Chưa có ai phù hợp')  # màn hình rỗng
        self.assertContains(r, 'Thử chọn ngày khác')  # câu từ goi_y_noi_tieu_chi
        self.assertContains(r, 'Sửa câu trả lời')  # có đường quay lại

    def test_tom_tat_5_dap_an(self):
        self.dat_session(ngan_sach='3000000', phong_cach=[self.s1.pk])  # chọn dưới 3 triệu và 1 phong cách
        r = self.client.get(self.url_kq)  # mở kết quả
        self.assertContains(r, 'Dưới 3 triệu')  # ngân sách hiện theo chữ của mức
        self.assertContains(r, 'Tự nhiên')  # tên phong cách
        self.assertContains(r, self.ngay.strftime('%d/%m/%Y'))  # ngày chụp

    def test_toi_da_5_the(self):
        for _ in range(7):  # 7 người cùng phù hợp
            self.tao_nag()  # tạo từng người
        self.dat_session()  # trả lời mặc định
        self.assertEqual(len(self.client.get(self.url_kq).context['cac_the']), 5)  # chỉ hiện 5


# =====================================================================
# Nút ở trang Tìm kiếm (E5)
# =====================================================================
class NutTimKiemTest(TroLyTestCase):
    def test_khach_hang_thay_nut(self):
        r = self.client.get(reverse('search'))  # mở trang Tìm kiếm bằng Khách hàng
        self.assertContains(r, 'Trợ lý chọn Nhiếp ảnh gia')  # có nút
        self.assertContains(r, reverse('assistant'))  # trỏ tới Trợ lý

    def test_khach_chua_dang_nhap_thay_khoi_va_duoc_dan_toi_dang_nhap(self):
        self.client.logout()  # đăng xuất
        r = self.client.get(reverse('search'))  # mở trang Tìm kiếm khi chưa đăng nhập
        self.assertContains(r, 'Trợ lý chọn Nhiếp ảnh gia')  # vẫn thấy khối gợi ý (E5)
        self.assertContains(r, 'Bạn cần đăng nhập để dùng')  # kèm dòng nhắc đăng nhập
        self.assertContains(r, f"{reverse('login')}?next={reverse('assistant')}")  # nút dẫn sang đăng nhập, xong quay lại Trợ lý

    def test_nhiep_anh_gia_khong_thay_nut(self):
        nag = self.tao_nag()  # tạo Nhiếp ảnh gia
        self.client.force_login(nag.MaTaiKhoan)  # đăng nhập bằng họ
        self.assertNotContains(self.client.get(reverse('search')), 'Trợ lý chọn Nhiếp ảnh gia')  # không có nút (tránh bấm rồi bị 403)