# delivery/forms.py - N4 / UC5.3: kiểm tra ảnh Nhiếp ảnh gia chọn tải lên (bước 4, ngoại lệ 4a)
from django import forms                                       # thư viện form của Django
from PIL import Image                                          # Pillow: mở ảnh để kiểm tra có đúng là ảnh thật không

from delivery.services import DUNG_LUONG_TOI_DA, DUOI_CHO_PHEP, SO_ANH_TOI_DA, SO_PIXEL_TOI_DA  # giới hạn khai báo ở services (sửa 1 chỗ)


class MultipleFileInput(forms.ClearableFileInput):             # ô chọn NHIỀU tệp (cách Django hướng dẫn)
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):                      # trường nhận danh sách tệp
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):                       # kiểm tra từng tệp bằng hàm của FileField
        kiem_tra_mot_tep = super().clean
        if isinstance(data, (list, tuple)):
            return [kiem_tra_mot_tep(tep, initial) for tep in data]
        return [kiem_tra_mot_tep(data, initial)]


class TaiAnhForm(forms.Form):                                  # form tải ảnh
    anh = MultipleFileField(
        label='Chọn ảnh để tải lên',
        help_text=f'JPG, JPEG hoặc PNG, tối đa {DUNG_LUONG_TOI_DA // (1024 * 1024)} MB mỗi ảnh, tối đa {SO_ANH_TOI_DA} ảnh mỗi lần.',
        widget=MultipleFileInput(attrs={'accept': '.jpg,.jpeg,.png'}),   # trình duyệt chỉ gợi ý 3 đuôi này
        error_messages={'required': 'Vui lòng chọn ít nhất một ảnh.'})

    def clean_anh(self):                                       # Django tự gọi khi kiểm tra ô 'anh'
        ds = self.cleaned_data['anh']
        if not ds:                                             # không chọn tệp nào
            raise forms.ValidationError('Vui lòng chọn ít nhất một ảnh.')
        if len(ds) > SO_ANH_TOI_DA:                            # quá số lượng
            raise forms.ValidationError(f'Mỗi lần chỉ được tải tối đa {SO_ANH_TOI_DA} ảnh (bạn chọn {len(ds)} ảnh).')
        loi = []                                               # gom hết lỗi để báo một lần
        for tep in ds:
            duoi = tep.name.rsplit('.', 1)[-1].lower() if '.' in tep.name else ''
            if duoi not in DUOI_CHO_PHEP:                      # sai đuôi tệp
                loi.append(f'{tep.name}: chỉ nhận JPG, JPEG hoặc PNG.')
            elif tep.size > DUNG_LUONG_TOI_DA:                 # quá dung lượng
                loi.append(f'{tep.name}: vượt quá {DUNG_LUONG_TOI_DA // (1024 * 1024)} MB.')
            else:
                try:                                           # mở thử để chắc đây là ảnh thật (không phải tệp đổi đuôi)
                    with Image.open(tep) as anh:
                        so_pixel = anh.size[0] * anh.size[1]
                        anh.verify()
                        dinh_dang_that = anh.format
                except Exception:                              # tệp hỏng hoặc không phải ảnh
                    loi.append(f'{tep.name}: không phải ảnh hợp lệ.')
                else:
                    if dinh_dang_that not in ('JPEG', 'PNG'):  # ví dụ ảnh GIF đổi thành .png
                        loi.append(f'{tep.name}: định dạng thật của tệp không phải JPG hoặc PNG.')
                    elif so_pixel > SO_PIXEL_TOI_DA:           # N5: ảnh quá lớn thì không kịp chèn watermark trong 5 giây
                        loi.append(f'{tep.name}: độ phân giải quá lớn (tối đa {SO_PIXEL_TOI_DA // 1_000_000} megapixel).')
                tep.seek(0)                                    # đưa con trỏ về đầu tệp để bước xử lý đọc lại được
        if loi:
            if len(loi) > 10:                                  # chỉ liệt kê 10 lỗi đầu cho gọn
                loi = loi[:10] + [f'... và {len(loi) - 10} ảnh lỗi khác.']
            raise forms.ValidationError(loi)
        return ds
