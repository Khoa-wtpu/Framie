"""
Bộ kiểm thử cho chức năng giữ chỗ UC4.1.
Các test case kiểm tra luồng chọn slot, đổi slot, hết hạn, hoàn tất, xử lý lỗi và phân quyền.
"""

# Nhập timedelta để tạo khoảng thời gian, ví dụ ngày trong tương lai hoặc thời điểm hết hạn.
from datetime import timedelta
# Nhập mock để giả lập hành vi của hàm khi kiểm thử các tình huống lỗi.
from unittest import mock

# Lấy model người dùng đang được cấu hình trong dự án, thay vì cố định một model cụ thể.
from django.contrib.auth import get_user_model
# Nhập model Group để tạo và gán nhóm quyền cho tài khoản kiểm thử.
from django.contrib.auth.models import Group
# Nhập lỗi OperationalError để mô phỏng sự cố khi truy cập cơ sở dữ liệu.
from django.db import OperationalError
# Nhập TestCase của Django, cung cấp môi trường và cơ chế kiểm thử có quản lý database.
from django.test import TestCase
# Nhập reverse để lấy URL từ tên route đã khai báo trong urls.py.
from django.urls import reverse
# Nhập timezone để sử dụng ngày giờ theo cấu hình múi giờ của Django.
from django.utils import timezone

# Nhập module xử lý giữ chỗ và đặt bí danh uc để gọi các hàm, ngoại lệ trong module.
from bookings import giu_cho as uc
# Nhập model lượt giữ chỗ và hằng số quy định thời lượng giữ chỗ.
from bookings.models import GiuCho, THOI_GIAN_GIU_CHO
# Nhập các hằng số trạng thái và vai trò để kiểm thử đúng theo quy ước của hệ thống.
from core.constants import TrangThaiGiuCho as GC, TrangThaiHoSo, TrangThaiSlot as SL, VaiTro
# Nhập model hồ sơ nhiếp ảnh gia để tạo dữ liệu kiểm thử.
from profiles.models import NhiepAnhGia
# Nhập model lịch khả dụng để tạo các khung giờ có thể được giữ.
from schedule.models import LichKhaDung

# Lấy model tài khoản người dùng thực tế của dự án để tạo người dùng kiểm thử.
User = get_user_model()


# Hàm tiện ích tạo tài khoản kiểm thử; có thể truyền nhóm quyền và các thuộc tính bổ sung.
def tao_user(ten, nhom=None, **kw):
    # Tạo tài khoản với tên đăng nhập, email và mật khẩu dùng riêng trong môi trường kiểm thử.
    u = User.objects.create_user(username=ten, email=f'{ten}@x.vn', password='x',
                                 # Sinh số điện thoại kiểm thử từ tên tài khoản và truyền thêm các thuộc tính được cung cấp.
                                 so_dien_thoai=f'09{abs(hash(ten)) % 10**8:08d}', **kw)
    # Chỉ thực hiện gán nhóm khi hàm được truyền tên nhóm.
    if nhom:
        # Lấy nhóm đã tồn tại hoặc tạo mới, sau đó thêm tài khoản vào nhóm đó.
        u.groups.add(Group.objects.get_or_create(name=nhom)[0])
    return u


# Khai báo nhóm kiểm thử cho chức năng UC4.1; TestCase giúp Django tạo database kiểm thử riêng.
class UC41(TestCase):
    # Hàm chuẩn bị dữ liệu ban đầu, được chạy trước mỗi test case trong lớp.
    def setUp(self):
        # Tạo khách hàng A để kiểm thử người đang giữ hoặc chọn khung giờ.
        self.a = tao_user('khach_a', VaiTro.KHACH_HANG)
        # Tạo khách hàng B để kiểm thử hành vi của người dùng khác.
        self.b = tao_user('khach_b', VaiTro.KHACH_HANG)
        # Tạo tài khoản nhiếp ảnh gia và đặt trạng thái hồ sơ đã được duyệt.
        self.nag_user = tao_user('nag', VaiTro.NHIEP_ANH_GIA, trang_thai_ho_so=TrangThaiHoSo.DA_DUYET)
        # Tạo hồ sơ nhiếp ảnh gia gắn với tài khoản vừa tạo và cung cấp các trường thông tin bắt buộc.
        self.nag = NhiepAnhGia.objects.create(MaTaiKhoan=self.nag_user, AnhDaiDien='a.jpg', GioiThieu='g',
                                              # Hoàn tất thông tin ngân hàng và ảnh mã QR cho hồ sơ nhiếp ảnh gia.
                                              NganHang='b', SoTaiKhoan='1', ChuTaiKhoan='c', AnhMaQR='q.png')
        # Chọn ngày trong tương lai hai ngày để tạo lịch kiểm thử còn hiệu lực.
        ngay = timezone.localdate() + timedelta(days=2)
        # Tạo khung giờ thứ nhất từ 09:00 đến 10:00 của nhiếp ảnh gia.
        self.s1 = LichKhaDung.objects.create(MaNhiepAnhGia=self.nag, Ngay=ngay, GioBatDau='09:00', GioKetThuc='10:00')
        # Tạo khung giờ thứ hai liền sau khung giờ thứ nhất để kiểm thử đổi slot.
        self.s2 = LichKhaDung.objects.create(MaNhiepAnhGia=self.nag, Ngay=ngay, GioBatDau='10:00', GioKetThuc='11:00')
        # Bắt đầu tạo một khung giờ thuộc ngày hôm qua để kiểm tra hệ thống từ chối lịch quá khứ.
        self.qua_khu = LichKhaDung.objects.create(MaNhiepAnhGia=self.nag, Ngay=timezone.localdate() - timedelta(days=1),
                                                  # Thiết lập thời gian của khung giờ quá khứ từ 09:00 đến 10:00.
                                                  GioBatDau='09:00', GioKetThuc='10:00')

    # Hàm phụ lấy trạng thái hiện tại của một khung giờ từ database.
    def trang_thai(self, slot):
        # Truy vấn lại khung giờ theo khóa chính để lấy trạng thái mới nhất, tránh dùng dữ liệu cũ trong bộ nhớ.
        return LichKhaDung.objects.get(pk=slot.pk).TrangThai

    # Hàm phụ mô phỏng thao tác người dùng chọn một khung giờ.
    def chon(self, user, slot):
        # Đăng nhập người dùng vào Django test client trước khi gửi request.
        self.client.force_login(user)
        # Gửi request POST đến route chọn slot, truyền khóa chính của khung giờ trong URL.
        return self.client.post(reverse('chon_slot', args=[slot.pk]),
                                # Gửi mã nhiếp ảnh gia trong dữ liệu POST và tự động đi theo các bước redirect để kiểm tra trang cuối.
                                {'ma_nhiep_anh_gia': self.nag.pk}, follow=True)

    # Nhóm kiểm thử luồng cơ bản: chọn slot và xác nhận lượt giữ chỗ được tạo.
    # ---- Basic flow ----
    # Kiểm tra luồng chính khi khách hàng chọn một slot còn trống.
    def test_luong_chinh(self):
        # Cho khách hàng A chọn khung giờ thứ nhất.
        r = self.chon(self.a, self.s1)
        # Xác nhận request cuối cùng trả về HTTP 200.
        self.assertEqual(r.status_code, 200)
        # Xác nhận slot vẫn ở trạng thái đang giữ sau khi lượt giữ được hoàn tất.
        self.assertEqual(self.trang_thai(self.s1), SL.DANG_GIU)
        # Lấy lượt giữ do khách hàng A tạo.
        g = GiuCho.objects.get()
        # Kiểm tra lượt giữ chỗ gắn đúng khách hàng, lịch và trạng thái đang giữ.
        self.assertEqual((g.MaKhachHang, g.MaLich, g.TrangThai), (self.a, self.s1, GC.DANG_GIU))
        # Kiểm tra khoảng thời gian từ lúc giữ đến lúc hết hạn đúng bằng thời lượng cấu hình.
        self.assertEqual(g.ThoiDiemHetHan - g.ThoiDiemGiu, THOI_GIAN_GIU_CHO)
        # Xác nhận hệ thống chuyển người dùng đến màn hình giữ chỗ tương ứng.
        self.assertEqual(r.redirect_chain[-1][0], reverse('man_hinh_giu_cho', args=[g.pk]))
        # Kiểm tra số giây đếm ngược ban đầu xấp xỉ 5 phút, có dung sai do thời gian xử lý request.
        self.assertTrue(290 <= r.context['con_lai_giay'] <= 300)
        # Xác nhận trang phản hồi có phần tử HTML dùng để hiển thị đồng hồ đếm ngược.
        self.assertContains(r, 'id="dem-nguoc"')

    # Kiểm tra trang lịch chỉ hiển thị các slot còn trống, không hiển thị slot đang được giữ.
    def test_trang_lich_chi_hien_slot_trong(self):
        # Khách hàng A giữ khung giờ thứ nhất trước.
        self.chon(self.a, self.s1)
        # Đăng nhập bằng khách hàng B để thử truy cập lượt của A.
        self.client.force_login(self.b)
        # Khách hàng mở trang chọn lịch khi không còn slot nào.
        r = self.client.get(reverse('lich_chon_slot', args=[self.nag.pk]))
        # Lấy danh sách khóa chính của tất cả slot được truyền sang template, theo từng ngày.
        ds = [s.pk for _, slots in r.context['lich_theo_ngay'] for s in slots]
        # Xác nhận chỉ slot thứ hai xuất hiện; slot đang giữ và slot quá khứ đều bị loại khỏi danh sách.
        self.assertEqual(ds, [self.s2.pk])          # s1 đang giữ, slot quá khứ không hiện

    # Kiểm tra trang lịch hiển thị thông báo khi khách hàng hiện tại đang giữ một khung giờ.
    def test_banner_dang_giu_tren_trang_lich(self):
        # Khách hàng A giữ khung giờ thứ nhất trước.
        self.chon(self.a, self.s1)
        # Khách hàng mở trang chọn lịch khi không còn slot nào.
        r = self.client.get(reverse('lich_chon_slot', args=[self.nag.pk]))
        # Xác nhận nội dung banner thông báo đang giữ chỗ xuất hiện trên trang.
        self.assertContains(r, 'Bạn đang giữ chỗ một khung giờ')

    # Nhóm kiểm thử các ràng buộc: người khác không được chọn slot đang giữ, slot quá khứ hoặc slot không tồn tại.
    # ---- BR4.1-2 / 4a ----
    # Kiểm tra khách hàng thứ hai không thể chiếm slot đang được khách hàng thứ nhất giữ.
    def test_nguoi_khac_khong_chon_duoc_slot_dang_giu(self):
        # Khách hàng A giữ khung giờ thứ nhất trước.
        self.chon(self.a, self.s1)
        # Cho khách hàng B thử giữ cùng slot dù trạng thái slot đang hiển thị là trống.
        r = self.chon(self.b, self.s1)
        # Xác nhận hệ thống thông báo slot không còn khả dụng.
        self.assertContains(r, 'Slot không còn khả dụng')
        # Đảm bảo thao tác chọn lại không tạo thêm lượt giữ chỗ.
        self.assertEqual(GiuCho.objects.count(), 1)
        # Xác nhận lượt giữ chỗ duy nhất vẫn thuộc khách hàng A.
        self.assertEqual(GiuCho.objects.get().MaKhachHang, self.a)
        # Kiểm tra người dùng được chuyển về trang chọn lịch khi thao tác thất bại.
        self.assertEqual(r.redirect_chain[-1][0], reverse('lich_chon_slot', args=[self.nag.pk]))

    # Kiểm tra không thể giữ một khung giờ thuộc ngày đã qua.
    def test_slot_da_qua_gio_khong_chon_duoc(self):
        # Cho khách hàng A thử chọn slot quá khứ.
        r = self.chon(self.a, self.qua_khu)
        # Xác nhận hệ thống thông báo slot không còn khả dụng.
        self.assertContains(r, 'Slot không còn khả dụng')
        # Đảm bảo không có bản ghi giữ chỗ nào được tạo dở dang.
        self.assertEqual(GiuCho.objects.count(), 0)
        # Xác nhận trạng thái slot quá khứ không bị thay đổi.
        self.assertEqual(self.trang_thai(self.qua_khu), SL.TRONG)

    # Kiểm tra request chọn một mã slot không tồn tại trong database.
    def test_slot_khong_ton_tai(self):
        # Đăng nhập khách hàng A để truy cập trang lịch.
        self.client.force_login(self.a)
        # Gửi POST với mã slot giả định 9999 để kiểm tra xử lý đối tượng không tồn tại.
        r = self.client.post(reverse('chon_slot', args=[9999]), {'ma_nhiep_anh_gia': self.nag.pk}, follow=True)
        # Xác nhận hệ thống thông báo slot không còn khả dụng.
        self.assertContains(r, 'Slot không còn khả dụng')

    # Kiểm tra ràng buộc duy nhất vẫn bảo vệ dữ liệu khi trạng thái slot và bản ghi giữ chỗ không đồng nhất.
    def test_rang_buoc_unique_chan_khi_du_lieu_lech(self):
        # Mô tả tình huống dữ liệu lệch được dựng lên để kiểm tra tính an toàn của thao tác.
        # Giả lập dữ liệu lệch: có lượt đang giữ nhưng slot vẫn "Lịch trống" -> vẫn không tạo lượt thứ hai, slot rollback.
        # Lấy thời điểm hiện tại để tạo lượt giữ chỗ giả lập.
        now = timezone.now()
        # Tạo sẵn một lượt giữ chỗ cho khách hàng A trên slot thứ nhất.
        GiuCho.objects.create(MaKhachHang=self.a, MaLich=self.s1, ThoiDiemGiu=now,
                              # Đặt thời điểm hết hạn trong tương lai theo thời lượng giữ chỗ cấu hình.
                              ThoiDiemHetHan=now + THOI_GIAN_GIU_CHO)
        # Cho khách hàng B thử giữ cùng slot dù trạng thái slot đang hiển thị là trống.
        r = self.chon(self.b, self.s1)
        # Xác nhận hệ thống thông báo slot không còn khả dụng.
        self.assertContains(r, 'Slot không còn khả dụng')
        # Đảm bảo thao tác chọn lại không tạo thêm lượt giữ chỗ.
        self.assertEqual(GiuCho.objects.count(), 1)
        # Đảm bảo slot không bị thay đổi trạng thái khi giao dịch gặp lỗi.
        self.assertEqual(self.trang_thai(self.s1), SL.TRONG)

    # Nhóm kiểm thử chức năng khách hàng đổi từ slot đang giữ sang một slot khác.
    # ---- 3a: chọn slot khác ----
    # Kiểm tra đổi slot thành công sẽ kết thúc lượt giữ cũ và tạo lượt giữ mới.
    def test_chon_slot_khac_ghi_nhan_slot_moi(self):
        # Khách hàng A giữ khung giờ thứ nhất trước.
        self.chon(self.a, self.s1)
        # Khách hàng A tiếp tục chọn slot thứ hai để thay thế slot thứ nhất.
        self.chon(self.a, self.s2)
        # Đảm bảo slot không bị thay đổi trạng thái khi giao dịch gặp lỗi.
        self.assertEqual(self.trang_thai(self.s1), SL.TRONG)
        # Kiểm tra slot của lượt B đã hoàn tất vẫn giữ nguyên trạng thái.
        self.assertEqual(self.trang_thai(self.s2), SL.DANG_GIU)
        # Lấy bản ghi giữ chỗ gắn với slot cũ.
        cu = GiuCho.objects.get(MaLich=self.s1)
        # Lấy bản ghi giữ chỗ gắn với slot mới.
        moi = GiuCho.objects.get(MaLich=self.s2)
        # Kiểm tra lượt giữ cũ đã hết hạn và lượt giữ mới đang hoạt động.
        self.assertEqual((cu.TrangThai, moi.TrangThai), (GC.HET_HAN, GC.DANG_GIU))
        # Ghi chú rằng slot cũ phải có thể được khách hàng khác chọn sau khi đã nhả.
        # slot cũ chọn lại được bởi người khác
        # Cho khách hàng B chọn lại slot cũ vừa được trả về.
        self.chon(self.b, self.s1)
        # Xác nhận slot vẫn ở trạng thái đang giữ sau khi lượt giữ được hoàn tất.
        self.assertEqual(self.trang_thai(self.s1), SL.DANG_GIU)

    # Kiểm tra chọn lại chính slot đang giữ không làm gia hạn thời gian giữ chỗ.
    def test_chon_lai_dung_slot_khong_gia_han(self):
        # Khách hàng A giữ khung giờ thứ nhất trước.
        self.chon(self.a, self.s1)
        # Lấy lượt giữ do khách hàng A tạo.
        g = GiuCho.objects.get()
        # Lưu lại thời điểm hết hạn trước khi khách hàng chọn lại slot.
        het = g.ThoiDiemHetHan
        # Khách hàng A giữ khung giờ thứ nhất trước.
        self.chon(self.a, self.s1)
        # Đảm bảo thao tác chọn lại không tạo thêm lượt giữ chỗ.
        self.assertEqual(GiuCho.objects.count(), 1)
        # Xác nhận thời điểm hết hạn không thay đổi sau thao tác chọn lại.
        self.assertEqual(GiuCho.objects.get().ThoiDiemHetHan, het)

    # Kiểm tra nếu slot mới đã bị người khác giữ thì slot cũ của khách hàng vẫn được giữ nguyên.
    def test_chon_slot_khac_that_bai_thi_giu_nguyen_slot_cu(self):
        # Khách hàng A giữ khung giờ thứ nhất trước.
        self.chon(self.a, self.s1)
        # Khách hàng B giữ slot thứ hai trước để tạo tình huống xung đột.
        self.chon(self.b, self.s2)                 # b đang giữ s2
        # Khách hàng A thử đổi sang slot thứ hai nhưng slot này đã thuộc lượt giữ của B.
        r = self.chon(self.a, self.s2)             # a muốn đổi sang s2 nhưng đã có người giữ
        # Xác nhận hệ thống thông báo slot không còn khả dụng.
        self.assertContains(r, 'Slot không còn khả dụng')
        # Xác nhận slot thứ nhất của A vẫn đang được giữ sau khi đổi slot thất bại.
        self.assertEqual(self.trang_thai(self.s1), SL.DANG_GIU)          # slot cũ của a còn nguyên
        # Đảm bảo trạng thái bản ghi giữ chỗ cũ cũng được giữ nguyên.
        self.assertEqual(GiuCho.objects.get(MaLich=self.s1).TrangThai, GC.DANG_GIU)

    # Kiểm tra lỗi phát sinh khi giữ slot mới sẽ khiến toàn bộ giao dịch rollback, bao gồm thao tác nhả slot cũ.
    def test_loi_o_buoc_giu_slot_moi_thi_rollback_nha_slot_cu(self):
        # Khách hàng A giữ khung giờ thứ nhất trước.
        self.chon(self.a, self.s1)
        # Lưu tham chiếu hàm đổi trạng thái thật để có thể gọi lại trong hàm giả lập.
        that = uc.doi_trang_thai_khung_gio

        # Tạo hàm giả lập: chỉ gây lỗi khi hệ thống chuyển slot mới sang trạng thái đang giữ.
        def gia(lich, moi):                         # chỉ hỏng ở bước giữ slot mới; nhả slot cũ vẫn chạy thật
            # Kiểm tra trạng thái đích có phải đang giữ hay không.
            if moi == SL.DANG_GIU:
                # Chủ động phát sinh ValidationError để mô phỏng lỗi khi giữ slot mới.
                raise uc.ValidationError('x')
            # Với các trạng thái khác, gọi hàm đổi trạng thái gốc để thao tác nhả slot cũ vẫn diễn ra.
            return that(lich, moi)
        # Tạm thay hàm đổi trạng thái trong module bằng hàm giả lập trong phạm vi khối with.
        with mock.patch.object(uc, 'doi_trang_thai_khung_gio', side_effect=gia):
            # Cho khách hàng A thử đổi sang slot thứ hai trong khi thao tác đổi trạng thái bị lỗi.
            r = self.chon(self.a, self.s2)
        # Xác nhận hệ thống thông báo slot không còn khả dụng.
        self.assertContains(r, 'Slot không còn khả dụng')
        # Xác nhận giao dịch rollback đã khôi phục trạng thái đang giữ của slot cũ.
        self.assertEqual(self.trang_thai(self.s1), SL.DANG_GIU)                 # slot cũ vẫn được giữ
        # Đảm bảo trạng thái bản ghi giữ chỗ cũ cũng được giữ nguyên.
        self.assertEqual(GiuCho.objects.get(MaLich=self.s1).TrangThai, GC.DANG_GIU)
        # Xác nhận slot mới không bị giữ dở dang sau khi giao dịch thất bại.
        self.assertEqual(self.trang_thai(self.s2), SL.TRONG)

    # Kiểm tra khi thao tác nhả slot cũ gặp lỗi, hệ thống không được tiếp tục đổi slot.
    def test_khong_nha_duoc_slot_cu(self):
        # Khách hàng A giữ khung giờ thứ nhất trước.
        self.chon(self.a, self.s1)
        # Giả lập hàm đổi trạng thái luôn phát sinh ValidationError để kiểm tra lỗi ngay ở bước nhả slot cũ.
        with mock.patch.object(uc, 'doi_trang_thai_khung_gio', side_effect=uc.ValidationError('x')):
            # Cho khách hàng A thử đổi sang slot thứ hai trong khi thao tác đổi trạng thái bị lỗi.
            r = self.chon(self.a, self.s2)
        # Xác nhận hệ thống trả thông báo lỗi tổng quát cho người dùng.
        self.assertContains(r, 'Không thể thực hiện yêu cầu')
        # Xác nhận slot vẫn ở trạng thái đang giữ sau khi lượt giữ được hoàn tất.
        self.assertEqual(self.trang_thai(self.s1), SL.DANG_GIU)
        # Đảm bảo trạng thái bản ghi giữ chỗ cũ cũng được giữ nguyên.
        self.assertEqual(GiuCho.objects.get(MaLich=self.s1).TrangThai, GC.DANG_GIU)

    # Nhóm kiểm thử cơ chế hết hạn sau 5 phút và giải phóng slot.
    # ---- 5b: hết 5 phút ----
    # Hàm phụ đẩy thời điểm giữ chỗ và hết hạn về quá khứ để mô phỏng lượt giữ đã hết hạn.
    def het_gio(self, g, phut=1):
        # Cập nhật trực tiếp thời điểm bắt đầu giữ về trước hiện tại một khoảng lớn hơn thời lượng giữ chỗ.
        GiuCho.objects.filter(pk=g.pk).update(ThoiDiemGiu=timezone.now() - THOI_GIAN_GIU_CHO - timedelta(minutes=phut),
                                              # Đặt thời điểm hết hạn lùi về quá khứ theo số phút truyền vào.
                                              ThoiDiemHetHan=timezone.now() - timedelta(minutes=phut))

    # Kiểm tra khi hết thời hạn giữ chỗ, lượt giữ được đánh dấu hết hạn và slot được giải phóng.
    def test_het_5_phut_nha_slot_va_giu_cho_het_han(self):
        # Khách hàng A giữ khung giờ thứ nhất trước.
        self.chon(self.a, self.s1)
        # Lấy lượt giữ do khách hàng A tạo.
        g = GiuCho.objects.get()
        # Mô phỏng lượt giữ đã quá hạn.
        self.het_gio(g)
        # Truy cập màn hình giữ chỗ để kích hoạt kiểm tra thời hạn.
        r = self.client.get(reverse('man_hinh_giu_cho', args=[g.pk]))
        # Đảm bảo slot không bị thay đổi trạng thái khi giao dịch gặp lỗi.
        self.assertEqual(self.trang_thai(self.s1), SL.TRONG)
        # Xác nhận bản ghi giữ chỗ vẫn ở trạng thái hết hạn.
        self.assertEqual(GiuCho.objects.get().TrangThai, GC.HET_HAN)
        # Kiểm tra trang hiển thị thông báo lượt giữ chỗ đã hết hạn.
        self.assertContains(r, 'Thời gian giữ chỗ đã hết hạn')
        # Xác nhận bộ đếm thời gian còn lại bằng 0.
        self.assertEqual(r.context['con_lai_giay'], 0)
        # Xác nhận context không còn đánh dấu người dùng đang giữ chỗ.
        self.assertFalse(r.context['dang_giu'])

    # Kiểm tra API trả đúng trạng thái và số giây còn lại ở cả trường hợp còn hạn lẫn hết hạn.
    def test_api_trang_thai_con_han_va_het_han(self):
        # Khách hàng A giữ khung giờ thứ nhất trước.
        self.chon(self.a, self.s1)
        # Lấy lượt giữ do khách hàng A tạo.
        g = GiuCho.objects.get()
        # Gọi API trạng thái giữ chỗ và chuyển phản hồi JSON thành dictionary để kiểm tra.
        j = self.client.get(reverse('trang_thai_giu_cho', args=[g.pk])).json()
        # Xác nhận API cho biết lượt giữ chưa hết hạn.
        self.assertFalse(j['het_han'])
        # Kiểm tra API trả số giây còn lại xấp xỉ 5 phút.
        self.assertTrue(290 <= j['con_lai_giay'] <= 300)
        # Mô phỏng lượt giữ đã quá hạn.
        self.het_gio(g)
        # Gọi API trạng thái giữ chỗ và chuyển phản hồi JSON thành dictionary để kiểm tra.
        j = self.client.get(reverse('trang_thai_giu_cho', args=[g.pk])).json()
        # Xác nhận API nhận diện lượt giữ đã hết hạn sau khi thời gian được đẩy về quá khứ.
        self.assertTrue(j['het_han'])
        # Xác nhận API trả số giây còn lại bằng 0 khi đã hết hạn.
        self.assertEqual(j['con_lai_giay'], 0)
        # Kiểm tra trường trạng thái trong JSON là hết hạn.
        self.assertEqual(j['trang_thai'], GC.HET_HAN)
        # Đảm bảo slot không bị thay đổi trạng thái khi giao dịch gặp lỗi.
        self.assertEqual(self.trang_thai(self.s1), SL.TRONG)

    # Kiểm tra khách hàng khác có thể chọn slot sau khi lượt giữ trước đã hết hạn.
    def test_nguoi_khac_chon_duoc_sau_khi_het_han(self):
        # Khách hàng A giữ khung giờ thứ nhất trước.
        self.chon(self.a, self.s1)
        # Đẩy thời điểm hết hạn của lượt giữ của khách hàng A về quá khứ.
        self.het_gio(GiuCho.objects.get())
        # Khách hàng B chọn slot; hàm xử lý giữ chỗ phải tự dọn lượt hết hạn trước khi tạo lượt mới.
        self.chon(self.b, self.s1)                 # không ai mở trang đếm ngược: giu_cho_slot tự dọn trước
        # Xác nhận slot vẫn ở trạng thái đang giữ sau khi lượt giữ được hoàn tất.
        self.assertEqual(self.trang_thai(self.s1), SL.DANG_GIU)
        # Đảm bảo khách hàng B có đúng một lượt giữ đang hoạt động.
        self.assertEqual(GiuCho.objects.filter(MaKhachHang=self.b, TrangThai=GC.DANG_GIU).count(), 1)
        # Xác nhận lượt giữ cũ của khách hàng A vẫn được lưu với trạng thái hết hạn.
        self.assertEqual(GiuCho.objects.get(MaKhachHang=self.a).TrangThai, GC.HET_HAN)

    # Kiểm tra tác vụ quét chỉ giải phóng lượt đã hết hạn, không ảnh hưởng lượt còn hạn hoặc đã hoàn tất.
    def test_quet_khong_dung_luot_chua_het_han_hoac_da_hoan_tat(self):
        # Khách hàng A giữ khung giờ thứ nhất trước.
        self.chon(self.a, self.s1)
        self.chon(self.b, self.s2)
        # Lấy lượt giữ của khách hàng B để chuyển sang trạng thái hoàn tất.
        gb = GiuCho.objects.get(MaKhachHang=self.b)
        # Gọi hàm nghiệp vụ đánh dấu lượt giữ của khách hàng B đã hoàn tất.
        uc.hoan_tat_giu_cho(self.b, gb.pk)
        # Đẩy lượt giữ của khách hàng A về quá hạn để tác vụ quét cần giải phóng.
        self.het_gio(GiuCho.objects.get(MaKhachHang=self.a))
        # Đẩy thời điểm của lượt B về quá khứ nhưng lượt này đã hoàn tất nên không được giải phóng.
        self.het_gio(gb)                           # đã hoàn tất => không bị nhả dù quá giờ
        # Chạy tác vụ dọn dẹp và xác nhận chỉ có một lượt giữ được giải phóng.
        self.assertEqual(uc.giai_phong_giu_cho_het_han(), 1)
        # Đảm bảo slot không bị thay đổi trạng thái khi giao dịch gặp lỗi.
        self.assertEqual(self.trang_thai(self.s1), SL.TRONG)
        # Kiểm tra slot của lượt B đã hoàn tất vẫn giữ nguyên trạng thái.
        self.assertEqual(self.trang_thai(self.s2), SL.DANG_GIU)
        # Xác nhận lượt B vẫn ở trạng thái đã hoàn tất.
        self.assertEqual(GiuCho.objects.get(pk=gb.pk).TrangThai, GC.DA_HOAN_TAT)
        # Chạy tác vụ lần nữa để xác nhận không còn lượt nào cần giải phóng và thao tác có tính lặp an toàn.
        self.assertEqual(uc.giai_phong_giu_cho_het_han(), 0)       # chạy lại không đổi gì

    # Nhóm kiểm thử hàm hoàn tất lượt giữ chỗ, được sử dụng tiếp trong UC4.2.
    # ---- hoan_tat_giu_cho (cho UC4.2) ----
    # Kiểm tra có thể hoàn tất lượt giữ chỗ khi vẫn còn trong thời hạn.
    def test_hoan_tat_kip_han(self):
        # Khách hàng A giữ khung giờ thứ nhất trước.
        self.chon(self.a, self.s1)
        # Gọi hàm hoàn tất với đúng khách hàng và mã lượt giữ chỗ.
        g = uc.hoan_tat_giu_cho(self.a, GiuCho.objects.get().pk)
        # Xác nhận lượt giữ chỗ được chuyển sang trạng thái đã hoàn tất.
        self.assertEqual(g.TrangThai, GC.DA_HOAN_TAT)
        # Xác nhận slot vẫn ở trạng thái đang giữ sau khi lượt giữ được hoàn tất.
        self.assertEqual(self.trang_thai(self.s1), SL.DANG_GIU)

    # Kiểm tra không thể hoàn tất lượt giữ chỗ đã hết hạn.
    def test_hoan_tat_qua_han(self):
        # Khách hàng A giữ khung giờ thứ nhất trước.
        self.chon(self.a, self.s1)
        # Lấy lượt giữ do khách hàng A tạo.
        g = GiuCho.objects.get()
        # Mô phỏng lượt giữ đã quá hạn.
        self.het_gio(g)
        # Xác nhận lời gọi bên trong phải phát sinh ngoại lệ nghiệp vụ GiuChoLoi.
        with self.assertRaises(uc.GiuChoLoi):
            # Thử hoàn tất lượt giữ đã hết hạn để kiểm tra hệ thống từ chối.
            uc.hoan_tat_giu_cho(self.a, g.pk)
        # Đảm bảo slot không bị thay đổi trạng thái khi giao dịch gặp lỗi.
        self.assertEqual(self.trang_thai(self.s1), SL.TRONG)
        # Xác nhận bản ghi giữ chỗ vẫn ở trạng thái hết hạn.
        self.assertEqual(GiuCho.objects.get().TrangThai, GC.HET_HAN)

    # Nhóm kiểm thử xử lý lỗi hệ thống trong quá trình chọn slot.
    # ---- 4b ----
    # Kiểm tra hệ thống phản hồi an toàn khi xảy ra lỗi database lúc dọn các lượt giữ hết hạn.
    def test_loi_he_thong(self):
        # Đăng nhập khách hàng A để truy cập trang lịch.
        self.client.force_login(self.a)
        # Giả lập hàm giải phóng lượt hết hạn phát sinh OperationalError.
        with mock.patch.object(uc, 'giai_phong_giu_cho_het_han', side_effect=OperationalError('db')):
            # Gửi yêu cầu chọn slot trong lúc hàm dọn dẹp đang bị giả lập lỗi.
            r = self.client.post(reverse('chon_slot', args=[self.s1.pk]), {'ma_nhiep_anh_gia': self.nag.pk})
        # Kiểm tra response chuyển hướng về trang lịch; không tải trang đích tự động ở bước assert này.
        self.assertRedirects(r, reverse('lich_chon_slot', args=[self.nag.pk]), fetch_redirect_response=False)
        # Tự gửi GET đến URL redirect để kiểm tra nội dung trang thông báo.
        r = self.client.get(r['Location'])
        # Xác nhận người dùng nhận được thông báo lỗi hệ thống phù hợp.
        self.assertContains(r, 'Không thể thực hiện yêu cầu, vui lòng thử lại sau.')
        # Đảm bảo slot không bị thay đổi trạng thái khi giao dịch gặp lỗi.
        self.assertEqual(self.trang_thai(self.s1), SL.TRONG)
        # Đảm bảo không có bản ghi giữ chỗ nào được tạo dở dang.
        self.assertEqual(GiuCho.objects.count(), 0)

    # Nhóm kiểm thử xác thực, phân quyền và giới hạn truy cập dữ liệu giữ chỗ.
    # ---- Quyền ----
    # Kiểm tra người chưa đăng nhập không thể thực hiện thao tác chọn slot.
    def test_chua_dang_nhap(self):
        # Gửi request chọn slot bằng tài khoản nhiếp ảnh gia.
        r = self.client.post(reverse('chon_slot', args=[self.s1.pk]))
        # Xác nhận hệ thống chuyển hướng người dùng đến trang đăng nhập.
        self.assertEqual(r.status_code, 302)
        # Kiểm tra URL chuyển hướng có tham số next để quay lại trang cần truy cập sau khi đăng nhập.
        self.assertIn('next=', r['Location'])
        # Đảm bảo slot không bị thay đổi trạng thái khi giao dịch gặp lỗi.
        self.assertEqual(self.trang_thai(self.s1), SL.TRONG)

    # Kiểm tra tài khoản không thuộc vai trò khách hàng không được chọn slot.
    def test_khong_phai_khach_hang(self):
        # Đăng nhập bằng tài khoản nhiếp ảnh gia.
        self.client.force_login(self.nag_user)
        # Gửi request chọn slot bằng tài khoản nhiếp ảnh gia.
        r = self.client.post(reverse('chon_slot', args=[self.s1.pk]))
        # Xác nhận server trả HTTP 403 Forbidden do không đủ quyền.
        self.assertEqual(r.status_code, 403)
        # Đảm bảo slot không bị thay đổi trạng thái khi giao dịch gặp lỗi.
        self.assertEqual(self.trang_thai(self.s1), SL.TRONG)

    # Tài khoản chưa thuộc nhóm nào bị chặn (403): khach_hang_required theo cùng quy tắc với GiuCho.clean() (phải thuộc
    # nhóm Khách hàng). accounts.permissions.chi_khach_hang thì cho qua -> đây là lý do giữ bản riêng (xem ghi chú ở giu_cho.py).
    def test_tai_khoan_chua_co_nhom_bi_chan(self):
        khong_nhom = tao_user('khong_nhom')
        self.client.force_login(khong_nhom)
        self.assertEqual(self.client.get(reverse('lich_chon_slot', args=[self.nag.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse('chon_slot', args=[self.s1.pk])).status_code, 403)
        self.assertEqual(self.trang_thai(self.s1), SL.TRONG)

    # Câu "giữ chỗ cho bạn N phút" lấy từ THOI_GIAN_GIU_CHO, không viết cứng.
    def test_trang_lich_hien_so_phut_theo_hang_so(self):
        self.client.force_login(self.a)
        url = reverse('lich_chon_slot', args=[self.nag.pk])
        self.assertContains(self.client.get(url), '<strong>5 phút</strong>')
        with mock.patch.object(uc, 'THOI_GIAN_GIU_CHO', timedelta(minutes=7)):
            r = self.client.get(url)
        self.assertContains(r, '<strong>7 phút</strong>')
        self.assertNotContains(r, '<strong>5 phút</strong>')

    # Kiểm tra khách hàng không thể xem màn hình hoặc API của lượt giữ thuộc khách hàng khác.
    def test_khong_xem_duoc_luot_cua_nguoi_khac(self):
        # Khách hàng A giữ khung giờ thứ nhất trước.
        self.chon(self.a, self.s1)
        # Lấy lượt giữ do khách hàng A tạo.
        g = GiuCho.objects.get()
        # Đăng nhập bằng khách hàng B để thử truy cập lượt của A.
        self.client.force_login(self.b)
        # Xác nhận khách hàng B không truy cập được trang chi tiết lượt giữ của A và nhận HTTP 404.
        self.assertEqual(self.client.get(reverse('man_hinh_giu_cho', args=[g.pk])).status_code, 404)
        # Xác nhận API trạng thái cũng không tiết lộ thông tin lượt giữ của khách hàng khác.
        self.assertEqual(self.client.get(reverse('trang_thai_giu_cho', args=[g.pk])).status_code, 404)

    # Kiểm tra route chọn slot chỉ chấp nhận phương thức POST.
    def test_chon_slot_chi_nhan_post(self):
        # Đăng nhập khách hàng A để truy cập trang lịch.
        self.client.force_login(self.a)
        # Gửi GET và xác nhận server trả HTTP 405 Method Not Allowed.
        self.assertEqual(self.client.get(reverse('chon_slot', args=[self.s1.pk])).status_code, 405)

    # Kiểm tra lịch của nhiếp ảnh gia chưa được duyệt không được công khai cho khách hàng.
    def test_nag_chua_duyet_khong_cong_khai(self):
        # Cập nhật trạng thái hồ sơ nhiếp ảnh gia thành chờ duyệt.
        User.objects.filter(pk=self.nag_user.pk).update(trang_thai_ho_so=TrangThaiHoSo.CHO_DUYET)
        # Đăng nhập khách hàng A để truy cập trang lịch.
        self.client.force_login(self.a)
        # Xác nhận trang lịch không được truy cập và trả HTTP 404 khi hồ sơ chưa được duyệt.
        self.assertEqual(self.client.get(reverse('lich_chon_slot', args=[self.nag.pk])).status_code, 404)

    # Kiểm tra Nhiếp ảnh gia bị khóa tài khoản (is_active=False) thì không mở được lịch và không giữ chỗ được.
    def test_nag_bi_khoa_khong_mo_lich_va_khong_giu_cho(self):
        # Hồ sơ vẫn 'Đã duyệt' nhưng tài khoản bị khóa.
        User.objects.filter(pk=self.nag_user.pk).update(is_active=False)
        self.client.force_login(self.a)
        # Trang lịch công khai trả 404.
        self.assertEqual(self.client.get(reverse('lich_chon_slot', args=[self.nag.pk])).status_code, 404)
        # Hàm giữ chỗ từ chối, slot vẫn trống, không có lượt giữ nào.
        with self.assertRaises(uc.GiuChoLoi) as ctx:
            uc.giu_cho_slot(self.a, self.s1.pk)
        self.assertEqual(ctx.exception.thong_bao, uc.TB_NAG_KHONG_NHAN_BOOKING)
        # Qua web (POST chọn slot): không giữ được, được đưa về trang tìm kiếm thay vì trang lịch 404.
        r = self.chon(self.a, self.s1)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.redirect_chain[-1][0], reverse('search'))
        self.assertEqual(self.trang_thai(self.s1), SL.TRONG)
        self.assertFalse(GiuCho.objects.exists())

    # Kiểm tra giao diện xử lý đúng khi nhiếp ảnh gia chưa có khung giờ khả dụng.
    def test_trang_lich_rong(self):
        # Xóa toàn bộ lịch khả dụng trong dữ liệu kiểm thử để tạo trường hợp danh sách trống.
        LichKhaDung.objects.all().delete()
        # Đăng nhập khách hàng A để truy cập trang lịch.
        self.client.force_login(self.a)
        # Khách hàng mở trang chọn lịch khi không còn slot nào.
        r = self.client.get(reverse('lich_chon_slot', args=[self.nag.pk]))
        # Xác nhận trang hiển thị thông báo chưa có khung giờ trống.
        self.assertContains(r, 'chưa có khung giờ trống')

