import re  # kiểm tra chuỗi theo mẫu (số điện thoại, họ tên)
import unicodedata  # chuẩn hóa chữ tiếng Việt về một dạng duy nhất trước khi kiểm tra

from django import forms  # thư viện form của Django
from django.contrib.auth.forms import AuthenticationForm  # form đăng nhập mẫu của Django
from django.contrib.auth.password_validation import validate_password  # chạy các quy tắc AUTH_PASSWORD_VALIDATORS trong settings.py
from django.core.exceptions import ValidationError  # lỗi nhập liệu
from django.db.models import Q  # Q: ghép điều kiện "hoặc" khi tìm trong DB

from .models import User  # model User của FRAMIE (dùng để kiểm tra trùng)
from .validators import DoPhucTapMatKhau  # luật 4 loại ký tự của mật khẩu (P4)


class DangNhapForm(AuthenticationForm):  # kế thừa form mẫu, chỉ đổi chữ và kiểu ô nhập
    error_messages = {  # các câu báo lỗi của form
        'invalid_login': 'Email hoặc mật khẩu không chính xác',  # đúng chữ trong đặc tả, dùng cho cả sai email lẫn sai mật khẩu
        'inactive': 'Tài khoản của bạn đã bị khóa. Vui lòng liên hệ Quản trị viên.',  # tài khoản bị khóa (P7 sẽ dùng)
    }  # hết danh sách lỗi

    username = forms.EmailField(  # ô email (name vẫn là username để backend nhận được)
        label='Email',  # nhãn hiển thị
        max_length=100,  # độ dài tối đa
        widget=forms.EmailInput(attrs={'autofocus': True, 'autocomplete': 'email'}),
        # con trỏ tự nhảy vào ô; trình duyệt gợi ý email đã lưu
        error_messages={'invalid': 'Email hoặc mật khẩu không chính xác'},
        # gõ sai dạng email cũng báo đúng câu theo đặc tả
    )  # hết ô email
    password = forms.CharField(  # ô mật khẩu
        label='Mật khẩu',  # nhãn hiển thị
        strip=False,  # không tự cắt khoảng trắng đầu/cuối mật khẩu
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),  # ô ẩn ký tự, gợi ý trình duyệt điền mật khẩu đã lưu
    )  # hết ô mật khẩu


class DangKyForm(forms.Form):  # P4: form đăng ký tài khoản Khách hàng (UC7.1a)
    ho_ten = forms.CharField(  # ô họ và tên
        label='Họ và tên',  # nhãn hiển thị
        max_length=100,  # tối đa 100 ký tự
        widget=forms.TextInput(attrs={'autofocus': True, 'autocomplete': 'name'}),  # con trỏ tự nhảy vào ô đầu tiên; trình duyệt gợi ý tên
        error_messages={'required': 'Vui lòng nhập họ và tên.'},  # câu báo khi để trống
    )  # hết ô họ tên
    email = forms.EmailField(  # ô email (tự kiểm tra dạng a@b.c)
        label='Email',  # nhãn hiển thị
        max_length=100,  # khớp max_length=100 của cột email trong User
        widget=forms.EmailInput(attrs={'autocomplete': 'email'}),  # trình duyệt gợi ý email đã lưu
        error_messages={'required': 'Vui lòng nhập email.', 'invalid': 'Email không đúng định dạng.'},  # câu báo khi trống hoặc sai dạng
    )  # hết ô email
    so_dien_thoai = forms.CharField(  # ô số điện thoại
        label='Số điện thoại',  # nhãn hiển thị
        widget=forms.TextInput(attrs={'type': 'tel', 'inputmode': 'numeric', 'autocomplete': 'tel', 'maxlength': '10'}),  # bàn phím số trên điện thoại, chặn gõ quá 10 ký tự
        help_text='10 chữ số, bắt đầu bằng 0.',  # dòng hướng dẫn dưới ô
        error_messages={'required': 'Vui lòng nhập số điện thoại.'},  # câu báo khi để trống
    )  # hết ô số điện thoại
    mat_khau = forms.CharField(  # ô mật khẩu
        label='Mật khẩu',  # nhãn hiển thị
        strip=False,  # không tự cắt khoảng trắng đầu/cuối mật khẩu
        max_length=128,  # chặn mật khẩu quá dài làm chậm bước băm
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),  # ẩn ký tự; trình duyệt đề xuất mật khẩu mới
        help_text='Từ 8 ký tự, có chữ hoa, chữ thường, chữ số và ký tự đặc biệt.',  # dòng hướng dẫn dưới ô
        error_messages={'required': 'Vui lòng nhập mật khẩu.'},  # câu báo khi để trống
    )  # hết ô mật khẩu

    def clean_ho_ten(self):  # Django tự gọi sau khi ô ho_ten qua kiểm tra cơ bản
        ho_ten = unicodedata.normalize('NFC', self.cleaned_data['ho_ten'])  # đưa về dạng dựng sẵn: gõ trên macOS hay Windows đều như nhau
        ho_ten = ' '.join(ho_ten.split())  # gộp nhiều khoảng trắng liên tiếp thành một, bỏ khoảng trắng hai đầu
        if not re.fullmatch(r'[^\W\d_]+(?: [^\W\d_]+)*', ho_ten):  # chỉ nhận chữ cái (có dấu) cách nhau bằng một dấu cách
            raise ValidationError('Họ và tên chỉ gồm chữ cái và khoảng trắng.')  # báo lỗi
        return ho_ten  # trả họ tên đã làm sạch

    def clean_email(self):  # Django tự gọi sau khi ô email qua kiểm tra cơ bản
        email = self.cleaned_data['email'].strip().lower()  # chữ thường: A@x.com và a@x.com là một
        if User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email)).exists():  # đã có tài khoản dùng email (hoặc username) này, không phân biệt hoa/thường
            raise ValidationError('Email này đã được đăng ký.')  # báo lỗi trùng
        return email  # trả email chữ thường

    def clean_so_dien_thoai(self):  # Django tự gọi sau khi ô số điện thoại qua kiểm tra cơ bản
        so = self.cleaned_data['so_dien_thoai'].strip()  # bỏ khoảng trắng hai đầu
        if not re.fullmatch(r'0[0-9]{9}', so):  # đúng 10 ký tự, ký tự đầu là 0, còn lại là 0-9 (như RegexValidator ở models.py)
            raise ValidationError('Số điện thoại gồm 10 chữ số và bắt đầu bằng 0.')  # báo sai định dạng
        if User.objects.filter(so_dien_thoai=so).exists():  # đã có tài khoản dùng số này
            raise ValidationError('Số điện thoại này đã được đăng ký.')  # báo lỗi trùng
        return so  # trả số điện thoại hợp lệ

    def clean(self):  # chạy SAU khi mọi ô đã qua kiểm tra riêng, nên có đủ dữ liệu để so sánh chéo
        du_lieu = super().clean()  # lấy dữ liệu đã làm sạch
        mat_khau = du_lieu.get('mat_khau')  # lấy mật khẩu (None nếu ô này đã lỗi)
        if mat_khau:  # chỉ kiểm tra khi có mật khẩu
            user_tam = User(  # tạo User tạm, KHÔNG lưu DB, để validator so mật khẩu với thông tin cá nhân
                username=du_lieu.get('email', ''),  # username sẽ bằng email
                email=du_lieu.get('email', ''),  # email người dùng nhập
                first_name=du_lieu.get('ho_ten', ''),  # họ tên người dùng nhập
            )  # hết User tạm
            loi_mat_khau = []  # gom mọi lỗi mật khẩu vào một danh sách
            try:  # chạy các quy tắc có sẵn của Django (độ dài 8, không quá phổ biến, không giống email/tên, không toàn số)
                validate_password(mat_khau, user_tam)  # các quy tắc này lấy từ AUTH_PASSWORD_VALIDATORS trong settings.py
            except ValidationError as loi:  # có quy tắc nào vi phạm
                loi_mat_khau.extend(loi.error_list)  # lấy từng lỗi bỏ vào danh sách
            try:  # chạy thêm luật của FRAMIE: chữ hoa, chữ thường, số, ký tự đặc biệt (gọi thẳng, không qua settings.py)
                DoPhucTapMatKhau().validate(mat_khau, user_tam)  # nếu thiếu loại ký tự nào sẽ báo lỗi
            except ValidationError as loi:  # thiếu loại ký tự
                loi_mat_khau.extend(loi.error_list)  # bỏ lỗi vào cùng danh sách
            if loi_mat_khau:  # có ít nhất một lỗi
                self.add_error('mat_khau', loi_mat_khau)  # gắn tất cả lỗi vào ô mật khẩu
        return du_lieu  # trả dữ liệu cho view
