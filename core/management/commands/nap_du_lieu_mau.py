# =====================================================================
# core/management/commands/nap_du_lieu_mau.py   (task B5)
# Lệnh nạp DỮ LIỆU MẪU cho FRAMIE.
#
#   python manage.py nap_du_lieu_mau                 xóa dữ liệu mẫu cũ (nếu có) rồi nạp mới
#   python manage.py nap_du_lieu_mau --chi-xoa        chỉ xóa dữ liệu mẫu
#   python manage.py nap_du_lieu_mau --khong-danh-gia-nen   bỏ 14 Booking nền (chỉ còn BK01..BK17)
#
# Dữ liệu mẫu nhận biết bằng email có đuôi @example.com, nên lệnh KHÔNG đụng vào tài
# khoản thật bạn tự tạo. Danh mục (loại hình, phong cách, khu vực) được giữ lại, chỉ
# thêm nếu chưa có. Mọi dữ liệu và mốc thời gian nằm ở _du_lieu_mau.py.
# =====================================================================
import unicodedata
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError, RestrictedError
from django.utils import timezone

from accounts.models import YeuCauDatLaiMatKhau
from bookings.models import Booking, GiuCho, LichSuTrangThaiBooking, YeuCauHuy
from core.constants import (HOAN_TAT_BAN_GIAO, DinhDangTep, KetQuaDuyetHoSo,
                            KetQuaTaiAnh, LoaiAnh, LoaiThanhToan, LuuTruAnh,
                            TrangThaiGiuCho, TrangThaiGoi, TrangThaiHoSo, TrangThaiSlot,
                            VaiTro)
from delivery.models import (Anh, BanGiao, LichSuTaiAnh, YeuCauChinhSua,
                             YeuCauChinhSua_Anh)
from notifications.models import ThongBao
from payments.models import MinhChungThanhToan, ThanhToan
from profiles.models import (DuyetHoSo, GoiDichVu, HinhAnhProject, KhuVuc,
                             LoaiHinhChup, NhiepAnhGia, NhiepAnhGia_KhuVuc,
                             NhiepAnhGia_LoaiHinhChup, NhiepAnhGia_PhongCach,
                             PhongCach, Project)
from reviews.models import DanhGia
from schedule.models import LichKhaDung

from . import _du_lieu_mau as dl

User = get_user_model()

# Màu thương hiệu đơn sắc: #1A1A1A, #D9D9D9, trắng (và các độ xám ở giữa)
XAM = ['#1A1A1A', '#4D4D4D', '#8C8C8C', '#BFBFBF', '#D9D9D9']


# ---------------------------------------------------------------------
# Ảnh giữ chỗ (placeholder) vẽ bằng Pillow
# ---------------------------------------------------------------------
def _bo_dau(s):
    s = unicodedata.normalize('NFD', s)
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn').replace('đ', 'd').replace('Đ', 'D')


def _font(co):
    from PIL import ImageFont
    for ten in ('DejaVuSans.ttf', 'arial.ttf', 'Arial.ttf', 'segoeui.ttf',
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(ten, co), True
        except OSError:
            continue
    try:
        return ImageFont.load_default(co), False
    except TypeError:                      # Pillow cũ không nhận tham số size
        return ImageFont.load_default(), False


def ve_anh(duong_dan, rong, cao, chi_so, dong1, dong2='', watermark=False):
    """Vẽ một ảnh giữ chỗ màu xám thương hiệu, ghi chữ giữa ảnh. Trả về kích thước file (byte)."""
    from PIL import Image, ImageDraw
    nen = XAM[chi_so % len(XAM)]
    toi = chi_so % len(XAM) <= 2
    mau_chu = '#FFFFFF' if toi else '#1A1A1A'
    img = Image.new('RGB', (rong, cao), nen)
    d = ImageDraw.Draw(img)
    d.rectangle([10, 10, rong - 11, cao - 11], outline=mau_chu, width=2)
    f1, co_dau = _font(max(14, cao // 9))
    f2, _ = _font(max(11, cao // 16))
    if not co_dau:
        dong1, dong2 = _bo_dau(dong1), _bo_dau(dong2)
    for text, f, y in ((dong1, f1, cao * 0.40), (dong2, f2, cao * 0.58)):
        if text:
            w = d.textlength(text, font=f)
            d.text(((rong - w) / 2, y), text, fill=mau_chu, font=f)
    if watermark:                          # watermark đơn giản: chữ FRAMIE lặp trên ảnh
        fw, _ = _font(max(12, cao // 12))
        for yy in range(int(cao * 0.1), cao, max(40, cao // 4)):
            for xx in range(int(rong * 0.05), rong, max(120, rong // 3)):
                d.text((xx, yy), 'FRAMIE', fill=('#BFBFBF' if toi else '#4D4D4D'), font=fw)
    Path(duong_dan).parent.mkdir(parents=True, exist_ok=True)
    if str(duong_dan).lower().endswith(('.jpg', '.jpeg')):
        img.save(duong_dan, 'JPEG', quality=80)
    else:
        img.save(duong_dan, 'PNG')
    return Path(duong_dan).stat().st_size


class Command(BaseCommand):
    help = 'Xóa và nạp lại dữ liệu mẫu FRAMIE (10 nhiếp ảnh gia, 8 khách hàng, 17 Booking mẫu...).'

    def add_arguments(self, parser):
        parser.add_argument('--chi-xoa', action='store_true', help='Chỉ xóa dữ liệu mẫu, không nạp lại.')
        parser.add_argument('--khong-danh-gia-nen', action='store_true',
                            help='Không tạo 14 Booking nền đã hoàn thành + đánh giá (chỉ còn BK01..BK17).')

    # -----------------------------------------------------------------
    def handle(self, *args, **opts):
        self.media = Path(settings.MEDIA_ROOT)
        self.rieng = Path(getattr(settings, 'PRIVATE_MEDIA_ROOT', Path(settings.BASE_DIR) / 'private_media'))
        try:
            with transaction.atomic():
                self.xoa()
                if opts['chi_xoa']:
                    self.stdout.write(self.style.SUCCESS('Đã xóa dữ liệu mẫu.'))
                    return
                self.now = timezone.now()
                self.nap(co_nen=not opts['khong_danh_gia_nen'])
        except (ProtectedError, RestrictedError) as e:
            raise CommandError(
                'Không xóa được dữ liệu mẫu cũ vì còn bản ghi khác (do bạn tự tạo) đang trỏ tới nó:\n'
                f'{e}\nHãy xóa các bản ghi đó trong trang quản trị rồi chạy lại.')
        self.in_tom_tat(co_nen=not opts['khong_danh_gia_nen'])

    # -----------------------------------------------------------------
    # XÓA
    # -----------------------------------------------------------------
    def xoa(self):
        users = User.objects.filter(email__iendswith=dl.DUOI_EMAIL)
        ids = list(users.values_list('pk', flat=True))
        nag_q = Q(MaNhiepAnhGia__MaTaiKhoan__in=ids)
        bk = Booking.objects.filter(Q(MaKhachHang__in=ids) | nag_q)
        # Xóa từ bảng "con" lên bảng "cha" vì các khóa ngoại đều chặn xóa (PROTECT/RESTRICT).
        DanhGia.objects.filter(MaBooking__in=bk).delete()
        LichSuTaiAnh.objects.filter(MaAnh__MaBooking__in=bk).delete()
        YeuCauChinhSua_Anh.objects.filter(MaYeuCauChinhSua__MaBooking__in=bk).delete()
        YeuCauChinhSua.objects.filter(MaBooking__in=bk).delete()
        Anh.objects.filter(MaBooking__in=bk).delete()
        BanGiao.objects.filter(MaBooking__in=bk).delete()
        MinhChungThanhToan.objects.filter(MaThanhToan__MaBooking__in=bk).delete()
        ThanhToan.objects.filter(MaBooking__in=bk).delete()
        YeuCauHuy.objects.filter(MaBooking__in=bk).delete()
        LichSuTrangThaiBooking.objects.filter(MaBooking__in=bk).delete()
        ThongBao.objects.filter(Q(MaNguoiNhan__in=ids) | Q(MaBooking__in=bk)).delete()
        bk.delete()
        GiuCho.objects.filter(Q(MaKhachHang__in=ids) | Q(MaLich__MaNhiepAnhGia__MaTaiKhoan__in=ids)).delete()
        LichKhaDung.objects.filter(nag_q).delete()
        DuyetHoSo.objects.filter(Q(MaNhiepAnhGia__MaTaiKhoan__in=ids) | Q(MaQuanTriVien__in=ids)).delete()
        HinhAnhProject.objects.filter(MaProject__MaNhiepAnhGia__MaTaiKhoan__in=ids).delete()
        Project.objects.filter(nag_q).delete()
        GoiDichVu.objects.filter(nag_q).delete()
        NhiepAnhGia.objects.filter(MaTaiKhoan__in=ids).delete()   # các bảng nối tự xóa theo (CASCADE)
        YeuCauDatLaiMatKhau.objects.filter(MaTaiKhoan__in=ids).delete()
        users.delete()
        # file ảnh mẫu (chỉ file tên mau_*, không đụng ảnh thật)
        for thu_muc in ('avatars', 'qr', 'portfolio'):
            for f in (self.media / thu_muc).glob('mau_*'):
                f.unlink(missing_ok=True)
        import shutil
        shutil.rmtree(self.rieng / 'mau', ignore_errors=True)

    # -----------------------------------------------------------------
    # NẠP
    # -----------------------------------------------------------------
    def nap(self, co_nen):
        now = self.now
        self.kiem_tra_trung()
        self.nap_nhom_va_danh_muc()
        self.nap_nguoi_dung()
        self.nap_ho_so_va_duyet()
        self.nap_goi_va_project()
        bk = dl.lich_booking(now)
        nen = dl.lich_nen(now) if co_nen else []
        self.nap_khung_gio(bk, nen)
        for b in bk + nen:
            self.nap_booking(b)
        self.nap_giu_cho_het_han()
        self.nap_thong_bao()

    def kiem_tra_trung(self):
        """Email/số điện thoại là duy nhất: báo rõ nếu trùng với tài khoản THẬT của bạn."""
        for p in dl.NHIEP_ANH_GIA + dl.KHACH_HANG + [dl.QUAN_TRI_VIEN]:
            if User.objects.filter(Q(email=dl.email_cua(p['user'])) | Q(so_dien_thoai=p['sdt'])
                                   | Q(username=p['user'])).exists():
                raise CommandError(f'Tài khoản thật của bạn đang dùng trùng username/email/số điện thoại '
                                   f'của dữ liệu mẫu "{p["user"]}" ({p["sdt"]}). Hãy đổi hoặc xóa tài khoản đó.')

    def nap_nhom_va_danh_muc(self):
        self.nhom = {}
        for ten in (VaiTro.KHACH_HANG, VaiTro.NHIEP_ANH_GIA, VaiTro.QUAN_TRI_VIEN):
            self.nhom[ten], _ = Group.objects.get_or_create(name=ten)
        self.loai_hinh = [LoaiHinhChup.objects.get_or_create(TenLoaiHinh=t)[0] for t in dl.LOAI_HINH]
        self.phong_cach = [PhongCach.objects.get_or_create(TenPhongCach=t)[0] for t in dl.PHONG_CACH]
        self.khu_vuc = [KhuVuc.objects.get_or_create(TenKhuVuc=t)[0] for t in dl.KHU_VUC]

    def tao_user(self, p, vai_tro, trang_thai_ho_so=None, **extra):
        u = User(username=p['user'], email=dl.email_cua(p['user']), first_name=p['ten'], last_name=p['ho'],
                 so_dien_thoai=p['sdt'], trang_thai_ho_so=trang_thai_ho_so, **extra)
        u.set_password(dl.MAT_KHAU_MAU)           # lưu dạng đã mã hóa như mọi tài khoản Django
        u.save()
        u.groups.add(self.nhom[vai_tro])
        return u

    def nap_nguoi_dung(self):
        self.admin = self.tao_user(dl.QUAN_TRI_VIEN, VaiTro.QUAN_TRI_VIEN, is_staff=True, is_superuser=True)
        self.khach = [self.tao_user(p, VaiTro.KHACH_HANG) for p in dl.KHACH_HANG]
        self.user_nag = [self.tao_user(p, VaiTro.NHIEP_ANH_GIA, trang_thai_ho_so=p['hs'])
                         for p in dl.NHIEP_ANH_GIA]

    def nap_ho_so_va_duyet(self):
        now = self.now
        self.nag = []
        for i, p in enumerate(dl.NHIEP_ANH_GIA):
            ten_dd = f'avatars/mau_nag{i + 1:02d}.png'
            ten_qr = f'qr/mau_qr_nag{i + 1:02d}.png'
            ve_anh(self.media / ten_dd, 400, 400, i, f'{p["ten"]}', 'Ảnh đại diện mẫu')
            ve_anh(self.media / ten_qr, 360, 360, 4, 'QR mẫu', p['nh'])
            n = NhiepAnhGia.objects.create(
                MaTaiKhoan=self.user_nag[i], AnhDaiDien=ten_dd, GioiThieu=dl.GIOI_THIEU[i],
                NganHang=p['nh'], SoTaiKhoan=p['stk'], ChuTaiKhoan=_bo_dau(f'{p["ho"]} {p["ten"]}').upper(),
                AnhMaQR=ten_qr)
            for k in p['loai']:
                NhiepAnhGia_LoaiHinhChup.objects.create(MaNhiepAnhGia=n, MaLoaiHinh=self.loai_hinh[k])
            for k in p['pc']:
                NhiepAnhGia_PhongCach.objects.create(MaNhiepAnhGia=n, MaPhongCach=self.phong_cach[k])
            for k in p['kv']:
                NhiepAnhGia_KhuVuc.objects.create(MaNhiepAnhGia=n, MaKhuVuc=self.khu_vuc[k])
            self.nag.append(n)
            # --- các lượt duyệt hồ sơ ---
            if p['hs'] == TrangThaiHoSo.DA_DUYET:
                if i == 1:    # NAG số 2: lần 1 bị yêu cầu chỉnh sửa, lần 2 được duyệt (để xem lịch sử)
                    DuyetHoSo.objects.create(
                        MaNhiepAnhGia=n, MaQuanTriVien=self.admin, LanNop=1, ThoiDiemNop=now - dl.timedelta(days=40),
                        ThoiDiemDuyet=now - dl.timedelta(days=39), KetQua=KetQuaDuyetHoSo.YEU_CAU_CHINH_SUA,
                        NoiDungPhanHoi='Vui lòng bổ sung thêm ảnh vào project và cập nhật ảnh mã QR rõ nét hơn.')
                    DuyetHoSo.objects.create(
                        MaNhiepAnhGia=n, MaQuanTriVien=self.admin, LanNop=2, ThoiDiemNop=now - dl.timedelta(days=38),
                        ThoiDiemDuyet=now - dl.timedelta(days=37), KetQua=KetQuaDuyetHoSo.DA_DUYET)
                else:
                    DuyetHoSo.objects.create(
                        MaNhiepAnhGia=n, MaQuanTriVien=self.admin, LanNop=1, ThoiDiemNop=now - dl.timedelta(days=60),
                        ThoiDiemDuyet=now - dl.timedelta(days=59), KetQua=KetQuaDuyetHoSo.DA_DUYET)
            elif p['hs'] == TrangThaiHoSo.CHO_DUYET:
                DuyetHoSo.objects.create(MaNhiepAnhGia=n, LanNop=1, ThoiDiemNop=now - dl.timedelta(days=1))
            else:
                DuyetHoSo.objects.create(
                    MaNhiepAnhGia=n, MaQuanTriVien=self.admin, LanNop=1, ThoiDiemNop=now - dl.timedelta(days=5),
                    ThoiDiemDuyet=now - dl.timedelta(days=4), KetQua=KetQuaDuyetHoSo.DA_TU_CHOI,
                    NoiDungPhanHoi='Thông tin tài khoản ngân hàng chưa khớp với tên chủ tài khoản.')
        # chắc chắn trạng thái hồ sơ trong User khớp với lượt duyệt mới nhất
        for i, p in enumerate(dl.NHIEP_ANH_GIA):
            User.objects.filter(pk=self.user_nag[i].pk).update(trang_thai_ho_so=p['hs'])

    def nap_goi_va_project(self):
        self.goi = {}                    # chỉ số NAG -> {'gioi_han': GoiDichVu, 'toan_bo': GoiDichVu}
        for i in range(dl.SO_NAG_DA_DUYET):
            n = self.nag[i]
            self.goi[i] = {}
            for g in dl.goi_cua(i):
                obj = GoiDichVu.objects.create(
                    MaNhiepAnhGia=n, MaLoaiHinh=self.loai_hinh[g['loai_hinh']], TenGoi=g['ten'],
                    MoTa=f'Gói {g["ten"].lower()}, thời lượng {g["thoi_luong"]} phút.',
                    Gia=g['gia'], ThoiLuongChup=g['thoi_luong'], LoaiHauKy=g['hau_ky'],
                    SoAnhHauKyToiDa=g['so_anh'], TrangThai=g['trang_thai'])
                if g['trang_thai'] == TrangThaiGoi.DANG_AP_DUNG:
                    self.goi[i]['gioi_han' if g['so_anh'] else 'toan_bo'] = obj
            for j, pr in enumerate(dl.project_cua(i, self.now)):
                p = Project.objects.create(
                    MaNhiepAnhGia=n, MaLoaiHinh=self.loai_hinh[pr['loai_hinh']], TenProject=pr['ten'],
                    Concept=pr['concept'], NgayChup=pr['ngay_chup'],
                    AnhBia=f'portfolio/mau_p{i + 1:02d}_{j + 1}_bia.png')
                ve_anh(self.media / f'portfolio/mau_p{i + 1:02d}_{j + 1}_bia.png', 800, 600, i + j,
                       pr['ten'], 'Ảnh bìa mẫu')
                for k in range(1, pr['so_anh'] + 1):
                    ten = f'portfolio/mau_p{i + 1:02d}_{j + 1}_{k:02d}.png'
                    ve_anh(self.media / ten, 800, 600, i + j + k, pr['ten'], f'Ảnh {k}/{pr["so_anh"]}')
                    HinhAnhProject.objects.create(MaProject=p, DuongDanHinhAnh=ten, ThuTu=k)

    def nap_khung_gio(self, bk, nen):
        self.slot = {}                   # mã booking -> LichKhaDung
        for s in dl.lich_khung_gio(bk, nen, self.now):
            obj = LichKhaDung.objects.create(
                MaNhiepAnhGia=self.nag[s['nag']], Ngay=s['ngay'], GioBatDau=s['bat_dau'],
                GioKetThuc=s['ket_thuc'], TrangThai=s['trang_thai'])
            if s['ma_booking']:
                self.slot[s['ma_booking']] = obj

    # -----------------------------------------------------------------
    def nap_booking(self, b):
        goi = self.goi[b['nag']]['gioi_han' if b['gioi_han'] else 'toan_bo']
        slot = self.slot[b['ma']]
        khach = self.khach[b['khach']]
        bk = Booking.objects.create(
            MaKhachHang=khach, MaNhiepAnhGia=self.nag[b['nag']], MaGoi=goi, MaLich=slot,
            NgayGioChup=b['chup'], DiaDiem=b['dia_diem'], SoNguoi=b['so_nguoi'], Concept=b['concept'],
            YeuCauRieng=b['yeu_cau'], TrangThai=b['trang_thai'], HanDatCoc=b['han_coc'],
            HanChonAnh=b['han_chon'], HanHauKy=b['han_hau_ky'], HanThanhToanConLai=b['han_tt'],
            TongGiaTri=goi.Gia, LyDoTuChoi=b['ly_do_tu_choi'], NgayTao=b['tao'])
        ma = b['ma']
        if b['co_giu_cho']:
            GiuCho.objects.create(MaKhachHang=khach, MaLich=slot, ThoiDiemGiu=b['tao'] - dl.timedelta(minutes=3),
                                  ThoiDiemHetHan=b['tao'] + dl.timedelta(minutes=2),
                                  TrangThai=TrangThaiGiuCho.DA_HOAN_TAT)
        for cu, moi, luc, ben, ly_do in b['lich_su']:
            LichSuTrangThaiBooking.objects.create(MaBooking=bk, TrangThaiCu=cu, TrangThaiMoi=moi,
                                                  ThoiDiemThayDoi=luc, BenThucHien=ben, LyDo=ly_do)
        # --- thanh toán: cọc 40% (làm tròn), còn lại 60% ---
        tong = Decimal(goi.Gia)
        so_coc = (tong * Decimal('0.4')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        for loai, key, so_tien in ((LoaiThanhToan.TIEN_COC, 'coc', so_coc),
                                   (LoaiThanhToan.PHAN_CON_LAI, 'con_lai', tong - so_coc)):
            p = b[key]
            if not p:
                continue
            tt = ThanhToan.objects.create(MaBooking=bk, LoaiThanhToan=loai, SoTien=so_tien,
                                          TrangThai=p['trang_thai'], NgayThanhToan=p['ngay_tt'],
                                          NgayXacNhan=p['ngay_xn'])
            if p['minh_chung'] and not ma.startswith('BKN'):
                ten = f'mau/minh_chung/{ma.lower()}_{key}.png'
                dung_luong = ve_anh(self.rieng / ten, 480, 640, 3, 'Minh chứng mẫu', f'{ma} - {key}')
                MinhChungThanhToan.objects.create(
                    MaThanhToan=tt, TenTep=Path(ten).name, DuongDanTep=ten, DinhDangTep=DinhDangTep.PNG,
                    KichThuocTep=dung_luong, NgayTaiLen=p['ngay_tt'])
        if b['ban_giao']:
            BanGiao.objects.create(MaBooking=bk, NgayXacNhan=b['ban_giao']['ngay_xn'],
                                   TrangThaiBanGiao=HOAN_TAT_BAN_GIAO, ThoiHanTaiAnh=b['ban_giao']['thoi_han'])
        anhs = self.nap_anh(b, bk, goi)
        for yc in b['chinh_sua']:
            y = YeuCauChinhSua.objects.create(MaBooking=bk, NgayYeuCau=yc['ngay'], NoiDung=yc['noi_dung'],
                                              SoLanYeuCau=yc['so_lan'])
            for idx, nd in yc['anh']:
                YeuCauChinhSua_Anh.objects.create(MaYeuCauChinhSua=y, MaAnh=anhs[idx], NoiDungChinhSua=nd)
        for k, (luc, thanh_cong) in enumerate(b['tai_anh']):
            LichSuTaiAnh.objects.create(
                MaAnh=anhs[k % len(anhs)], MaKhachHang=khach, ThoiDiemTaiAnh=luc,
                KetQuaTaiAnh=KetQuaTaiAnh.THANH_CONG if thanh_cong else KetQuaTaiAnh.THAT_BAI)
        if b['huy']:
            h = b['huy']
            YeuCauHuy.objects.create(
                MaBooking=bk, BenYeuCau=h['ben'], LyDo=h['ly_do'], TrangThaiBookingLucHuy=h['trang_thai_luc_huy'],
                XuLyTienCoc=h['xu_ly'], TrangThaiHoanTien=h['hoan_tien'],
                ThoiDiemXacNhanHoanTien=h['ngay_xn_hoan'], ThoiDiemYeuCau=h['ngay'])
        if b['danh_gia']:
            d = b['danh_gia']
            DanhGia.objects.create(MaBooking=bk, MaNhiepAnhGia=self.nag[b['nag']], Diem=d['diem'],
                                   NhanXet=d['nhan_xet'], NgayDanhGia=d['ngay'])
        return bk

    def nap_anh(self, b, bk, goi):
        a = b['anh']
        if not a:
            return []
        chon = a['chon']
        so_chon = goi.SoAnhHauKyToiDa if chon == 'toi_da' else chon
        hoan_chinh = a['loai'] == LoaiAnh.HOAN_CHINH
        da_xoa = a.get('luu_tru') == LuuTruAnh.DA_XOA
        ds = []
        for i in range(a['so_luong']):
            ten_file = f'{b["ma"].lower()}_anh_{i + 1:02d}.jpg'
            duong_dan = f'mau/booking_{b["ma"].lower()}/{ten_file}'
            if da_xoa:
                dung_luong = 150000 + 1000 * i      # file đã bị hệ thống xóa, chỉ còn bản ghi lịch sử
            else:
                dung_luong = ve_anh(self.rieng / duong_dan, 640, 427, i, f'{b["ma"]} - ảnh {i + 1}',
                                    a['loai'], watermark=not hoan_chinh)
            phien_ban = a.get('phien_ban', {}).get(i, 1)
            duong_dan_truoc = None                  # E2: ảnh hậu kỳ từ phiên bản 2 trở đi mới có bản có watermark liền trước
            if phien_ban > 1 and a['loai'] == LoaiAnh.DA_HAU_KY and not da_xoa:
                duong_dan_truoc = f'mau/booking_{b["ma"].lower()}/{ten_file[:-4]}_truoc.jpg'
                ve_anh(self.rieng / duong_dan_truoc, 640, 427, i + 4, f'{b["ma"]} - ảnh {i + 1}',
                       'Bản trước', watermark=True)
            ds.append(Anh.objects.create(
                MaBooking=bk, TenAnh=ten_file, DuongDanAnh=duong_dan, DuongDanAnhTruoc=duong_dan_truoc,
                DinhDangAnh=DinhDangTep.JPG,
                KichThuocAnh=dung_luong, LoaiAnh=a['loai'], PhienBanAnh=phien_ban,
                CoWatermark=0 if hoan_chinh else 1, DuocChonHauKy=1 if i < so_chon else 0,
                TrangThaiLuuTru=LuuTruAnh.DA_XOA if da_xoa else LuuTruAnh.CON_LUU, NgayTaiLen=a['ngay']))
        return ds

    def nap_giu_cho_het_han(self):
        """Một lượt giữ chỗ 'Hết hạn' (khung giờ về Lịch trống) để xem lịch sử giữ chỗ."""
        slot = LichKhaDung.objects.filter(MaNhiepAnhGia=self.nag[0], TrangThai=TrangThaiSlot.TRONG).first()
        if slot:
            luc = self.now - dl.timedelta(days=1)
            GiuCho.objects.create(MaKhachHang=self.khach[0], MaLich=slot, ThoiDiemGiu=luc,
                                  ThoiDiemHetHan=luc + dl.timedelta(minutes=5), TrangThai=TrangThaiGiuCho.HET_HAN)

    def nap_thong_bao(self):
        b1 = Booking.objects.filter(MaNhiepAnhGia=self.nag[0]).order_by('pk').first()
        b2 = Booking.objects.filter(MaKhachHang=self.khach[0]).order_by('pk').first()
        mau = [
            (self.user_nag[0], b1, 'Có yêu cầu đặt lịch mới', 'Một Khách hàng vừa gửi yêu cầu đặt lịch chụp. Hãy xem và phản hồi.'),
            (self.khach[0], b2, 'Booking của bạn đã được chấp nhận', 'Nhiếp ảnh gia đã chấp nhận. Vui lòng đặt cọc trong vòng 1 ngày.'),
            (self.admin, None, 'Có hồ sơ chờ duyệt', 'Có 2 hồ sơ Nhiếp ảnh gia đang chờ bạn xem xét.'),
        ]
        for nguoi, booking, tieu_de, noi_dung in mau:
            ThongBao.objects.create(MaNguoiNhan=nguoi, MaBooking=booking, TieuDe=tieu_de, NoiDung=noi_dung)

    # -----------------------------------------------------------------
    def in_tom_tat(self, co_nen):
        self.stdout.write(self.style.SUCCESS('Đã nạp xong dữ liệu mẫu.'))
        self.stdout.write(f'  Nhiếp ảnh gia: {NhiepAnhGia.objects.filter(MaTaiKhoan__email__iendswith=dl.DUOI_EMAIL).count()}'
                          f' | Khách hàng: {len(dl.KHACH_HANG)} | Booking: {Booking.objects.filter(MaKhachHang__email__iendswith=dl.DUOI_EMAIL).count()}'
                          f'{" (gồm 14 Booking nền đã đánh giá)" if co_nen else ""}')
        self.stdout.write(f'  Mật khẩu chung của mọi tài khoản mẫu: {dl.MAT_KHAU_MAU}')
        self.stdout.write(f'  Quản trị viên: {dl.email_cua(dl.QUAN_TRI_VIEN["user"])}')
        self.stdout.write(f'  Nhiếp ảnh gia đã duyệt: {dl.email_cua("nag01")} ... {dl.email_cua("nag07")}')
        self.stdout.write(f'  Chờ duyệt: nag08, nag09 | Đã từ chối: nag10 | Khách hàng: kh01 ... kh08 (cùng đuôi {dl.DUOI_EMAIL})')
