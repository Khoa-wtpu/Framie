# chat/test_nang_cap.py - bước 8 của nâng cấp chat. Test MỚI, không sửa tests.py và test_trao_doi.py. Chạy: python manage.py test chat
import shutil  # xóa thư mục ảnh tạm sau mỗi test
import tempfile  # tạo thư mục ảnh tạm, không đụng private_media thật
from datetime import datetime, timedelta  # dựng mốc thời gian
from io import BytesIO, StringIO  # ảnh giả trong bộ nhớ; hứng chữ in ra của lệnh don_anh_chat
from types import SimpleNamespace  # dựng đối tượng giả có ThoiGianGui cho nhom_anh_theo_thang
from unittest import mock  # ép giới hạn nhỏ lại để thử trường hợp "quá xa"

from django.core.exceptions import ValidationError  # lỗi dữ liệu của services.gui_tin_nhan
from django.core.files.uploadedfile import SimpleUploadedFile  # file tải lên giả
from django.core.management import call_command  # chạy lệnh manage.py trong test
from django.test import TestCase, override_settings  # lớp test; đổi PRIVATE_MEDIA_ROOT sang thư mục tạm
from django.urls import reverse  # đổi name thành đường dẫn
from django.utils import timezone  # giờ hiện tại có múi giờ
from PIL import Image  # tạo ảnh thật để Pillow kiểm tra

from chat import services  # hàm nghiệp vụ
from chat.models import CuocTroChuyen, DinhKemTinNhan, ThamGia, TinNhan  # bảng của Module 8
from chat.test_trao_doi import AJAX, CoSoTest, _tao_nag, _tao_user  # dùng lại cách dựng dữ liệu của test cũ
from core.constants import VaiTro  # tên vai trò

BI_MAT = 'bimat-zzz'  # chữ ASCII để kiểm "không lộ nội dung" (JSON mã hóa chữ có dấu nên dùng chữ không dấu cho chắc)


def _tao_anh(ten='a.jpg', dinh_dang='JPEG'):  # tạo một file ảnh thật, nhỏ, trong bộ nhớ
    bo_nho = BytesIO()  # chỗ chứa
    Image.new('RGB', (40, 30), 'red').save(bo_nho, dinh_dang)  # vẽ ảnh đỏ 40x30 rồi lưu
    return SimpleUploadedFile(ten, bo_nho.getvalue(), content_type='image/' + dinh_dang.lower())  # giống file trình duyệt gửi lên


def _json(r):  # đọc JSON trả về
    return r.json()  # Django test client có sẵn


# ---------------------------------------------------------------------------------------------
# Bỏ dấu và tìm trong cuộc trò chuyện (bước 7)
# ---------------------------------------------------------------------------------------------
class BoDauTests(TestCase):  # hàm bo_dau
    def test_bo_dau_tieng_viet(self):  # chữ có dấu thành chữ thường không dấu
        self.assertEqual(services.bo_dau('Phạnh'), 'phanh')  # ví dụ trong yêu cầu
        self.assertEqual(services.bo_dau('Đường Nguyễn'), 'duong nguyen')  # đ và ễ

    def test_giu_nguyen_do_dai(self):  # để vị trí khớp trên bản không dấu đúng với bản gốc
        goc = 'Chụp ẢNH đẹp, giá 500k!'  # chuỗi bất kỳ
        self.assertEqual(len(services.bo_dau(goc)), len(goc))  # cùng độ dài


class TimTrongCuocTests(CoSoTest):  # tìm trong cuộc trò chuyện
    def goi(self, q, user=None):  # gọi view tìm, mặc định bằng Khách hàng
        self.client.force_login(user or self.khach)  # đăng nhập
        return self.client.get(reverse('tim_trong_cuoc', args=[self.cuoc.pk]), {'q': q})  # GET ?q=

    def test_tim_khong_phan_biet_hoa_thuong_va_dau(self):  # "phanh" ra "Phạnh"
        t = self.tin(self.nag.MaTaiKhoan, 'Anh Phạnh sẽ chụp ở Đà Lạt')  # tin có dấu
        for tu in ('phanh', 'PHẠNH', 'phạnh', 'da lat', 'ĐÀ LẠT'):  # nhiều cách gõ
            kq = _json(self.goi(tu))['ket_qua']  # kết quả
            self.assertEqual([k['id'] for k in kq], [t.pk], tu)  # đều ra đúng tin đó

    def test_ket_qua_moi_nhat_truoc_va_co_co_cua_toi(self):  # thứ tự và cờ "Bạn:"
        a = self.tin(self.khach, 'phanh dau')  # tin cũ, của khách
        b = self.tin(self.nag.MaTaiKhoan, 'phanh sau')  # tin mới, của nhiếp ảnh gia
        kq = _json(self.goi('phanh'))['ket_qua']  # khách tìm
        self.assertEqual([k['id'] for k in kq], [b.pk, a.pk])  # mới nhất trước
        self.assertEqual([k['cua_toi'] for k in kq], [False, True])  # tin của khách ghi là của mình

    def test_khong_tim_ra_tin_da_thu_hoi(self):  # tin thu hồi không lộ qua tìm kiếm
        t = self.tin(self.nag.MaTaiKhoan, BI_MAT + ' phanh')  # tin sẽ thu hồi
        services.thu_hoi_tin(self.cuoc, self.nag.MaTaiKhoan, t.pk)  # người gửi thu hồi
        r = self.goi('phanh')  # khách tìm
        self.assertEqual(_json(r)['ket_qua'], [])  # không ra gì
        self.assertNotContains(r, BI_MAT)  # nội dung không có trong phản hồi

    def test_khong_tim_phan_da_xoa_phia_minh(self):  # phần đã xóa phía mình không tìm ra, người kia vẫn tìm ra
        self.tin(self.nag.MaTaiKhoan, 'phanh cu')  # tin trước khi xóa
        services.xoa_cuoc_phia_minh(self.cuoc, self.khach)  # khách xóa phía mình
        moi = self.tin(self.nag.MaTaiKhoan, 'phanh moi')  # tin sau khi xóa
        self.assertEqual([k['id'] for k in _json(self.goi('phanh'))['ket_qua']], [moi.pk])  # khách chỉ thấy tin mới
        self.assertEqual(len(_json(self.goi('phanh', self.nag.MaTaiKhoan))['ket_qua']), 2)  # nhiếp ảnh gia vẫn thấy cả hai

    def test_tin_chi_co_anh_khong_duoc_tim(self):  # tin không có chữ không có gì để tìm
        TinNhan.objects.create(MaCuocTroChuyen=self.cuoc, MaNguoiGui=self.khach, NoiDung='')  # tin rỗng chữ
        self.assertEqual(_json(self.goi('a'))['ket_qua'], [])  # không ra

    def test_tu_khoa_rong(self):  # chỉ có khoảng trắng
        self.tin(self.khach, 'xin chao')  # có tin
        d = _json(self.goi('   '))  # tìm khoảng trắng
        self.assertTrue(d['ok'])  # vẫn thành công
        self.assertEqual(d['ket_qua'], [])  # nhưng không có kết quả

    def test_toi_da_100_ket_qua(self):  # nhiều hơn 100 thì cắt và báo
        TinNhan.objects.bulk_create([TinNhan(MaCuocTroChuyen=self.cuoc, MaNguoiGui=self.khach, NoiDung='phanh %d' % i) for i in range(101)])  # 101 tin khớp
        d = _json(self.goi('phanh'))  # tìm
        self.assertEqual(len(d['ket_qua']), services.TOI_DA_KET_QUA_TIM)  # đúng 100
        self.assertTrue(d['bi_cat'])  # báo còn nữa
        ma = [k['id'] for k in d['ket_qua']]  # danh sách mã
        self.assertEqual(ma, sorted(ma, reverse=True))  # mới nhất trước

    def test_nguoi_ngoai_cuoc_bi_404(self):  # người không thuộc cuộc không tìm được
        self.tin(self.khach, 'phanh')  # có tin
        la = _tao_user('khach_la', VaiTro.KHACH_HANG)  # khách khác
        self.assertEqual(self.goi('phanh', la).status_code, 404)  # khách lạ
        nag_la = _tao_nag('nag_la')  # nhiếp ảnh gia khác
        self.assertEqual(self.goi('phanh', nag_la.MaTaiKhoan).status_code, 404)  # nhiếp ảnh gia lạ

    def test_chua_dang_nhap_401(self):  # hết phiên: chat.js báo hết phiên
        r = self.client.get(reverse('tim_trong_cuoc', args=[self.cuoc.pk]), {'q': 'a'})  # chưa đăng nhập
        self.assertEqual(r.status_code, 401)  # 401 JSON

    def test_chi_nhan_get(self):  # POST bị chặn
        self.client.force_login(self.khach)  # đăng nhập
        r = self.client.post(reverse('tim_trong_cuoc', args=[self.cuoc.pk]), {'q': 'a'})  # POST
        self.assertEqual(r.status_code, 405)  # không cho phép


# ---------------------------------------------------------------------------------------------
# Nhảy tới tin cũ (bước 7)
# ---------------------------------------------------------------------------------------------
class NhayToiTinTests(CoSoTest):  # view tin_nhan_den_tin
    def setUp(self):  # 40 tin của khách
        super().setUp()
        self.ma = [self.tin(self.khach, 'tin %d' % i).pk for i in range(40)]  # mã tin từ cũ đến mới

    def goi(self, user=None, **tham_so):  # gọi view, mặc định bằng Khách hàng
        self.client.force_login(user or self.khach)  # đăng nhập
        return self.client.get(reverse('tin_nhan_den_tin', args=[self.cuoc.pk]), tham_so)  # GET

    def test_tai_doan_lien_mach_tu_truoc_tin_can_toi(self):  # tải từ 10 tin trước tin cần tới đến trước tin đầu đang hiện
        r = self.goi(tin=self.ma[25], truoc=self.ma[35])  # cần tới tin 25, đang hiện từ tin 35
        d = _json(r)  # JSON
        self.assertTrue(d['ok'])  # thành công
        self.assertEqual([t['id'] for t in d['tin_nhan']], self.ma[15:35])  # tin 15..34, cũ trước mới sau
        self.assertTrue(d['con_cu'])  # còn tin cũ hơn nữa

    def test_het_tin_cu(self):  # nhảy tới tin gần đầu cuộc thì không còn tin cũ
        d = _json(self.goi(tin=self.ma[5], truoc=self.ma[20]))  # tin 5
        self.assertEqual([t['id'] for t in d['tin_nhan']], self.ma[0:20])  # tải từ tin đầu tiên
        self.assertFalse(d['con_cu'])  # hết tin cũ

    def test_tham_so_sai_bi_400(self):  # thiếu, không phải số, hoặc tin đã nằm trong phần đang hiện
        self.assertEqual(self.goi().status_code, 400)  # thiếu cả hai
        self.assertEqual(self.goi(tin='abc', truoc=self.ma[20]).status_code, 400)  # không phải số
        self.assertEqual(self.goi(tin=self.ma[20], truoc=self.ma[10]).status_code, 400)  # tin mới hơn tin đầu đang hiện
        self.assertEqual(self.goi(tin=self.ma[20], truoc=self.ma[20]).status_code, 400)  # bằng nhau

    def test_qua_xa_bi_422(self):  # quá giới hạn thì yêu cầu kéo lên tải dần
        with mock.patch.object(services, 'TOI_DA_TIN_NHAY', 3):  # ép giới hạn còn 3 tin
            r = self.goi(tin=self.ma[5], truoc=self.ma[30])  # đoạn dài hơn 3 tin
        self.assertEqual(r.status_code, 422)  # báo quá xa
        self.assertFalse(_json(r)['ok'])  # không ok

    def test_khong_tai_phan_da_xoa_phia_minh(self):  # tin đã xóa phía mình không quay lại
        services.lay_tham_gia(self.cuoc, self.khach)  # bảo đảm có hàng THAMGIA
        ThamGia.objects.filter(MaCuocTroChuyen=self.cuoc, MaNguoiDung=self.khach).update(XoaDenMaTin=self.ma[9])  # xóa tới tin 9
        d = _json(self.goi(tin=self.ma[15], truoc=self.ma[25]))  # nhảy tới tin 15
        ids = [t['id'] for t in d['tin_nhan']]  # các tin tải về
        self.assertTrue(ids and all(i > self.ma[9] for i in ids))  # không có tin đã xóa
        self.assertFalse(d['con_cu'])  # phần cũ hơn đã xóa nên không còn gì

    def test_tin_thu_hoi_khong_lo_noi_dung(self):  # tin thu hồi nằm trong đoạn tải về vẫn không lộ chữ
        t = self.tin(self.nag.MaTaiKhoan, BI_MAT)  # tin sẽ thu hồi
        services.thu_hoi_tin(self.cuoc, self.nag.MaTaiKhoan, t.pk)  # thu hồi
        moi = self.tin(self.khach, 'tin sau')  # một tin sau đó
        r = self.goi(tin=t.pk, truoc=moi.pk)  # tải đoạn chứa tin thu hồi
        self.assertIn(t.pk, [x['id'] for x in _json(r)['tin_nhan']])  # tin thu hồi có trong danh sách (dưới dạng câu thay thế)
        self.assertNotContains(r, BI_MAT)  # nhưng nội dung thì không

    def test_nguoi_ngoai_cuoc_bi_404(self):  # người ngoài không tải được
        la = _tao_user('khach_la2', VaiTro.KHACH_HANG)  # khách khác
        self.assertEqual(self.goi(la, tin=self.ma[5], truoc=self.ma[20]).status_code, 404)  # 404

    def test_chua_dang_nhap_401(self):  # hết phiên
        r = self.client.get(reverse('tin_nhan_den_tin', args=[self.cuoc.pk]), {'tin': self.ma[5], 'truoc': self.ma[20]})  # chưa đăng nhập
        self.assertEqual(r.status_code, 401)  # 401


# ---------------------------------------------------------------------------------------------
# Ảnh trong chat: gửi, xem, hết hạn 6 tháng, dọn file (bước 5, 7b)
# ---------------------------------------------------------------------------------------------
class CoSoAnh(CoSoTest):  # lớp cha: dùng thư mục ảnh tạm thay cho private_media thật
    def setUp(self):  # chạy trước mỗi test
        super().setUp()
        self.thu_muc = tempfile.mkdtemp()  # thư mục tạm
        self.addCleanup(shutil.rmtree, self.thu_muc, ignore_errors=True)  # xóa sau test
        ghi_de = override_settings(PRIVATE_MEDIA_ROOT=self.thu_muc)  # kho_anh_chat() đọc biến này mỗi lần gọi
        ghi_de.enable()  # bật
        self.addCleanup(ghi_de.disable)  # tắt sau test

    def tin_anh(self, nguoi=None, noi_dung='', so_ngay=0):  # tạo tin có 1 ảnh; so_ngay > 0 thì lùi giờ gửi về quá khứ
        tin = services.gui_tin_nhan(self.cuoc, nguoi or self.khach, noi_dung, ds_anh=[_tao_anh()])  # lưu thật qua services
        if so_ngay:  # lùi giờ gửi (ThoiGianGui là auto_now_add nên phải dùng update)
            TinNhan.objects.filter(pk=tin.pk).update(ThoiGianGui=timezone.now() - timedelta(days=so_ngay))  # sửa giờ
            tin.refresh_from_db()  # nạp lại
        return tin  # trả về tin

    def xem(self, dinh_kem, user=None, nho=False):  # gọi view xem ảnh
        self.client.force_login(user or self.khach)  # đăng nhập
        r = self.client.get(reverse('xem_anh_chat', args=[dinh_kem.pk]) + ('?nho=1' if nho else ''))  # GET
        if getattr(r, 'streaming', False):  # ảnh đầy đủ trả theo luồng
            b''.join(r.streaming_content)  # đọc hết rồi
            r.close()  # đóng file để Windows xóa được thư mục tạm
        return r  # trả về phản hồi


class GuiAnhTests(CoSoAnh):  # gửi ảnh qua view
    def gui(self, ds_anh, noi_dung=''):  # POST như chat.js (gửi ngầm)
        self.client.force_login(self.khach)  # đăng nhập
        return self.client.post(self.url_gui, {'noi_dung': noi_dung, 'anh': ds_anh}, **AJAX)  # multipart

    def test_gui_anh_hop_le(self):  # lưu file với tên ngẫu nhiên, giữ tên gốc trong DB
        r = self.gui([_tao_anh('hinh-goc.jpg')])  # gửi 1 ảnh, không chữ
        self.assertEqual(r.status_code, 200)  # thành công
        dk = DinhKemTinNhan.objects.get()  # đúng một ảnh
        self.assertEqual(dk.TenGoc, 'hinh-goc.jpg')  # tên gốc để hiển thị
        self.assertNotIn('hinh-goc', dk.DuongDanFile)  # tên lưu là mã ngẫu nhiên
        self.assertTrue(services.kho_anh_chat().exists(dk.DuongDanFile))  # file có trong thư mục riêng
        self.assertEqual(dk.MaTinNhan.NoiDung, '')  # tin chỉ có ảnh

    def test_khong_phai_anh_bi_tu_choi(self):  # đuôi .jpg nhưng ruột không phải ảnh
        r = self.gui([SimpleUploadedFile('gia.jpg', b'day khong phai anh', content_type='image/jpeg')])  # file giả
        self.assertEqual(r.status_code, 400)  # từ chối
        self.assertEqual(TinNhan.objects.count(), 0)  # không lưu tin nào

    def test_dinh_dang_gif_bi_tu_choi(self):  # chỉ nhận JPG, PNG, WEBP
        r = self.gui([_tao_anh('a.gif', 'GIF')])  # ảnh GIF thật
        self.assertEqual(r.status_code, 400)  # từ chối
        self.assertEqual(DinhKemTinNhan.objects.count(), 0)  # không lưu ảnh

    def test_qua_5_anh_bi_tu_choi(self):  # tối đa 5 ảnh mỗi tin
        r = self.gui([_tao_anh('a%d.jpg' % i) for i in range(6)])  # 6 ảnh
        self.assertEqual(r.status_code, 400)  # từ chối
        self.assertEqual(TinNhan.objects.count(), 0)  # không lưu gì

    def test_qua_5mb_bi_tu_choi(self):  # mỗi ảnh tối đa 5 MB
        qua_nang = SimpleUploadedFile('to.jpg', b'0' * (services.GIOI_HAN_ANH + 1), content_type='image/jpeg')  # vượt 1 byte
        self.assertEqual(self.gui([qua_nang]).status_code, 400)  # từ chối

    def test_mot_anh_hong_thi_khong_luu_anh_nao(self):  # kiểm tra hết trước khi lưu bất cứ thứ gì
        r = self.gui([_tao_anh('tot.jpg'), SimpleUploadedFile('hong.jpg', b'xxx', content_type='image/jpeg')])  # 1 tốt, 1 hỏng
        self.assertEqual(r.status_code, 400)  # từ chối cả tin
        self.assertEqual(DinhKemTinNhan.objects.count(), 0)  # ảnh tốt cũng không lưu
        self.assertEqual(TinNhan.objects.count(), 0)  # tin cũng không lưu


class XemAnhTests(CoSoAnh):  # quyền xem ảnh và hạn 6 tháng
    def test_xem_duoc_anh_con_han(self):  # ảnh đầy đủ và ảnh nhỏ
        dk = self.tin_anh(so_ngay=10).dinh_kem.get()  # ảnh 10 ngày tuổi
        r = self.xem(dk)  # ảnh đầy đủ
        self.assertEqual(r.status_code, 200)  # xem được
        self.assertEqual(r['Content-Type'], 'image/jpeg')  # đúng loại
        self.assertEqual(r['X-Content-Type-Options'], 'nosniff')  # chống đoán loại tệp
        r = self.xem(dk, nho=True)  # ảnh nhỏ
        self.assertEqual(r.status_code, 200)  # xem được
        self.assertEqual(r['Content-Type'], 'image/jpeg')  # ảnh nhỏ luôn là JPEG

    def test_moc_6_thang(self):  # 182 ngày còn xem, 184 ngày thì 404
        con = self.tin_anh(so_ngay=182).dinh_kem.get()  # còn hạn
        het = self.tin_anh(so_ngay=184).dinh_kem.get()  # hết hạn
        self.assertEqual(self.xem(con).status_code, 200)  # còn xem được
        self.assertEqual(self.xem(het).status_code, 404)  # đã hết hạn
        self.assertEqual(self.xem(het, nho=True).status_code, 404)  # bản nhỏ cũng chặn

    def test_han_luu_anh_la_183_ngay(self):  # mốc so sánh
        lech = abs((timezone.now() - services.han_luu_anh()) - timedelta(days=183))  # chênh so với 183 ngày
        self.assertLess(lech, timedelta(seconds=5))  # gần như bằng nhau

    def test_nguoi_ngoai_cuoc_bi_404(self):  # chỉ hai người trong cuộc xem được
        dk = self.tin_anh().dinh_kem.get()  # ảnh mới
        la = _tao_user('khach_la3', VaiTro.KHACH_HANG)  # khách khác
        self.assertEqual(self.xem(dk, la).status_code, 404)  # 404
        self.assertEqual(self.xem(dk, self.nag.MaTaiKhoan).status_code, 200)  # còn nhiếp ảnh gia thì xem được

    def test_chua_dang_nhap_bi_chuyen_sang_dang_nhap(self):  # không có đường công khai
        dk = self.tin_anh().dinh_kem.get()  # ảnh mới
        r = self.client.get(reverse('xem_anh_chat', args=[dk.pk]))  # chưa đăng nhập
        self.assertEqual(r.status_code, 302)  # sang trang đăng nhập

    def test_anh_cua_tin_thu_hoi_bi_404(self):  # thu hồi tin thì ảnh cũng không xem được, cả với người gửi
        tin = self.tin_anh()  # tin có ảnh
        dk = tin.dinh_kem.get()  # ảnh
        services.thu_hoi_tin(self.cuoc, self.khach, tin.pk)  # thu hồi
        self.assertEqual(self.xem(dk).status_code, 404)  # người gửi cũng 404
        self.assertEqual(self.xem(dk, self.nag.MaTaiKhoan).status_code, 404)  # người nhận 404

    def test_anh_da_xoa_phia_minh_bi_404(self):  # xóa cuộc phía mình thì ảnh cũ biến mất với mình, người kia vẫn xem
        dk = self.tin_anh().dinh_kem.get()  # ảnh
        services.xoa_cuoc_phia_minh(self.cuoc, self.khach)  # khách xóa phía mình
        self.assertEqual(self.xem(dk).status_code, 404)  # khách 404
        self.assertEqual(self.xem(dk, self.nag.MaTaiKhoan).status_code, 200)  # nhiếp ảnh gia vẫn xem


class AnhHetHanHienThiTests(CoSoAnh):  # panel File phương tiện và bong bóng tin
    def test_anh_qua_han_khong_vao_panel(self):  # lay_anh_chia_se bỏ ảnh quá 6 tháng
        self.tin_anh(so_ngay=200)  # ảnh hết hạn
        moi = self.tin_anh(so_ngay=1)  # ảnh còn hạn
        ds = services.lay_anh_chia_se(self.cuoc)  # danh sách cho cột phải
        self.assertEqual([d.pk for d in ds], [moi.dinh_kem.get().pk])  # chỉ còn ảnh mới

    def test_trang_chat_hien_cau_het_han_va_khong_in_link_anh(self):  # bong bóng thay ảnh bằng câu thông báo
        tin = self.tin_anh(so_ngay=200)  # ảnh hết hạn
        dk = tin.dinh_kem.get()  # bản ghi ảnh
        self.client.force_login(self.khach)  # đăng nhập
        r = self.client.get(self.url_trang)  # mở cuộc trò chuyện
        self.assertContains(r, 'Ảnh đã hết hạn lưu trữ')  # câu thay thế
        self.assertNotContains(r, reverse('xem_anh_chat', args=[dk.pk]))  # không còn link ảnh (cả bong bóng lẫn panel)

    def test_tin_chu_van_con_khi_anh_het_han(self):  # chỉ ảnh mất, chữ còn
        self.tin_anh(noi_dung='chu-van-con', so_ngay=200)  # tin có chữ và ảnh hết hạn
        self.client.force_login(self.nag.MaTaiKhoan)  # nhiếp ảnh gia mở
        r = self.client.get(self.url_trang)  # trang chat
        self.assertContains(r, 'chu-van-con')  # chữ vẫn hiện
        self.assertContains(r, 'Ảnh đã hết hạn lưu trữ')  # ảnh báo hết hạn

    def test_anh_con_han_van_hien(self):  # đối chứng: ảnh mới có link ảnh và không có câu hết hạn
        dk = self.tin_anh(so_ngay=5).dinh_kem.get()  # ảnh mới
        self.client.force_login(self.khach)  # đăng nhập
        r = self.client.get(self.url_trang)  # trang chat
        self.assertContains(r, reverse('xem_anh_chat', args=[dk.pk]))  # có link
        self.assertNotContains(r, 'Ảnh đã hết hạn lưu trữ')  # không có câu hết hạn


class DonAnhTests(CoSoAnh):  # lệnh don_anh_chat
    def test_chi_xem_khong_xoa_va_chay_that_chi_xoa_file_qua_han(self):  # --chi-xem rồi chạy thật
        cu = self.tin_anh(so_ngay=200).dinh_kem.get()  # ảnh hết hạn
        moi = self.tin_anh(so_ngay=1).dinh_kem.get()  # ảnh còn hạn
        kho = services.kho_anh_chat()  # thư mục ảnh tạm

        ra = StringIO()  # hứng chữ in ra
        call_command('don_anh_chat', '--chi-xem', stdout=ra)  # chỉ đếm
        self.assertIn('Sẽ xóa 1 ảnh', ra.getvalue())  # báo đúng số lượng
        self.assertTrue(kho.exists(cu.DuongDanFile))  # chưa xóa gì

        ra = StringIO()  # hứng lần chạy thật
        call_command('don_anh_chat', stdout=ra)  # xóa thật
        self.assertIn('Đã xóa 1 ảnh', ra.getvalue())  # báo đã xóa
        self.assertFalse(kho.exists(cu.DuongDanFile))  # file hết hạn đã mất
        self.assertTrue(kho.exists(moi.DuongDanFile))  # file còn hạn còn nguyên
        self.assertTrue(DinhKemTinNhan.objects.filter(pk=cu.pk).exists())  # bản ghi vẫn giữ
        self.assertTrue(TinNhan.objects.filter(pk=cu.MaTinNhan_id).exists())  # tin nhắn vẫn giữ

        ra = StringIO()  # chạy lần hai
        call_command('don_anh_chat', stdout=ra)  # không còn gì để xóa
        self.assertIn('Đã xóa 0 ảnh', ra.getvalue())  # không xóa thêm
        self.assertIn('1 ảnh đã dọn từ trước', ra.getvalue())  # nhận ra ảnh đã dọn


# ---------------------------------------------------------------------------------------------
# File phương tiện theo tháng (bước 7b)
# ---------------------------------------------------------------------------------------------
class NhomAnhTheoThangTests(TestCase):  # hàm nhom_anh_theo_thang
    def _anh(self, nam, thang, ngay):  # đối tượng giả có MaTinNhan.ThoiGianGui
        luc = timezone.make_aware(datetime(nam, thang, ngay, 12, 0), timezone.get_current_timezone())  # 12 giờ trưa cho khỏi lệch ngày
        return SimpleNamespace(MaTinNhan=SimpleNamespace(ThoiGianGui=luc))  # giống DinhKemTinNhan đủ dùng

    def test_chia_nhom_va_nhan_thang(self):  # ảnh mới nhất trước, mỗi tháng một nhóm
        nam = timezone.localtime().year  # năm hiện tại
        ds = [self._anh(nam, 11, 5), self._anh(nam, 11, 1), self._anh(nam, 3, 2), self._anh(nam - 1, 12, 30)]  # 4 ảnh, 3 tháng
        nhom = services.nhom_anh_theo_thang(ds)  # chia nhóm
        self.assertEqual([n['khoa'] for n in nhom], ['%d-11' % nam, '%d-03' % nam, '%d-12' % (nam - 1)])  # khóa tháng
        self.assertEqual([n['nhan'] for n in nhom], ['Tháng 11', 'Tháng 3', 'Tháng 12/%d' % (nam - 1)])  # năm khác ghi kèm năm
        self.assertEqual([len(n['anh']) for n in nhom], [2, 1, 1])  # số ảnh mỗi nhóm

    def test_danh_sach_rong(self):  # không có ảnh
        self.assertEqual(services.nhom_anh_theo_thang([]), [])  # không có nhóm nào


# ---------------------------------------------------------------------------------------------
# Trạng thái riêng từng người: đã xem, chưa đọc, ghim, ẩn, xóa, thu hồi, trả lời (bước 1 đến 6)
# ---------------------------------------------------------------------------------------------
class TrangThaiCuocTests(CoSoTest):  # THAMGIA và các nút ba chấm
    def post(self, ten_url, user, ma_cuoc=None, **kw):  # POST nhanh tới một view dạng JSON
        self.client.force_login(user)  # đăng nhập
        return self.client.post(reverse(ten_url, args=[ma_cuoc or self.cuoc.pk]), **AJAX, **kw)  # POST ngầm

    def dong(self, user, ma=None, chi_an=False):  # dòng của một cuộc trong cột trái của user (None nếu không có)
        for d in services.danh_sach_cuoc(user, chi_an=chi_an):  # duyệt danh sách
            if d['ma'] == (ma or self.cuoc.pk):  # đúng cuộc
                return d  # trả về
        return None  # không có

    def test_so_chua_doc_va_mo_trang_la_da_xem(self):  # 3 tin chưa đọc, mở trang thì về 0
        for i in range(3):  # nhiếp ảnh gia gửi 3 tin (qua services để hai hàng THAMGIA được tạo TRƯỚC tin; tạo bằng ORM thì tin có sẵn bị coi là đã đọc)
            services.gui_tin_nhan(self.cuoc, self.nag.MaTaiKhoan, 'tin %d' % i)  # gửi tin
        d = self.dong(self.khach)  # dòng của khách
        self.assertEqual(d['so_chua_doc'], 3)  # 3 tin chưa đọc
        self.assertTrue(d['chua_doc'])  # in đậm, lọt bộ lọc Chưa đọc
        self.client.force_login(self.khach)  # khách mở cuộc trò chuyện
        self.client.get(self.url_trang)  # ghi đã xem
        d = self.dong(self.khach)  # dòng sau khi mở
        self.assertEqual(d['so_chua_doc'], 0)  # hết chưa đọc
        self.assertFalse(d['chua_doc'])  # không còn in đậm

    def test_tin_cua_chinh_minh_khong_tinh_chua_doc(self):  # tự gửi thì không tự báo chưa đọc
        services.gui_tin_nhan(self.cuoc, self.khach, 'chao')  # khách gửi
        self.assertEqual(self.dong(self.khach)['so_chua_doc'], 0)  # khách không có tin chưa đọc
        self.assertEqual(self.dong(self.nag.MaTaiKhoan)['so_chua_doc'], 1)  # nhiếp ảnh gia có 1

    def test_da_xem_hien_cho_nguoi_gui(self):  # mốc đã xem của đối phương
        t = services.gui_tin_nhan(self.cuoc, self.khach, 'chao anh')  # khách gửi
        self.assertLess(services.doi_phuong_da_xem_toi(self.cuoc, self.khach), t.pk)  # nhiếp ảnh gia chưa xem
        self.client.force_login(self.nag.MaTaiKhoan)  # nhiếp ảnh gia mở trang
        self.client.get(self.url_trang)  # ghi đã xem
        self.assertGreaterEqual(services.doi_phuong_da_xem_toi(self.cuoc, self.khach), t.pk)  # đã xem tới tin đó

    def test_da_xem_khong_bao_gio_lui(self):  # khai báo mã nhỏ hơn không làm lùi, mã quá lớn bị chặn
        t = services.gui_tin_nhan(self.cuoc, self.nag.MaTaiKhoan, 'a')  # một tin
        services.danh_dau_da_xem(self.cuoc, self.khach, t.pk)  # xem tới tin này
        services.danh_dau_da_xem(self.cuoc, self.khach, 0)  # thử lùi
        self.assertEqual(services.lay_tham_gia(self.cuoc, self.khach).MaTinDaXemCuoi, t.pk)  # vẫn giữ nguyên
        services.danh_dau_da_xem(self.cuoc, self.khach, t.pk + 999)  # khai quá tin thật
        self.assertEqual(services.lay_tham_gia(self.cuoc, self.khach).MaTinDaXemCuoi, t.pk)  # bị chặn ở tin cuối thật

    def test_danh_dau_chua_doc_roi_bo(self):  # nút ba chấm đổi qua lại
        services.gui_tin_nhan(self.cuoc, self.nag.MaTaiKhoan, 'a')  # có một tin
        self.client.force_login(self.khach)  # khách đọc
        self.client.get(self.url_trang)  # đã đọc hết
        r = self.post('doi_chua_doc', self.khach)  # đánh dấu chưa đọc
        self.assertTrue(_json(r)['chua_doc'])  # đang chưa đọc
        self.assertTrue(self.dong(self.khach)['chua_doc'])  # cột trái cũng thấy
        r = self.post('doi_chua_doc', self.khach)  # bấm lại
        self.assertFalse(_json(r)['chua_doc'])  # về đã đọc

    def test_ghim_len_dau_chi_cho_nguoi_ghim(self):  # ghim chỉ đổi hàng của chính mình
        nag2 = _tao_nag('nag2')  # nhiếp ảnh gia thứ hai
        cuoc2 = CuocTroChuyen.objects.create(MaKhachHang=self.khach, MaNhiepAnhGia=nag2)  # cuộc thứ hai của khách
        self.tin(self.khach, 'cu')  # tin ở cuộc 1
        TinNhan.objects.create(MaCuocTroChuyen=cuoc2, MaNguoiGui=self.khach, NoiDung='moi')  # tin mới hơn ở cuộc 2
        thu_tu = [d['ma'] for d in services.danh_sach_cuoc(self.khach)]  # chưa ghim
        self.assertEqual(thu_tu, [cuoc2.pk, self.cuoc.pk])  # cuộc 2 mới hơn nên đứng đầu
        r = self.post('doi_ghim', self.khach)  # ghim cuộc 1
        self.assertTrue(_json(r)['trang_thai'])  # đang ghim
        thu_tu = [d['ma'] for d in services.danh_sach_cuoc(self.khach)]  # sau khi ghim
        self.assertEqual(thu_tu, [self.cuoc.pk, cuoc2.pk])  # cuộc ghim lên đầu
        self.assertFalse(self.dong(self.nag.MaTaiKhoan)['da_ghim'])  # nhiếp ảnh gia không bị ghim theo
        r = self.post('doi_ghim', self.khach)  # bấm lại
        self.assertFalse(_json(r)['trang_thai'])  # bỏ ghim

    def test_an_roi_tu_hien_lai_khi_co_tin_moi(self):  # ẩn khỏi danh sách thường, có tin mới thì hiện lại
        services.gui_tin_nhan(self.cuoc, self.nag.MaTaiKhoan, 'a')  # có tin
        r = self.post('doi_an', self.khach)  # ẩn
        self.assertTrue(_json(r)['trang_thai'])  # đang ẩn
        self.assertIsNone(self.dong(self.khach))  # không có trong danh sách thường
        self.assertIsNotNone(self.dong(self.khach, chi_an=True))  # có trong tab Đã ẩn
        services.gui_tin_nhan(self.cuoc, self.nag.MaTaiKhoan, 'b')  # tin mới
        self.assertIsNotNone(self.dong(self.khach))  # hiện lại ở danh sách thường
        self.assertIsNone(self.dong(self.khach, chi_an=True))  # khỏi tab Đã ẩn

    def test_xoa_chi_phia_minh(self):  # khách xóa, nhiếp ảnh gia vẫn thấy đủ
        self.tin(self.khach, 'noidungcu-khach')  # tin của khách
        self.tin(self.nag.MaTaiKhoan, 'noidungcu-nag')  # tin của nhiếp ảnh gia
        self.post('xoa_cuoc', self.khach)  # khách xóa phía mình
        self.assertIsNone(self.dong(self.khach))  # biến khỏi danh sách của khách
        self.assertIsNotNone(self.dong(self.nag.MaTaiKhoan))  # nhiếp ảnh gia vẫn còn
        self.client.force_login(self.khach)  # khách mở lại trang
        self.assertNotContains(self.client.get(self.url_trang), 'noidungcu')  # không còn thấy tin cũ
        self.client.force_login(self.nag.MaTaiKhoan)  # nhiếp ảnh gia mở
        r = self.client.get(self.url_trang)  # trang chat
        self.assertContains(r, 'noidungcu-khach')  # vẫn thấy tin của khách
        self.assertContains(r, 'noidungcu-nag')  # và tin của mình
        self.assertEqual(TinNhan.objects.filter(MaCuocTroChuyen=self.cuoc).count(), 2)  # dữ liệu không bị xóa
        services.gui_tin_nhan(self.cuoc, self.nag.MaTaiKhoan, 'tin-sau-khi-xoa')  # có tin mới
        self.assertIsNotNone(self.dong(self.khach))  # cuộc tự hiện lại
        self.client.force_login(self.khach)  # khách mở
        r = self.client.get(self.url_trang)  # trang chat
        self.assertContains(r, 'tin-sau-khi-xoa')  # thấy tin mới
        self.assertNotContains(r, 'noidungcu')  # tin cũ vẫn không quay lại

    def test_ba_cham_cua_nguoi_ngoai_bi_404(self):  # người ngoài cuộc không đổi được trạng thái
        la = _tao_user('khach_la4', VaiTro.KHACH_HANG)  # khách khác
        for ten in ('doi_ghim', 'doi_an', 'xoa_cuoc', 'doi_chua_doc'):  # bốn nút ba chấm
            self.assertEqual(self.post(ten, la).status_code, 404, ten)  # đều 404
        self.assertFalse(ThamGia.objects.filter(MaCuocTroChuyen=self.cuoc, MaNguoiDung=la).exists())  # không tạo hàng nào cho người lạ

    def test_ba_cham_chi_nhan_post(self):  # GET bị chặn
        self.client.force_login(self.khach)  # đăng nhập
        self.assertEqual(self.client.get(reverse('doi_ghim', args=[self.cuoc.pk])).status_code, 405)  # 405


class ThuHoiVaTraLoiTests(CoSoTest):  # thu hồi và trả lời tin
    def thu_hoi(self, user, tin):  # POST thu hồi
        self.client.force_login(user)  # đăng nhập
        return self.client.post(reverse('thu_hoi_tin', args=[self.cuoc.pk, tin.pk]), **AJAX)  # POST

    def test_chi_nguoi_gui_thu_hoi_duoc(self):  # tin của người kia bị 403
        cua_nag = self.tin(self.nag.MaTaiKhoan, 'tin cua nag')  # tin của nhiếp ảnh gia
        self.assertEqual(self.thu_hoi(self.khach, cua_nag).status_code, 403)  # khách không thu hồi được
        cua_nag.refresh_from_db()  # nạp lại
        self.assertFalse(cua_nag.DaThuHoi)  # tin còn nguyên
        self.assertEqual(self.thu_hoi(self.nag.MaTaiKhoan, cua_nag).status_code, 200)  # người gửi thu hồi được

    def test_thu_hoi_giu_noi_dung_trong_db_nhung_khong_gui_cho_trinh_duyet(self):  # đúng quyết định số 4
        t = self.tin(self.nag.MaTaiKhoan, BI_MAT)  # tin sẽ thu hồi
        self.thu_hoi(self.nag.MaTaiKhoan, t)  # thu hồi
        t.refresh_from_db()  # nạp lại
        self.assertTrue(t.DaThuHoi)  # đã đánh dấu
        self.assertIsNotNone(t.ThuHoiLuc)  # có giờ thu hồi
        self.assertEqual(t.NoiDung, BI_MAT)  # nội dung vẫn nằm trong DB
        for user in (self.khach, self.nag.MaTaiKhoan):  # cả hai bên
            self.client.force_login(user)  # đăng nhập
            self.assertNotContains(self.client.get(self.url_trang), BI_MAT)  # trang chat
            self.assertNotContains(self.client.get(self.url_moi, {'sau': 0}), BI_MAT)  # polling
            self.assertNotContains(self.client.get(reverse('tin_nhan_moi', args=[self.cuoc.pk]), {'truoc': t.pk + 1}), BI_MAT)  # tải tin cũ
        dong = services.danh_sach_cuoc(self.khach)[0]  # dòng cột trái của khách
        self.assertEqual(dong['noi_dung'], 'Tin nhắn đã bị thu hồi')  # xem trước dùng câu thay thế
        self.assertNotIn(BI_MAT, dong['noi_dung'])  # không lộ chữ

    def test_thu_hoi_tin_khong_thuoc_cuoc_la_404(self):  # tin của cuộc khác
        nag2 = _tao_nag('nag3')  # nhiếp ảnh gia khác
        cuoc2 = CuocTroChuyen.objects.create(MaKhachHang=self.khach, MaNhiepAnhGia=nag2)  # cuộc khác của cùng khách
        t2 = TinNhan.objects.create(MaCuocTroChuyen=cuoc2, MaNguoiGui=self.khach, NoiDung='o cuoc khac')  # tin ở cuộc khác
        self.assertEqual(self.thu_hoi(self.khach, t2).status_code, 404)  # không thu hồi qua cuộc này được

    def test_tra_loi_luu_ma_tin_goc(self):  # MaTinTraLoi
        goc = self.tin(self.nag.MaTaiKhoan, 'tin goc')  # tin gốc
        tl = services.gui_tin_nhan(self.cuoc, self.khach, 'tra loi', ma_tra_loi=goc.pk)  # trả lời
        self.assertEqual(tl.MaTinTraLoi_id, goc.pk)  # lưu đúng tin gốc

    def test_khong_tra_loi_duoc_tin_da_thu_hoi_hoac_cuoc_khac(self):  # hai trường hợp bị chặn
        goc = self.tin(self.nag.MaTaiKhoan, 'tin goc')  # tin gốc
        services.thu_hoi_tin(self.cuoc, self.nag.MaTaiKhoan, goc.pk)  # thu hồi
        with self.assertRaises(ValidationError):  # trả lời tin đã thu hồi
            services.gui_tin_nhan(self.cuoc, self.khach, 'x', ma_tra_loi=goc.pk)  # bị từ chối
        nag2 = _tao_nag('nag4')  # nhiếp ảnh gia khác
        cuoc2 = CuocTroChuyen.objects.create(MaKhachHang=self.khach, MaNhiepAnhGia=nag2)  # cuộc khác
        o_cuoc_khac = TinNhan.objects.create(MaCuocTroChuyen=cuoc2, MaNguoiGui=self.khach, NoiDung='y')  # tin ở cuộc khác
        with self.assertRaises(ValidationError):  # trả lời tin của cuộc khác
            services.gui_tin_nhan(self.cuoc, self.khach, 'x', ma_tra_loi=o_cuoc_khac.pk)  # bị từ chối

    def test_trich_dan_khong_lo_noi_dung_khi_tin_goc_bi_thu_hoi(self):  # thu hồi tin gốc sau khi đã có người trả lời
        goc = self.tin(self.nag.MaTaiKhoan, BI_MAT)  # tin gốc
        services.gui_tin_nhan(self.cuoc, self.khach, 'ok em biet', ma_tra_loi=goc.pk)  # khách trả lời
        services.thu_hoi_tin(self.cuoc, self.nag.MaTaiKhoan, goc.pk)  # nhiếp ảnh gia thu hồi tin gốc
        self.client.force_login(self.khach)  # khách mở trang
        r = self.client.get(self.url_trang)  # trang chat
        self.assertContains(r, 'ok em biet')  # tin trả lời vẫn hiện
        self.assertNotContains(r, BI_MAT)  # khối trích dẫn không lộ nội dung gốc

    def test_trich_dan_khong_lo_phan_da_xoa_phia_minh(self):  # tin gốc nằm trong phần đã xóa của người xem
        goc = self.tin(self.nag.MaTaiKhoan, BI_MAT)  # tin gốc
        services.gui_tin_nhan(self.cuoc, self.khach, 'tra loi', ma_tra_loi=goc.pk)  # trả lời
        services.xoa_cuoc_phia_minh(self.cuoc, self.khach)  # khách xóa phía mình (tin trả lời cũng nằm trong phần đã xóa)
        moi = services.gui_tin_nhan(self.cuoc, self.nag.MaTaiKhoan, 'tin moi')  # có tin mới
        self.assertIsNotNone(moi.pk)  # đã lưu
        self.client.force_login(self.khach)  # khách mở trang
        self.assertNotContains(self.client.get(self.url_trang), BI_MAT)  # tin gốc đã xóa không quay lại
