# schedule/forms.py - K10: form thêm / sửa khung giờ (UC3.1, wireframe SC3.2 "Thiết lập / Chỉnh sửa khung giờ")
from django import forms

from schedule import quan_ly
from schedule.models import LichKhaDung

BUOC_GIO = (0, 30)      # ô chọn giờ cách nhau 30 phút


def _cac_gio():
    """[('08:00:00', '08:00'), ...] từ 00:00 đến 23:30. Giá trị gửi lên có dạng HH:MM:SS để khớp giá trị
    Django điền sẵn khi sửa (nếu không ô chọn sẽ không được chọn sẵn giờ cũ)."""
    return [(f'{h:02d}:{m:02d}:00', f'{h:02d}:{m:02d}') for h in range(24) for m in BUOC_GIO]


def _chon_gio(nhan, thieu):
    return forms.TimeField(
        label=nhan,
        widget=forms.Select(choices=[('', 'Chọn giờ')] + _cac_gio()),
        error_messages={'required': thieu, 'invalid': 'Giờ không hợp lệ.'})


class KhungGioForm(forms.ModelForm):
    Ngay = forms.DateField(
        label='Ngày',
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        error_messages={'required': 'Vui lòng chọn ngày.', 'invalid': 'Ngày không hợp lệ.'})
    GioBatDau = _chon_gio('Giờ bắt đầu', 'Vui lòng chọn giờ bắt đầu.')
    GioKetThuc = _chon_gio('Giờ kết thúc', 'Vui lòng chọn giờ kết thúc.')

    class Meta:
        model = LichKhaDung
        fields = ['Ngay', 'GioBatDau', 'GioKetThuc']

    def __init__(self, *args, nag, **kwargs):
        super().__init__(*args, **kwargs)
        # Khung giờ luôn thuộc về Nhiếp ảnh gia đang đăng nhập (không cho người dùng tự chọn qua form).
        # Gán ngay từ đầu để LichKhaDung.clean() biết kiểm tra chồng giờ với lịch của đúng người này.
        self.instance.MaNhiepAnhGia = nag
        self.fields['Ngay'].widget.attrs['min'] = quan_ly.bay_gio().date().isoformat()
        if self.instance.pk:
            self._them_gio_le_neu_can()

    def _them_gio_le_neu_can(self):
        """Khung giờ cũ (tạo ở trang admin) có thể lẻ phút, vd 09:15. Thêm giờ đó vào ô chọn để sửa không bị mất."""
        for ten in ('GioBatDau', 'GioKetThuc'):
            gia_tri = getattr(self.instance, ten, None)
            if gia_tri is None:
                continue
            ma = gia_tri.strftime('%H:%M:%S')
            cac_lua_chon = list(self.fields[ten].widget.choices)
            if ma not in [c[0] for c in cac_lua_chon]:
                cac_lua_chon.append((ma, gia_tri.strftime('%H:%M')))
                cac_lua_chon = cac_lua_chon[:1] + sorted(cac_lua_chon[1:])
                self.fields[ten].widget.choices = cac_lua_chon

    def clean(self):
        du_lieu = super().clean()
        ngay, bat_dau, ket_thuc = du_lieu.get('Ngay'), du_lieu.get('GioBatDau'), du_lieu.get('GioKetThuc')
        bg = quan_ly.bay_gio()
        if ngay and ngay < bg.date():
            self.add_error('Ngay', 'Ngày không được ở trong quá khứ.')
        elif ngay and bat_dau and ngay == bg.date() and bat_dau <= bg.time():
            self.add_error('GioBatDau', 'Giờ bắt đầu phải sau thời điểm hiện tại.')
        if bat_dau and ket_thuc and ket_thuc <= bat_dau:
            self.add_error('GioKetThuc', 'Giờ kết thúc phải sau giờ bắt đầu.')
        return du_lieu

    def _post_clean(self):
        # Đã có lỗi nhập liệu ở trên thì dừng, không chạy tiếp kiểm tra của model: tránh báo lỗi chồng giờ
        # dựa trên dữ liệu chưa hợp lệ, và tránh báo hai lần cùng một lỗi "giờ kết thúc".
        if self.errors:
            return
        super()._post_clean()
