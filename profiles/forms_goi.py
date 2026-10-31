# =====================================================================
# profiles/forms_goi.py  -  K6: form thêm / sửa gói dịch vụ (UC1.4) (Khoa)
#
#   GoiForm(request.POST or None, nag=nag, instance=goi_hoac_None)
#
# Quy tắc (wireframe C1.7): Tên gói, Loại hình, Mô tả/Quyền lợi, Giá, Thời lượng, Hình thức hậu kỳ bắt buộc.
# "Số ảnh hậu kỳ tối đa" chỉ nhập khi chọn "Giới hạn số lượng ảnh" (> 0); chọn "Hậu kỳ toàn bộ ảnh" thì để trống.
# Trạng thái trong form chỉ chọn Đang áp dụng / Ngừng áp dụng; "Đã ẩn" đổi bằng nút Ẩn / Hiện lại ở danh sách.
# =====================================================================
from django import forms
from django.core.exceptions import ValidationError

from core.constants import LoaiHauKy, TrangThaiGoi
from profiles.models import GoiDichVu, LoaiHinhChup

THOI_LUONG_TOI_DA = 1440        # một ngày
SO_ANH_TOI_DA = 10000
MO_TA_TOI_DA = 2000


class GoiForm(forms.ModelForm):
    class Meta:
        model = GoiDichVu
        fields = ['TenGoi', 'MaLoaiHinh', 'MoTa', 'Gia', 'ThoiLuongChup',
                  'LoaiHauKy', 'SoAnhHauKyToiDa', 'TrangThai']
        labels = {'TenGoi': 'Tên gói', 'MaLoaiHinh': 'Loại hình chụp', 'MoTa': 'Mô tả / Quyền lợi',
                  'Gia': 'Giá (VNĐ)', 'ThoiLuongChup': 'Thời lượng chụp (phút)',
                  'LoaiHauKy': 'Hình thức hậu kỳ', 'SoAnhHauKyToiDa': 'Số ảnh hậu kỳ tối đa',
                  'TrangThai': 'Trạng thái gói'}
        help_texts = {'SoAnhHauKyToiDa': 'Khách hàng chỉ được chọn tối đa số ảnh này để hậu kỳ.',
                      'MoTa': '', 'Gia': ''}
        widgets = {
            'TenGoi': forms.TextInput(attrs={'placeholder': 'Nhập tên gói dịch vụ'}),
            'MoTa': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Mô tả nội dung và quyền lợi của gói'}),
            'Gia': forms.NumberInput(attrs={'placeholder': 'Nhập giá gói', 'inputmode': 'numeric', 'min': 1}),
            'ThoiLuongChup': forms.NumberInput(attrs={'placeholder': 'Nhập số phút', 'inputmode': 'numeric', 'min': 1}),
            'LoaiHauKy': forms.RadioSelect,
            'SoAnhHauKyToiDa': forms.NumberInput(attrs={'placeholder': 'Nhập số ảnh', 'inputmode': 'numeric', 'min': 1}),
            'TrangThai': forms.RadioSelect,
        }
        error_messages = {
            'TenGoi': {'required': 'Vui lòng nhập tên gói.'},
            'MaLoaiHinh': {'required': 'Vui lòng chọn loại hình chụp.'},
            'MoTa': {'required': 'Vui lòng nhập mô tả và quyền lợi của gói.'},
            'Gia': {'required': 'Vui lòng nhập giá gói.', 'invalid': 'Giá phải là số nguyên lớn hơn 0.',
                    'max_digits': 'Giá quá lớn.', 'max_whole_digits': 'Giá quá lớn.',
                    'max_decimal_places': 'Giá phải là số nguyên (không có phần lẻ).'},
            'ThoiLuongChup': {'required': 'Vui lòng nhập thời lượng chụp.',
                              'invalid': 'Thời lượng phải là số phút nguyên lớn hơn 0.'},
            'LoaiHauKy': {'required': 'Vui lòng chọn hình thức hậu kỳ.'},
            'SoAnhHauKyToiDa': {'invalid': 'Số ảnh hậu kỳ tối đa phải là số nguyên lớn hơn 0.'},
            'TrangThai': {'required': 'Vui lòng chọn trạng thái gói.'},
        }

    def __init__(self, *args, nag, **kwargs):
        super().__init__(*args, **kwargs)
        self.nag = nag
        self.fields['MaLoaiHinh'].queryset = LoaiHinhChup.objects.all()
        self.fields['MaLoaiHinh'].empty_label = 'Chọn loại hình chụp'
        self.fields['LoaiHauKy'].choices = LoaiHauKy.CHOICES          # bỏ dòng trống "---------"
        # Thêm mới / sửa gói bình thường: chọn 2 trạng thái. Gói đang "Đã ẩn" thì giữ thêm lựa chọn đó.
        trang_thai = [(t, t) for t in (TrangThaiGoi.DANG_AP_DUNG, TrangThaiGoi.NGUNG_AP_DUNG)]
        if self.instance.pk and self.instance.TrangThai == TrangThaiGoi.DA_AN:
            trang_thai.append((TrangThaiGoi.DA_AN, TrangThaiGoi.DA_AN))
        self.fields['TrangThai'].choices = trang_thai
        if not self.instance.pk:
            self.initial.setdefault('TrangThai', TrangThaiGoi.DANG_AP_DUNG)
            self.initial.setdefault('LoaiHauKy', LoaiHauKy.GIOI_HAN)
        for ten in ('Gia', 'ThoiLuongChup', 'SoAnhHauKyToiDa'):
            self.fields[ten].localize = False

    def clean_TenGoi(self):
        ten = ' '.join(self.cleaned_data['TenGoi'].split())
        if not ten:
            raise ValidationError('Vui lòng nhập tên gói.')
        # So sánh trong Python: iexact của SQLite không phân biệt hoa/thường với chữ có dấu (Â, Ó...).
        cac_ten = GoiDichVu.objects.filter(MaNhiepAnhGia=self.nag)
        if self.instance.pk:
            cac_ten = cac_ten.exclude(pk=self.instance.pk)
        if any(t.casefold() == ten.casefold() for t in cac_ten.values_list('TenGoi', flat=True)):
            raise ValidationError('Bạn đã có một gói trùng tên này. Vui lòng đặt tên khác.')
        return ten

    def clean_MoTa(self):
        mo_ta = (self.cleaned_data['MoTa'] or '').strip()
        if not mo_ta:
            raise ValidationError('Vui lòng nhập mô tả và quyền lợi của gói.')
        if len(mo_ta) > MO_TA_TOI_DA:
            raise ValidationError(f'Mô tả tối đa {MO_TA_TOI_DA} ký tự.')
        return mo_ta

    def clean_Gia(self):
        gia = self.cleaned_data['Gia']
        if gia is None or gia <= 0:
            raise ValidationError('Giá phải là số nguyên lớn hơn 0.')
        if gia != gia.to_integral_value():
            raise ValidationError('Giá phải là số nguyên (không có phần lẻ).')
        return gia

    def clean_ThoiLuongChup(self):
        phut = self.cleaned_data['ThoiLuongChup']
        if phut is None or phut <= 0:
            raise ValidationError('Thời lượng phải là số phút nguyên lớn hơn 0.')
        if phut > THOI_LUONG_TOI_DA:
            raise ValidationError(f'Thời lượng tối đa {THOI_LUONG_TOI_DA} phút (24 giờ).')
        return phut

    def clean(self):
        data = super().clean()
        loai = data.get('LoaiHauKy')
        if loai == LoaiHauKy.GIOI_HAN:
            so_anh = data.get('SoAnhHauKyToiDa')
            if 'SoAnhHauKyToiDa' not in self.errors:
                if so_anh is None:
                    self.add_error('SoAnhHauKyToiDa', 'Vui lòng nhập số ảnh hậu kỳ tối đa.')
                elif so_anh <= 0:
                    self.add_error('SoAnhHauKyToiDa', 'Số ảnh hậu kỳ tối đa phải lớn hơn 0.')
                elif so_anh > SO_ANH_TOI_DA:
                    self.add_error('SoAnhHauKyToiDa', f'Số ảnh hậu kỳ tối đa là {SO_ANH_TOI_DA}.')
        elif loai == LoaiHauKy.TOAN_BO:
            data['SoAnhHauKyToiDa'] = None     # hậu kỳ toàn bộ ảnh thì không giới hạn số ảnh (đúng ràng buộc CSDL)
            self.errors.pop('SoAnhHauKyToiDa', None)
        return data

    def save(self, commit=True):
        goi = super().save(commit=False)
        goi.MaNhiepAnhGia = self.nag
        if commit:
            goi.save()
        return goi
