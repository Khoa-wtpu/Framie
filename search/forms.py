# search/forms.py - K8: form tìm kiếm + lọc nhiếp ảnh gia (gửi bằng GET để chia sẻ được đường dẫn)
from django import forms

from profiles.models import KhuVuc, LoaiHinhChup, PhongCach
from search.services import SAP_XEP, SAP_XEP_MAC_DINH

GIA_TOI_DA = 10 ** 11            # nhỏ hơn giới hạn của cột Gia (12 chữ số)
GIA_TOI_THIEU = 1000             # giá thấp nhất được lọc (VNĐ): không có gói nào rẻ hơn, nhập thấp hơn là nhập nhầm


def _tien(so):
    return f'{so:,}'.replace(',', '.')           # 1000 -> 1.000

def _chon_nhieu(model, nhan):
    return forms.ModelMultipleChoiceField(
        queryset=model.objects.all(), required=False, label=nhan,
        widget=forms.CheckboxSelectMultiple,
        error_messages={'invalid_choice': f'{nhan} đã chọn không hợp lệ.',
                        'invalid_pk_value': f'{nhan} đã chọn không hợp lệ.',
                        'invalid_list': f'{nhan} đã chọn không hợp lệ.'})


class TimKiemForm(forms.Form):
    q = forms.CharField(
        label='Từ khóa hoặc ID', required=False, max_length=100,
        error_messages={'max_length': 'Từ khóa tối đa 100 ký tự.'},
        widget=forms.TextInput(attrs={
            'placeholder': 'Tìm theo từ khóa hoặc ID Nhiếp ảnh gia', 'autocomplete': 'off',
            'type': 'search'}))
    loai_hinh = _chon_nhieu(LoaiHinhChup, 'Loại hình chụp')
    phong_cach = _chon_nhieu(PhongCach, 'Phong cách')
    khu_vuc = _chon_nhieu(KhuVuc, 'Khu vực')
    gia_tu = forms.IntegerField(
        label='Từ (VNĐ)', required=False, min_value=GIA_TOI_THIEU, max_value=GIA_TOI_DA,
        error_messages={'invalid': 'Giá bắt đầu phải là số nguyên.',
                        'min_value': f'Giá bắt đầu tối thiểu là {_tien(GIA_TOI_THIEU)} VNĐ.',
                        'max_value': 'Giá bắt đầu quá lớn.'},
        widget=forms.NumberInput(
            attrs={'placeholder': 'Từ (VNĐ)', 'inputmode': 'numeric', 'min': GIA_TOI_THIEU, 'step': GIA_TOI_THIEU}))
    gia_den = forms.IntegerField(
        label='Đến (VNĐ)', required=False, min_value=GIA_TOI_THIEU, max_value=GIA_TOI_DA,
        error_messages={'invalid': 'Giá kết thúc phải là số nguyên.',
                        'min_value': f'Giá kết thúc tối thiểu là {_tien(GIA_TOI_THIEU)} VNĐ.',
                        'max_value': 'Giá kết thúc quá lớn.'},
        widget=forms.NumberInput(
            attrs={'placeholder': 'Đến (VNĐ)', 'inputmode': 'numeric', 'min': GIA_TOI_THIEU, 'step': GIA_TOI_THIEU}))
    sap_xep = forms.ChoiceField(
        label='Sắp xếp', required=False,
        choices=[(khoa, nhan) for khoa, (nhan, _) in SAP_XEP.items()],
        error_messages={'invalid_choice': 'Cách sắp xếp không hợp lệ.'})

    def clean_q(self):
        q = ' '.join(self.cleaned_data['q'].split())          # gộp khoảng trắng thừa
        if q and any(ord(c) < 32 for c in q):
            raise forms.ValidationError('Từ khóa chứa ký tự không hợp lệ.')
        if q and not any(c.isalnum() for c in q):
            raise forms.ValidationError('Từ khóa không hợp lệ, vui lòng nhập chữ hoặc số.')
        return q

    def clean_sap_xep(self):
        return self.cleaned_data['sap_xep'] or SAP_XEP_MAC_DINH

    def clean(self):
        data = super().clean()
        tu, den = data.get('gia_tu'), data.get('gia_den')
        if tu is not None and den is not None and tu > den:
            raise forms.ValidationError('Khoảng giá không hợp lệ: giá bắt đầu phải nhỏ hơn hoặc bằng giá kết thúc.')
        return data

    def so_bo_loc(self):
        """Số nhóm bộ lọc đang bật (hiện trên nút "Bộ lọc"). Từ khóa và sắp xếp không tính."""
        d = self.cleaned_data
        nhom = [bool(d.get('loai_hinh')), bool(d.get('phong_cach')), bool(d.get('khu_vuc')),
                d.get('gia_tu') is not None or d.get('gia_den') is not None]
        return sum(nhom)
