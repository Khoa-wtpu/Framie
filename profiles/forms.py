# =====================================================================
# profiles/forms.py  -  K2: form hồ sơ nhiếp ảnh gia (Khoa)
# Người dùng form này: Phanh (trang đăng ký Nhiếp ảnh gia, P5), Khoa (K3, "Hồ sơ của tôi").
#
# Cách dùng trong view (Phanh):
#     form = NhiepAnhGiaForm(request.POST or None, request.FILES or None, user=user)
#     if form.is_valid():
#         nag = form.save()          # lưu hồ sơ + 3 danh mục + tạo lượt duyệt -> 'Chờ duyệt'
#
# Form CHỈ lo phần hồ sơ chuyên môn (bảng NHIEPANHGIA). Họ tên, email, số điện thoại,
# mật khẩu thuộc bảng User nên do form đăng ký tài khoản của Phanh xử lý.
# Cập nhật hồ sơ (K3): NhiepAnhGiaForm(..., instance=nag, user=nag.MaTaiKhoan).
# =====================================================================
from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.db.models import Max

from core.constants import VaiTro
from profiles.models import (DuyetHoSo, KhuVuc, LoaiHinhChup, NhiepAnhGia,
                             NhiepAnhGia_KhuVuc, NhiepAnhGia_LoaiHinhChup,
                             NhiepAnhGia_PhongCach, PhongCach)

TOI_DA_ANH = 5 * 1024 * 1024   # ảnh tải lên tối đa 5MB (wireframe: JPG/PNG ≤ 5MB)


def _chon_nhieu(model, nhan):
    # Ô chọn nhiều (hộp tích), bắt buộc chọn ít nhất một.
    return forms.ModelMultipleChoiceField(
        queryset=model.objects.all(), label=nhan,
        widget=forms.CheckboxSelectMultiple,
        error_messages={'required': f'Vui lòng chọn ít nhất một {nhan.lower()}.'})


class NhiepAnhGiaForm(forms.ModelForm):
    loai_hinh = _chon_nhieu(LoaiHinhChup, 'Loại hình chụp')
    phong_cach = _chon_nhieu(PhongCach, 'Phong cách')
    khu_vuc = _chon_nhieu(KhuVuc, 'Khu vực')

    class Meta:
        model = NhiepAnhGia
        fields = ['AnhDaiDien', 'GioiThieu', 'NganHang', 'SoTaiKhoan', 'ChuTaiKhoan', 'AnhMaQR']
        widgets = {'GioiThieu': forms.Textarea(attrs={'rows': 5})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # user: tài khoản sở hữu hồ sơ. Khi sửa hồ sơ có sẵn thì lấy từ chính hồ sơ.
        self.user = user or (self.instance.MaTaiKhoan if self.instance.pk else None)
        # Sửa hồ sơ: điền sẵn 3 ô chọn nhiều theo dữ liệu hiện có.
        if self.instance.pk and not self.is_bound:
            self.initial['loai_hinh'] = list(self.instance.loai_hinh_chup.values_list('pk', flat=True))
            self.initial['phong_cach'] = list(self.instance.phong_cach.values_list('pk', flat=True))
            self.initial['khu_vuc'] = list(self.instance.khu_vuc.values_list('pk', flat=True))

    def _kiem_tra_dung_luong(self, ten_truong):
        tep = self.cleaned_data.get(ten_truong)
        # Chỉ kiểm tra file MỚI tải lên (khi giữ ảnh cũ thì tep không phải UploadedFile).
        if isinstance(tep, UploadedFile) and tep.size > TOI_DA_ANH:
            raise forms.ValidationError('Ảnh không được lớn hơn 5MB.')
        return tep

    def clean_AnhDaiDien(self):
        return self._kiem_tra_dung_luong('AnhDaiDien')

    def clean_AnhMaQR(self):
        return self._kiem_tra_dung_luong('AnhMaQR')

    def clean(self):
        data = super().clean()
        # Phải là tài khoản thuộc nhóm Nhiếp ảnh gia (Data Dictionary: kiểm tra ở tầng ứng dụng).
        # Với đăng ký mới, view phải gán nhóm này cho User TRƯỚC khi gọi is_valid().
        if self.user is None:
            raise forms.ValidationError('Thiếu tài khoản của nhiếp ảnh gia.')
        if not self.user.groups.filter(name=VaiTro.NHIEP_ANH_GIA).exists():
            raise forms.ValidationError('Tài khoản này không thuộc nhóm Nhiếp ảnh gia.')
        return data

    def save(self, commit=True):
        # Lưu hồ sơ + 3 bảng nối + tạo lượt duyệt trong CÙNG một giao dịch: lỗi giữa chừng thì hoàn tác hết.
        with transaction.atomic():
            nag = super().save(commit=False)
            if nag.pk is None:
                nag.MaTaiKhoan = self.user
            nag.save()
            self._luu_lien_ket(nag, NhiepAnhGia_LoaiHinhChup, 'MaLoaiHinh', 'loai_hinh')
            self._luu_lien_ket(nag, NhiepAnhGia_PhongCach, 'MaPhongCach', 'phong_cach')
            self._luu_lien_ket(nag, NhiepAnhGia_KhuVuc, 'MaKhuVuc', 'khu_vuc')
            self._nop_ho_so(nag)
        return nag

    def _luu_lien_ket(self, nag, bang_noi, cot, ten_truong):
        # Đồng bộ bảng nối với các mục đã chọn: xóa mục bỏ chọn, thêm mục mới chọn.
        da_chon = list(self.cleaned_data[ten_truong])
        bang_noi.objects.filter(MaNhiepAnhGia=nag).exclude(**{cot + '__in': da_chon}).delete()
        da_co = set(bang_noi.objects.filter(MaNhiepAnhGia=nag).values_list(cot, flat=True))
        bang_noi.objects.bulk_create([
            bang_noi(MaNhiepAnhGia=nag, **{cot: muc}) for muc in da_chon if muc.pk not in da_co])

    def _nop_ho_so(self, nag):
        # Gửi / cập nhật hồ sơ -> trạng thái 'Chờ duyệt'.
        # DuyetHoSo.save() tự đồng bộ User.trang_thai_ho_so = 'Chờ duyệt'.
        moi_nhat = DuyetHoSo.objects.filter(MaNhiepAnhGia=nag).order_by('-LanNop').first()
        if moi_nhat is not None and moi_nhat.KetQua is None:
            return   # đang có lượt chờ xử lý: không tạo thêm lượt thứ hai
        lan = (DuyetHoSo.objects.filter(MaNhiepAnhGia=nag)
               .aggregate(m=Max('LanNop'))['m'] or 0) + 1
        DuyetHoSo.objects.create(MaNhiepAnhGia=nag, LanNop=lan)