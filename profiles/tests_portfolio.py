# profiles/tests_portfolio.py - K5: quản lý Portfolio (UC1.3). Chạy: python manage.py test profiles
import shutil
import tempfile
from datetime import timedelta
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.datastructures import MultiValueDict
from django.utils import timezone
from PIL import Image

from core.constants import TrangThaiHoSo, VaiTro
from profiles.forms_portfolio import ProjectForm
from profiles.models import HinhAnhProject, LoaiHinhChup, NhiepAnhGia, Project

User = get_user_model()
THU_MUC_ANH = tempfile.mkdtemp()      # ảnh test lưu ở đây, không làm bẩn thư mục media thật


def tao_anh(ten='a.png', dinh_dang='PNG'):
    bo_nho = BytesIO()
    Image.new('RGB', (10, 10), 'red').save(bo_nho, dinh_dang)
    return SimpleUploadedFile(ten, bo_nho.getvalue())


@override_settings(MEDIA_ROOT=THU_MUC_ANH)
class PortfolioTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(THU_MUC_ANH, ignore_errors=True)

    def setUp(self):
        self.nhom_nag, _ = Group.objects.get_or_create(name=VaiTro.NHIEP_ANH_GIA)
        self.dem = 0
        self.user, self.nag = self.tao_nag('nag1')
        self.user2, self.nag2 = self.tao_nag('nag2')
        self.cuoi = LoaiHinhChup.objects.create(TenLoaiHinh='Cưới')
        self.chan_dung = LoaiHinhChup.objects.create(TenLoaiHinh='Chân dung')
        self.client.force_login(self.user)
        self.ngay = (timezone.localdate() - timedelta(days=10)).isoformat()

    # ---- dữ liệu mẫu ----
    def tao_nag(self, ten, trang_thai=TrangThaiHoSo.DA_DUYET, co_ho_so=True):
        self.dem += 1
        user = User.objects.create_user(ten, f'{ten}@example.com', 'Matkhau@123',
                                        so_dien_thoai=f'09200000{self.dem:02d}')
        user.groups.add(self.nhom_nag)
        user.trang_thai_ho_so = trang_thai
        user.save()
        nag = None
        if co_ho_so:
            nag = NhiepAnhGia.objects.create(
                MaTaiKhoan=user, AnhDaiDien='avatars/a.png', GioiThieu='x',
                NganHang='VCB', SoTaiKhoan='123', ChuTaiKhoan='A', AnhMaQR='qr/a.png')
        return user, nag

    def tao_project(self, nag, ten='Project mẫu', so_hinh=3):
        project = Project.objects.create(
            MaNhiepAnhGia=nag, MaLoaiHinh=self.cuoi, TenProject=ten, AnhBia=tao_anh('bia.png'),
            NgayChup=timezone.localdate() - timedelta(days=30))
        for i in range(1, so_hinh + 1):
            HinhAnhProject.objects.create(MaProject=project, DuongDanHinhAnh=tao_anh(f'h{i}.png'), ThuTu=i)
        return project

    def du_lieu(self, **doi):
        data = {'TenProject': 'Chân dung studio', 'MaLoaiHinh': self.cuoi.pk, 'NgayChup': self.ngay,
                'Concept': 'Tối giản, ánh sáng tự nhiên', 'AnhBia': tao_anh('bia.png'),
                'anh_moi': [tao_anh('h1.png'), tao_anh('h2.png'), tao_anh('h3.png')]}
        data.update(doi)
        return data

    def tin_nhan(self, res):
        return [str(m) for m in get_messages(res.wsgi_request)]

    def thu_tu(self, project):
        return list(project.hinh_anh.order_by('ThuTu').values_list('pk', 'ThuTu'))

    # ---- quyền truy cập ----
    def test_chua_dang_nhap_ve_trang_dang_nhap(self):
        self.client.logout()
        for ten in ('portfolio', 'project_them'):
            res = self.client.get(reverse(ten))
            self.assertEqual(res.status_code, 302)
            self.assertIn('/dang-nhap/', res['Location'])

    def test_khach_hang_bi_403(self):
        khach = User.objects.create_user('khach', 'khach@example.com', 'Matkhau@123',
                                         so_dien_thoai='0988888888')
        khach.groups.add(Group.objects.get_or_create(name=VaiTro.KHACH_HANG)[0])
        self.client.force_login(khach)
        self.assertEqual(self.client.get(reverse('portfolio')).status_code, 403)
        self.assertEqual(self.client.get(reverse('project_them')).status_code, 403)

    def test_chua_duoc_duyet_khong_vao_duoc(self):
        user, _ = self.tao_nag('nag3', trang_thai=TrangThaiHoSo.CHO_DUYET)
        self.client.force_login(user)
        res = self.client.get(reverse('portfolio'))
        self.assertEqual(res.status_code, 302)
        self.assertTrue(any('chưa được duyệt' in t for t in self.tin_nhan(res)))
        res = self.client.post(reverse('project_them'), self.du_lieu())
        self.assertEqual(res.status_code, 302)
        self.assertEqual(Project.objects.count(), 0)

    def test_chua_co_ho_so_thi_chuyen_di(self):
        user, _ = self.tao_nag('nag3', co_ho_so=False)
        self.client.force_login(user)
        res = self.client.get(reverse('portfolio'))
        self.assertEqual(res.status_code, 302)
        self.assertTrue(any('chưa có hồ sơ' in t for t in self.tin_nhan(res)))

    # ---- danh sách ----
    def test_danh_sach_chi_hien_project_cua_minh(self):
        self.tao_project(self.nag, 'Của tôi', so_hinh=2)
        self.tao_project(self.nag2, 'Của người khác')
        res = self.client.get(reverse('portfolio'))
        self.assertContains(res, 'Quản lý Portfolio')
        self.assertContains(res, 'Của tôi')
        self.assertContains(res, '2 hình')
        self.assertNotContains(res, 'Của người khác')

    def test_danh_sach_trong(self):
        res = self.client.get(reverse('portfolio'))
        self.assertContains(res, 'Bạn chưa có project nào.')
        self.assertContains(res, 'Thêm project')

    # ---- thêm ----
    def test_hien_form_them(self):
        res = self.client.get(reverse('project_them'))
        for chu in ('Thêm project mới', 'Tên project', 'Loại hình chụp', 'Ngày chụp', 'Concept',
                    'Ảnh bìa', 'Hình ảnh trong project', 'Lưu', 'Hủy'):
            self.assertContains(res, chu)

    def test_them_hop_le(self):
        res = self.client.post(reverse('project_them'), self.du_lieu())
        self.assertRedirects(res, reverse('portfolio'))
        project = Project.objects.get()
        self.assertEqual(project.MaNhiepAnhGia, self.nag)
        self.assertEqual(project.TenProject, 'Chân dung studio')
        self.assertEqual(project.MaLoaiHinh, self.cuoi)
        self.assertEqual([t for _, t in self.thu_tu(project)], [1, 2, 3])
        self.assertTrue(any('Đã thêm project' in t for t in self.tin_nhan(res)))

    def test_them_thieu_thong_tin(self):
        for ten_truong, thong_bao in (('TenProject', 'Vui lòng nhập tên project.'),
                                      ('MaLoaiHinh', 'Vui lòng chọn loại hình chụp.'),
                                      ('NgayChup', 'Vui lòng chọn ngày chụp.'),
                                      ('AnhBia', 'Vui lòng tải ảnh bìa.')):
            data = self.du_lieu()
            del data[ten_truong]
            res = self.client.post(reverse('project_them'), data)
            self.assertEqual(res.status_code, 200, ten_truong)
            self.assertContains(res, thong_bao)
        self.assertEqual(Project.objects.count(), 0)

    def test_them_phai_co_it_nhat_mot_hinh(self):
        res = self.client.post(reverse('project_them'), self.du_lieu(anh_moi=[]))
        self.assertContains(res, 'Vui lòng tải lên ít nhất một hình cho project.')
        self.assertEqual(Project.objects.count(), 0)

    def test_ngay_chup_tuong_lai(self):
        ngay = (timezone.localdate() + timedelta(days=3)).isoformat()
        res = self.client.post(reverse('project_them'), self.du_lieu(NgayChup=ngay))
        self.assertContains(res, 'Ngày chụp không được ở tương lai.')

    def test_ten_project_toan_dau_cach(self):
        res = self.client.post(reverse('project_them'), self.du_lieu(TenProject='    '))
        self.assertContains(res, 'Vui lòng nhập tên project.')

    def kiem_tra_form(self, bia=None, anh_moi=None):
        """Kiểm tra thẳng form (không qua trình duyệt giả): gán tay .size vào file chỉ có tác dụng ở cách này."""
        data = self.du_lieu()
        tep = MultiValueDict({'AnhBia': [bia or tao_anh('bia.png')],
                              'anh_moi': anh_moi or [tao_anh('h1.png')]})
        return ProjectForm({k: data[k] for k in ('TenProject', 'MaLoaiHinh', 'NgayChup', 'Concept')},
                           tep, nag=self.nag)

    def test_anh_bia_khong_hop_le(self):
        bia_lon = tao_anh('lon.png')
        bia_lon.size = 6 * 1024 * 1024
        form = self.kiem_tra_form(bia=bia_lon)
        self.assertFalse(form.is_valid())
        self.assertIn('Ảnh bìa không được lớn hơn 5MB.', form.errors['AnhBia'])
        form = self.kiem_tra_form(bia=tao_anh('bia.gif', 'GIF'))
        self.assertFalse(form.is_valid())
        self.assertTrue(any('Chỉ nhận ảnh JPG' in e for e in form.errors['AnhBia']))
        # file không phải ảnh thật: đi qua trình duyệt giả cũng bị từ chối
        gia = SimpleUploadedFile('bia.png', b'khong phai anh')
        res = self.client.post(reverse('project_them'), self.du_lieu(AnhBia=gia))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Project.objects.count(), 0)

    def test_hinh_trong_project_khong_hop_le(self):
        lon = tao_anh('lon.png')
        lon.size = 11 * 1024 * 1024
        form = self.kiem_tra_form(anh_moi=[tao_anh('a.png'), lon])
        self.assertFalse(form.is_valid())
        self.assertTrue(any('mỗi hình không được lớn hơn 10MB' in e for e in form.errors['anh_moi']))
        form = self.kiem_tra_form(anh_moi=[tao_anh('a.png'), tao_anh('b.gif', 'GIF')])
        self.assertFalse(form.is_valid())
        self.assertTrue(any('Chỉ nhận ảnh JPG' in e for e in form.errors['anh_moi']))
        self.assertEqual(Project.objects.count(), 0)

    def test_toi_da_30_hinh(self):
        res = self.client.post(reverse('project_them'),
                               self.du_lieu(anh_moi=[tao_anh(f'h{i}.png') for i in range(31)]))
        self.assertContains(res, 'Mỗi project tối đa 30 hình.')
        self.assertEqual(Project.objects.count(), 0)

    # ---- sửa ----
    def test_hien_form_sua_co_san_du_lieu_va_danh_sach_hinh(self):
        project = self.tao_project(self.nag, 'Dạo phố Sài Gòn')
        res = self.client.get(reverse('project_sua', args=[project.pk]))
        self.assertContains(res, 'Chỉnh sửa project')
        self.assertContains(res, 'Dạo phố Sài Gòn')
        self.assertContains(res, 'Thứ tự và danh sách hình')
        for h, vi_tri in self.thu_tu(project):
            self.assertContains(res, f'name="thu_tu_{h}" value="{vi_tri}"')
            self.assertContains(res, f'name="xoa_hinh" value="{h}"')

    def test_sua_thong_tin_giu_nguyen_anh(self):
        project = self.tao_project(self.nag)
        bia_cu = project.AnhBia.name
        data = self.du_lieu(TenProject='Tên mới', MaLoaiHinh=self.chan_dung.pk)
        del data['AnhBia'], data['anh_moi']
        res = self.client.post(reverse('project_sua', args=[project.pk]), data)
        self.assertRedirects(res, reverse('portfolio'))
        project.refresh_from_db()
        self.assertEqual(project.TenProject, 'Tên mới')
        self.assertEqual(project.MaLoaiHinh, self.chan_dung)
        self.assertEqual(project.AnhBia.name, bia_cu)
        self.assertEqual(project.hinh_anh.count(), 3)
        self.assertIsNotNone(project.NgayCapNhat)

    def test_sua_them_hinh_noi_vao_cuoi(self):
        project = self.tao_project(self.nag, so_hinh=2)
        data = self.du_lieu(anh_moi=[tao_anh('moi1.png'), tao_anh('moi2.png')])
        del data['AnhBia']
        self.client.post(reverse('project_sua', args=[project.pk]), data)
        self.assertEqual([t for _, t in self.thu_tu(project)], [1, 2, 3, 4])

    def test_thay_anh_bia_xoa_file_cu(self):
        project = self.tao_project(self.nag)
        bia_cu = project.AnhBia.name
        data = self.du_lieu(AnhBia=tao_anh('bia_moi.png'))
        del data['anh_moi']
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('project_sua', args=[project.pk]), data)
        project.refresh_from_db()
        self.assertNotEqual(project.AnhBia.name, bia_cu)
        self.assertTrue(project.AnhBia.storage.exists(project.AnhBia.name))
        self.assertFalse(project.AnhBia.storage.exists(bia_cu))

    def test_sua_loi_khong_luu(self):
        project = self.tao_project(self.nag, 'Giữ nguyên')
        data = self.du_lieu(TenProject='')
        del data['AnhBia'], data['anh_moi']
        res = self.client.post(reverse('project_sua', args=[project.pk]), data)
        self.assertContains(res, 'Vui lòng nhập tên project.')
        project.refresh_from_db()
        self.assertEqual(project.TenProject, 'Giữ nguyên')

    # ---- chỉ động được vào của mình ----
    def test_khong_dong_vao_project_cua_nguoi_khac(self):
        khac = self.tao_project(self.nag2, 'Của người khác')
        hinh = khac.hinh_anh.first()
        mine = self.tao_project(self.nag, 'Của tôi')
        self.assertEqual(self.client.get(reverse('project_sua', args=[khac.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('project_sua', args=[khac.pk]), self.du_lieu()).status_code, 404)
        self.assertEqual(self.client.get(reverse('project_xoa', args=[khac.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('project_xoa', args=[khac.pk])).status_code, 404)
        self.assertTrue(Project.objects.filter(pk=khac.pk).exists())
        self.assertEqual(khac.hinh_anh.count(), 3)
        # Gửi kèm mã hình của project KHÁC vào form sửa project của mình: bị bỏ qua, hình kia còn nguyên
        data = self.du_lieu(xoa_hinh=[hinh.pk], anh_moi=[])
        del data['AnhBia']
        self.client.post(reverse('project_sua', args=[mine.pk]), data)
        self.assertTrue(HinhAnhProject.objects.filter(pk=hinh.pk).exists())
        self.assertEqual(mine.hinh_anh.count(), 3)

    # ---- sắp xếp hình (gõ số hoặc kéo thả: trình duyệt đều gửi lên các ô thu_tu_<mã hình>) ----
    def sua(self, project, **doi):
        """Gửi form sửa project, giữ nguyên ảnh bìa, không thêm hình mới (trừ khi truyền anh_moi)."""
        data = self.du_lieu(anh_moi=[], **doi)
        del data['AnhBia']
        return self.client.post(reverse('project_sua', args=[project.pk]), data)

    def test_doi_thu_tu_bang_so(self):
        project = self.tao_project(self.nag)
        h1, h2, h3 = [p for p, _ in self.thu_tu(project)]
        res = self.sua(project, **{f'thu_tu_{h1}': 3, f'thu_tu_{h2}': 1, f'thu_tu_{h3}': 2})
        self.assertRedirects(res, reverse('portfolio'))
        self.assertEqual(self.thu_tu(project), [(h2, 1), (h3, 2), (h1, 3)])

    def test_dua_hinh_cuoi_len_dau(self):
        project = self.tao_project(self.nag)
        h1, h2, h3 = [p for p, _ in self.thu_tu(project)]
        self.sua(project, **{f'thu_tu_{h3}': 1})                 # chỉ nhập một ô, hai ô kia giữ vị trí cũ
        self.assertEqual(self.thu_tu(project), [(h3, 1), (h1, 2), (h2, 3)])

    def test_so_trung_hoac_qua_lon_van_ra_thu_tu_hop_le(self):
        project = self.tao_project(self.nag)
        h1, h2, h3 = [p for p, _ in self.thu_tu(project)]
        self.sua(project, **{f'thu_tu_{h1}': 99, f'thu_tu_{h2}': 2, f'thu_tu_{h3}': 2})
        thu_tu = self.thu_tu(project)
        self.assertEqual([t for _, t in thu_tu], [1, 2, 3])        # luôn 1..n, không trùng
        self.assertEqual([p for p, _ in thu_tu], [h2, h3, h1])     # 99 về cuối; trùng số thì giữ thứ tự cũ

    def test_khong_gui_so_thi_giu_nguyen_thu_tu(self):
        project = self.tao_project(self.nag)
        truoc = self.thu_tu(project)
        self.sua(project)
        self.assertEqual(self.thu_tu(project), truoc)

    def test_so_thu_tu_khong_hop_le(self):
        project = self.tao_project(self.nag)
        h1 = project.hinh_anh.first().pk
        for xau in ('abc', '0', '-2', '1.5', '١'):
            res = self.sua(project, TenProject='Không được lưu', **{f'thu_tu_{h1}': xau})
            self.assertEqual(res.status_code, 200, xau)
            self.assertContains(res, 'Thứ tự hình phải là số nguyên từ 1 trở lên.')
        project.refresh_from_db()
        self.assertNotEqual(project.TenProject, 'Không được lưu')

    def test_sap_xep_roi_them_hinh_moi_nam_cuoi(self):
        project = self.tao_project(self.nag, so_hinh=2)
        h1, h2 = [p for p, _ in self.thu_tu(project)]
        data = self.du_lieu(anh_moi=[tao_anh('moi.png')], **{f'thu_tu_{h1}': 2, f'thu_tu_{h2}': 1})
        del data['AnhBia']
        self.client.post(reverse('project_sua', args=[project.pk]), data)
        thu_tu = self.thu_tu(project)
        self.assertEqual([p for p, _ in thu_tu[:2]], [h2, h1])
        self.assertEqual([t for _, t in thu_tu], [1, 2, 3])

    def test_form_loi_hien_lai_van_giu_so_vua_nhap(self):
        project = self.tao_project(self.nag)
        h1, h2, h3 = [p for p, _ in self.thu_tu(project)]
        res = self.sua(project, TenProject='', **{f'thu_tu_{h3}': 1, f'xoa_hinh': [h2]})
        self.assertContains(res, 'Vui lòng nhập tên project.')
        self.assertContains(res, f'name="thu_tu_{h3}" value="1"')    # hình 3 vẫn đứng đầu
        self.assertContains(res, f'value="{h2}" checked')            # dấu Xóa của hình 2 còn nguyên
        self.assertEqual(self.thu_tu(project), [(h1, 1), (h2, 2), (h3, 3)])   # nhưng chưa lưu gì

    # ---- gỡ hình (tick Xóa rồi bấm Lưu) ----
    def test_tick_xoa_hinh_giua_thi_danh_so_lai_va_xoa_file(self):
        project = self.tao_project(self.nag)
        h1, h2, h3 = [p for p, _ in self.thu_tu(project)]
        file_h2 = HinhAnhProject.objects.get(pk=h2).DuongDanHinhAnh
        ten_file, kho = file_h2.name, file_h2.storage
        with self.captureOnCommitCallbacks(execute=True):
            res = self.sua(project, xoa_hinh=[h2])
        self.assertRedirects(res, reverse('portfolio'))
        self.assertEqual(self.thu_tu(project), [(h1, 1), (h3, 2)])
        self.assertFalse(kho.exists(ten_file))

    def test_vua_xoa_vua_sap_xep(self):
        project = self.tao_project(self.nag, so_hinh=4)
        h1, h2, h3, h4 = [p for p, _ in self.thu_tu(project)]
        self.sua(project, xoa_hinh=[h2], **{f'thu_tu_{h4}': 1, f'thu_tu_{h1}': 3})
        self.assertEqual(self.thu_tu(project), [(h4, 1), (h3, 2), (h1, 3)])

    def test_khong_xoa_het_hinh(self):
        project = self.tao_project(self.nag, so_hinh=2)
        cac_hinh = [p for p, _ in self.thu_tu(project)]
        res = self.sua(project, xoa_hinh=cac_hinh)
        self.assertContains(res, 'Vui lòng giữ hoặc tải lên ít nhất một hình cho project.')
        self.assertEqual(project.hinh_anh.count(), 2)

    def test_xoa_het_hinh_cu_nhung_them_hinh_moi_thi_duoc(self):
        project = self.tao_project(self.nag, so_hinh=2)
        cac_hinh = [p for p, _ in self.thu_tu(project)]
        data = self.du_lieu(anh_moi=[tao_anh('moi.png')], xoa_hinh=cac_hinh)
        del data['AnhBia']
        self.client.post(reverse('project_sua', args=[project.pk]), data)
        self.assertEqual(project.hinh_anh.count(), 1)
        self.assertEqual([t for _, t in self.thu_tu(project)], [1])

    # ---- xóa project ----
    def test_hien_hop_xac_nhan_xoa(self):
        project = self.tao_project(self.nag, 'Chân dung studio')
        res = self.client.get(reverse('project_xoa', args=[project.pk]))
        self.assertContains(res, 'Bạn có chắc muốn xóa project')
        self.assertContains(res, 'Chân dung studio')
        self.assertContains(res, 'Toàn bộ hình ảnh trong project sẽ bị xóa khỏi Portfolio.')
        self.assertTrue(Project.objects.filter(pk=project.pk).exists())     # mở trang hỏi chưa xóa

    def test_xoa_project_xoa_luon_hinh_va_file(self):
        project = self.tao_project(self.nag)
        con_lai = self.tao_project(self.nag, 'Giữ lại')
        cac_file = [(project.AnhBia.storage, project.AnhBia.name)] + [
            (h.DuongDanHinhAnh.storage, h.DuongDanHinhAnh.name) for h in project.hinh_anh.all()]
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.post(reverse('project_xoa', args=[project.pk]))
        self.assertRedirects(res, reverse('portfolio'))
        self.assertTrue(any('Đã xóa project' in t for t in self.tin_nhan(res)))
        self.assertFalse(Project.objects.filter(pk=project.pk).exists())
        self.assertFalse(HinhAnhProject.objects.filter(MaProject_id=project.pk).exists())
        for kho, ten in cac_file:
            self.assertFalse(kho.exists(ten))
        self.assertTrue(Project.objects.filter(pk=con_lai.pk).exists())
        self.assertEqual(con_lai.hinh_anh.count(), 3)
        self.assertTrue(con_lai.AnhBia.storage.exists(con_lai.AnhBia.name))
