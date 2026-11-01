# payments/forms.py - N2 / UC5.1
from django import forms                                      # thư viện form của Django

from payments.services import DUNG_LUONG_TOI_DA, DUOI_CHO_PHEP  # dùng chung giới hạn đã khai báo ở services


class MinhChungForm(forms.Form):                              # form tải minh chứng
    tep = forms.ImageField(                                   # ImageField: tự kiểm tra tệp có đúng là ảnh (cần Pillow)
        label='Ảnh minh chứng chuyển khoản',
        help_text='Chỉ nhận JPG, JPEG hoặc PNG, tối đa 5 MB.',
        widget=forms.FileInput(attrs={'accept': '.jpg,.jpeg,.png'}),  # trình duyệt chỉ gợi ý 3 đuôi này
        error_messages={'required': 'Vui lòng chọn tệp minh chứng.',
                        'invalid_image': 'Tệp không phải ảnh hợp lệ.'})

    def clean_tep(self):                                      # Django tự gọi khi kiểm tra ô 'tep' (bước 4, ngoại lệ 4a)
        tep = self.cleaned_data['tep']
        duoi = tep.name.rsplit('.', 1)[-1].lower() if '.' in tep.name else ''
        if duoi not in DUOI_CHO_PHEP:                         # sai đuôi tệp
            raise forms.ValidationError('Chỉ chấp nhận tệp JPG, JPEG hoặc PNG.')
        if getattr(tep, 'image', None) and tep.image.format not in ('JPEG', 'PNG'):  # đổi đuôi gif thành png cũng bị chặn
            raise forms.ValidationError('Chỉ chấp nhận tệp JPG, JPEG hoặc PNG.')
        if tep.size > DUNG_LUONG_TOI_DA:                      # quá dung lượng
            raise forms.ValidationError('Dung lượng tệp vượt quá 5 MB.')
        return tep
