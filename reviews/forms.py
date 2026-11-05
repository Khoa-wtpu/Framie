# reviews/forms.py - N11 / UC6.1: form đánh giá (điểm 1-5 bắt buộc, nhận xét tối đa 500 ký tự không bắt buộc)
from django import forms

from reviews.services import DO_DAI_NHAN_XET_TOI_DA, chuan_hoa_nhan_xet


class DanhGiaForm(forms.Form):
    diem = forms.TypedChoiceField(
        label='Số sao', choices=[(i, str(i)) for i in range(1, 6)], coerce=int, required=True,
        error_messages={'required': 'Vui lòng chọn số sao từ 1 đến 5.',
                        'invalid_choice': 'Vui lòng chọn số sao từ 1 đến 5.'})
    nhan_xet = forms.CharField(label='Nhận xét', required=False, widget=forms.Textarea)   # độ dài kiểm tra ở clean_nhan_xet

    def clean_nhan_xet(self):
        nhan_xet = chuan_hoa_nhan_xet(self.cleaned_data.get('nhan_xet'))   # \r\n -> \n để đếm ký tự giống trình duyệt
        if nhan_xet and len(nhan_xet) > DO_DAI_NHAN_XET_TOI_DA:
            raise forms.ValidationError(f'Nhận xét tối đa {DO_DAI_NHAN_XET_TOI_DA} ký tự (hiện có {len(nhan_xet)}).')
        return nhan_xet or ''
