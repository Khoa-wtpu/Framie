import re  # kiểm tra chuỗi theo mẫu (số điện thoại, họ tên)
import unicodedata  # chuẩn hóa chữ tiếng Việt về một dạng duy nhất trước khi kiểm tra

from django import forms  # thư viện form của Django
from django.contrib.auth.forms import AuthenticationForm  # form đăng nhập mẫu của Django
from django.contrib.auth.password_validation import validate_password  # chạy các quy tắc AUTH_PASSWORD_VALIDATORS trong settings.py
from django.core.exceptions import ValidationError  # lỗi nhập liệu
from django.db.models import Q  # Q: ghép điều kiện "hoặc" khi tìm trong DB

from .models import User  # model User của FRAMIE (dùng để kiểm tra trùng)


def kiem_tra_mat_khau(mat_khau, user):  # P4 + P6: chạy MỌI luật mật khẩu khai báo trong AUTH_PASSWORD_VALIDATORS, trả danh sách lỗi (rỗng nếu hợp lệ)
    loi_mat_khau = []  # gom mọi lỗi vào một danh sách
    try:  # chạy các luật trong settings.py: độ dài 8, không quá phổ biến, không giống email/tên, không toàn số, và DoPhucTapMatKhau (chữ hoa, chữ thường, số, ký tự đặc biệt)
        validate_password(mat_khau, user)  # DoPhucTapMatKhau đã nằm trong settings.py nên KHÔNG gọi riêng ở đây nữa, nếu không mỗi lỗi hiện 2 lần
    except ValidationError as loi:  # có luật nào vi phạm
        loi_mat_khau.extend(loi.error_list)  # lấy từng lỗi bỏ vào danh sách
    return loi_mat_khau  # trả danh sách lỗi cho form


class DangNhapForm(AuthenticationForm):  # kế thừa form mẫu, chỉ đổi chữ và kiểu ô nhập
    error_messages = {  # các câu báo lỗi của form
        'invalid_login': 'Email hoặc mật khẩu không chính xác',  # đúng chữ trong đặc tả, dùng cho cả sai email lẫn sai mật khẩu
        'inactive': 'Tài khoản của bạn đã bị khóa. Vui lòng liên hệ Quản trị viên.',  # tài khoản bị khóa (P7 sẽ dùng)
    }  # hết danh sách lỗi

    username = forms.EmailField(  # ô email (name vẫn là username để backend nhận được)
        label='Email',  # nhãn hiển thị
        max_length=100,  # độ dài tối đa
        widget=forms.EmailInput(attrs={'autofocus': True, 'autocomplete': 'email'}),  # con trỏ tự nhảy vào ô; trình duyệt gợi ý email đã lưu
        error_messages={'invalid': 'Email hoặc mật khẩu không chính xác'},  # gõ sai dạng email cũng báo đúng câu theo đặc tả
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
        if not re.fullmatch(r"[^\W\d_]+(?:[ '’-][^\W\d_]+)*", ho_ten):  # chữ cái (có dấu), các cụm cách nhau bằng MỘT dấu cách, gạch nối hoặc dấu nháy
            raise ValidationError('Họ và tên chỉ gồm chữ cái, khoảng trắng, dấu gạch nối và dấu nháy.')  # báo lỗi
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
            loi_mat_khau = kiem_tra_mat_khau(mat_khau, user_tam)  # chạy mọi luật mật khẩu bằng hàm dùng chung (P4 và P6)
            if loi_mat_khau:  # có ít nhất một lỗi
                self.add_error('mat_khau', loi_mat_khau)  # gắn tất cả lỗi vào ô mật khẩu
        return du_lieu  # trả dữ liệu cho view


class QuenMatKhauForm(forms.Form):  # P6 bước 1: nhập email đã đăng ký
    user = None  # sẽ giữ User tìm được để view dùng tiếp, không phải tìm lần hai

    email = forms.EmailField(  # ô email
        label='Email đã đăng ký',  # nhãn hiển thị
        max_length=100,  # khớp max_length=100 của cột email trong User
        widget=forms.EmailInput(attrs={'autofocus': True, 'autocomplete': 'email'}),  # con trỏ tự nhảy vào ô; trình duyệt gợi ý email
        error_messages={'required': 'Vui lòng nhập email.', 'invalid': 'Email không đúng định dạng.'},  # câu báo khi trống hoặc sai dạng
    )  # hết ô email

    def clean_email(self):  # Django tự gọi sau khi ô email qua kiểm tra cơ bản
        email = self.cleaned_data['email'].strip().lower()  # chữ thường để so khớp không phân biệt hoa/thường
        self.user = User.objects.filter(email__iexact=email).first()  # tìm tài khoản; None nếu chưa có
        if self.user is None:  # email chưa đăng ký
            raise ValidationError('Email này chưa được đăng ký.')  # báo rõ theo đặc tả P6
        return email  # trả email đã làm sạch


class NhapMaForm(forms.Form):  # P6 bước 2: nhập mã 6 chữ số
    ma = forms.CharField(  # ô mã xác thực
        label='Mã xác thực',  # nhãn hiển thị
        widget=forms.TextInput(attrs={'autofocus': True, 'inputmode': 'numeric', 'autocomplete': 'one-time-code', 'maxlength': '6'}),  # bàn phím số; trình duyệt gợi ý mã vừa nhận; chặn gõ quá 6 ký tự
        help_text='Mã gồm 6 chữ số được gửi tới email của bạn, có hiệu lực tối đa 10 phút.',  # dòng hướng dẫn dưới ô
        error_messages={'required': 'Vui lòng nhập mã xác thực.'},  # câu báo khi để trống
    )  # hết ô mã

    def clean_ma(self):  # Django tự gọi sau khi ô ma qua kiểm tra cơ bản
        ma = self.cleaned_data['ma'].strip()  # bỏ khoảng trắng hai đầu (hay bị dính khi copy từ email)
        if not re.fullmatch(r'[0-9]{6}', ma):  # đúng 6 ký tự, mỗi ký tự là 0-9 (không dùng \d vì nhận cả chữ số của chữ viết khác)
            raise ValidationError('Mã xác thực gồm đúng 6 chữ số.')  # báo sai định dạng, chưa tính là một lần nhập sai
        return ma  # trả mã hợp lệ


class DatLaiMatKhauForm(forms.Form):  # P6 bước 3: nhập mật khẩu mới
    mat_khau_moi = forms.CharField(  # ô mật khẩu mới
        label='Mật khẩu mới',  # nhãn hiển thị
        strip=False,  # không tự cắt khoảng trắng đầu/cuối mật khẩu
        max_length=128,  # chặn mật khẩu quá dài làm chậm bước băm
        widget=forms.PasswordInput(attrs={'autofocus': True, 'autocomplete': 'new-password'}),  # ẩn ký tự; trình duyệt đề xuất mật khẩu mới
        help_text='Từ 8 ký tự, có chữ hoa, chữ thường, chữ số và ký tự đặc biệt.',  # dòng hướng dẫn dưới ô
        error_messages={'required': 'Vui lòng nhập mật khẩu mới.'},  # câu báo khi để trống
    )  # hết ô mật khẩu mới

    def __init__(self, *args, user, **kwargs):  # nhận thêm User đang đặt lại mật khẩu
        super().__init__(*args, **kwargs)  # khởi tạo form như bình thường
        self.user = user  # giữ User để so mật khẩu mới với thông tin cá nhân của họ

    def clean_mat_khau_moi(self):  # Django tự gọi sau khi ô qua kiểm tra cơ bản
        mat_khau = self.cleaned_data['mat_khau_moi']  # mật khẩu người dùng vừa nhập
        loi_mat_khau = kiem_tra_mat_khau(mat_khau, self.user)  # chạy mọi luật mật khẩu bằng hàm dùng chung (P4 và P6)
        if loi_mat_khau:  # có ít nhất một lỗi
            raise ValidationError(loi_mat_khau)  # báo tất cả lỗi dưới ô mật khẩu
        return mat_khau  # trả mật khẩu hợp lệ


class CapNhatKhachHangForm(forms.Form):  # Khách hàng sửa hồ sơ: họ tên, số điện thoại, email (cùng luật với form đăng ký, bỏ qua chính mình khi kiểm tra trùng)
    ho_ten = forms.CharField(  # ô họ và tên
        label='Họ và tên',  # nhãn hiển thị
        max_length=100,  # tối đa 100 ký tự
        widget=forms.TextInput(attrs={'autocomplete': 'name'}),  # trình duyệt gợi ý tên
        error_messages={'required': 'Vui lòng nhập họ và tên.'},  # câu báo khi để trống
    )  # hết ô họ tên
    so_dien_thoai = forms.CharField(  # ô số điện thoại
        label='Số điện thoại',  # nhãn hiển thị
        widget=forms.TextInput(attrs={'type': 'tel', 'inputmode': 'numeric', 'autocomplete': 'tel', 'maxlength': '10'}),  # bàn phím số, chặn quá 10 ký tự
        help_text='10 chữ số, bắt đầu bằng 0.',  # dòng hướng dẫn
        error_messages={'required': 'Vui lòng nhập số điện thoại.'},  # câu báo khi để trống
    )  # hết ô số điện thoại
    email = forms.EmailField(  # ô email
        label='Email',  # nhãn hiển thị
        max_length=100,  # khớp cột email của User
        widget=forms.EmailInput(attrs={'autocomplete': 'email'}),  # trình duyệt gợi ý email
        help_text='Email này cũng là tên đăng nhập của bạn.',  # dòng hướng dẫn
        error_messages={'required': 'Vui lòng nhập email.', 'invalid': 'Email không đúng định dạng.'},  # câu báo khi trống hoặc sai dạng
    )  # hết ô email

    def __init__(self, *args, user, **kwargs):  # nhận thêm User đang sửa hồ sơ
        super().__init__(*args, **kwargs)  # khởi tạo form như bình thường
        self.user = user  # giữ User để loại chính mình khỏi kiểm tra trùng và để lưu
        if not self.is_bound:  # lần đầu mở trang: điền sẵn dữ liệu hiện tại
            self.initial.setdefault('ho_ten', user.get_full_name())  # họ tên hiện tại
            self.initial.setdefault('so_dien_thoai', user.so_dien_thoai)  # số điện thoại hiện tại
            self.initial.setdefault('email', user.email)  # email hiện tại

    def clean_ho_ten(self):  # Django tự gọi sau khi ô ho_ten qua kiểm tra cơ bản
        ho_ten = unicodedata.normalize('NFC', self.cleaned_data['ho_ten'])  # đưa về dạng dựng sẵn
        ho_ten = ' '.join(ho_ten.split())  # gộp khoảng trắng thừa
        if not re.fullmatch(r"[^\W\d_]+(?:[ '’-][^\W\d_]+)*", ho_ten):  # cùng luật với DangKyForm
            raise ValidationError('Họ và tên chỉ gồm chữ cái, khoảng trắng, dấu gạch nối và dấu nháy.')  # báo lỗi
        return ho_ten  # trả họ tên đã làm sạch

    def clean_so_dien_thoai(self):  # Django tự gọi sau khi ô số điện thoại qua kiểm tra cơ bản
        so = self.cleaned_data['so_dien_thoai'].strip()  # bỏ khoảng trắng hai đầu
        if not re.fullmatch(r'0[0-9]{9}', so):  # đúng 10 chữ số, bắt đầu bằng 0
            raise ValidationError('Số điện thoại gồm 10 chữ số và bắt đầu bằng 0.')  # báo sai định dạng
        if User.objects.filter(so_dien_thoai=so).exclude(pk=self.user.pk).exists():  # số này người khác đang dùng
            raise ValidationError('Số điện thoại này đã được đăng ký.')  # báo trùng
        return so  # trả số điện thoại hợp lệ

    def clean_email(self):  # Django tự gọi sau khi ô email qua kiểm tra cơ bản
        email = self.cleaned_data['email'].strip().lower()  # chữ thường để so khớp
        if User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email)).exclude(pk=self.user.pk).exists():  # người khác đang dùng
            raise ValidationError('Email này đã được đăng ký.')  # báo trùng
        return email  # trả email chữ thường

    def save(self):  # lưu thay đổi vào User
        from .services import tach_ho_ten  # import trong hàm cho gọn, tránh phụ thuộc vòng
        user = self.user  # tài khoản đang sửa
        ten, ho_dem = tach_ho_ten(self.cleaned_data['ho_ten'])  # tách họ tên thành (tên, họ và tên đệm)
        email = self.cleaned_data['email']  # email mới
        if user.username.lower() == user.email.lower():  # username đang bằng email thì giữ khớp (đăng nhập bằng email)
            user.username = email  # cập nhật username theo email mới
        user.first_name, user.last_name = ten, ho_dem  # ghi họ tên
        user.email = email  # ghi email
        user.so_dien_thoai = self.cleaned_data['so_dien_thoai']  # ghi số điện thoại
        user.save(update_fields=['username', 'first_name', 'last_name', 'email', 'so_dien_thoai'])  # chỉ lưu các cột đổi
        return user  # trả User đã lưu


class DoiMatKhauForm(forms.Form):  # Đổi mật khẩu khi đã đăng nhập: nhập mật khẩu cũ, mật khẩu mới, nhập lại
    mat_khau_cu = forms.CharField(  # ô mật khẩu hiện tại
        label='Mật khẩu hiện tại',  # nhãn hiển thị
        strip=False,  # không cắt khoảng trắng
        max_length=128,  # chặn mật khẩu quá dài
        widget=forms.PasswordInput(attrs={'autofocus': True, 'autocomplete': 'current-password'}),  # ẩn ký tự
        error_messages={'required': 'Vui lòng nhập mật khẩu hiện tại.'},  # câu báo khi để trống
    )  # hết ô mật khẩu hiện tại
    mat_khau_moi = forms.CharField(  # ô mật khẩu mới
        label='Mật khẩu mới',  # nhãn hiển thị
        strip=False,  # không cắt khoảng trắng
        max_length=128,  # chặn mật khẩu quá dài
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),  # ẩn ký tự
        help_text='Từ 8 ký tự, có chữ hoa, chữ thường, chữ số và ký tự đặc biệt.',  # dòng hướng dẫn
        error_messages={'required': 'Vui lòng nhập mật khẩu mới.'},  # câu báo khi để trống
    )  # hết ô mật khẩu mới
    nhap_lai = forms.CharField(  # ô nhập lại mật khẩu mới
        label='Nhập lại mật khẩu mới',  # nhãn hiển thị
        strip=False,  # không cắt khoảng trắng
        max_length=128,  # chặn mật khẩu quá dài
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),  # ẩn ký tự
        error_messages={'required': 'Vui lòng nhập lại mật khẩu mới.'},  # câu báo khi để trống
    )  # hết ô nhập lại

    def __init__(self, *args, user, **kwargs):  # nhận thêm User đang đổi mật khẩu
        super().__init__(*args, **kwargs)  # khởi tạo form như bình thường
        self.user = user  # giữ User để kiểm tra mật khẩu cũ và lưu mật khẩu mới

    def clean_mat_khau_cu(self):  # kiểm tra mật khẩu hiện tại
        mat_khau = self.cleaned_data['mat_khau_cu']  # mật khẩu người dùng vừa gõ
        if not self.user.check_password(mat_khau):  # so với chuỗi băm đã lưu
            raise ValidationError('Mật khẩu hiện tại không đúng.')  # báo sai
        return mat_khau  # trả mật khẩu hiện tại

    def clean_mat_khau_moi(self):  # kiểm tra mật khẩu mới theo luật chung của FRAMIE
        mat_khau = self.cleaned_data['mat_khau_moi']  # mật khẩu mới vừa gõ
        loi_mat_khau = kiem_tra_mat_khau(mat_khau, self.user)  # chạy mọi luật mật khẩu (dùng chung với đăng ký và quên mật khẩu)
        if loi_mat_khau:  # có ít nhất một lỗi
            raise ValidationError(loi_mat_khau)  # báo tất cả lỗi dưới ô
        return mat_khau  # trả mật khẩu hợp lệ

    def clean(self):  # so sánh chéo giữa các ô
        du_lieu = super().clean()  # lấy dữ liệu đã làm sạch
        moi, lai, cu = du_lieu.get('mat_khau_moi'), du_lieu.get('nhap_lai'), du_lieu.get('mat_khau_cu')  # ba mật khẩu (None nếu ô đó đã lỗi)
        if moi and lai and moi != lai:  # hai lần nhập mật khẩu mới không khớp
            self.add_error('nhap_lai', 'Mật khẩu nhập lại không khớp.')  # báo ở ô nhập lại
        elif moi and cu and moi == cu:  # mật khẩu mới trùng mật khẩu cũ
            self.add_error('mat_khau_moi', 'Mật khẩu mới phải khác mật khẩu hiện tại.')  # báo ở ô mật khẩu mới
        return du_lieu  # trả dữ liệu

    def save(self):  # lưu mật khẩu mới (Django tự băm)
        self.user.set_password(self.cleaned_data['mat_khau_moi'])  # băm và gán mật khẩu mới
        self.user.save(update_fields=['password'])  # chỉ lưu cột mật khẩu
        return self.user  # trả User đã lưu
