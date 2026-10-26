from django import forms  # thư viện form của Django
from django.contrib.auth.forms import AuthenticationForm  # form đăng nhập mẫu của Django


class DangNhapForm(AuthenticationForm):  # kế thừa form mẫu, chỉ đổi chữ và kiểu ô nhập
    error_messages = {  # các câu báo lỗi của form
        'invalid_login': 'Email hoặc mật khẩu không chính xác',  # đúng chữ trong đặc tả, dùng cho cả sai email lẫn sai mật khẩu
        'inactive': 'Tài khoản của bạn đã bị khóa. Vui lòng liên hệ Quản trị viên.',  # tài khoản bị khóa (P7 sẽ dùng)
    }  # hết danh sách lỗi

    username = forms.EmailField(label='Email', max_length=100)  # đổi ô "username" thành ô email (name vẫn là username để backend nhận được)
    password = forms.CharField(  # ô mật khẩu
        label='Mật khẩu',  # nhãn hiển thị
        strip=False,  # không tự cắt khoảng trắng đầu/cuối mật khẩu
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),  # ô ẩn ký tự, gợi ý trình duyệt điền mật khẩu đã lưu
    )  # hết ô mật khẩu
