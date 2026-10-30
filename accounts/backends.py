from django.contrib.auth import get_user_model  # lấy model User của dự án (accounts.User)
from django.contrib.auth.backends import ModelBackend  # lớp xác thực mẫu của Django, ta kế thừa để sửa lại

User = get_user_model()  # gán model User vào biến để dùng bên dưới


class EmailBackend(ModelBackend):  # backend mới: cho phép đăng nhập bằng email thay vì username
    def authenticate(self, request, username=None, password=None, **kwargs):  # Django gọi hàm này khi người dùng bấm Đăng nhập
        if not username or not password:  # thiếu email hoặc thiếu mật khẩu
            return None  # None nghĩa là xác thực thất bại
        try:  # thử tìm tài khoản theo email
            user = User.objects.get(email__iexact=username.strip())  # iexact: không phân biệt chữ hoa/thường; strip bỏ khoảng trắng thừa
        except (User.DoesNotExist, User.MultipleObjectsReturned):  # không có email này (hoặc trùng bất thường)
            User().set_password(password)  # băm thử một mật khẩu để thời gian phản hồi giống nhau, tránh dò xem email có tồn tại không
            return None  # xác thực thất bại
        if user.check_password(password):  # so mật khẩu người dùng nhập với mật khẩu đã mã hóa trong DB
            return user  # đúng thì trả User; KHÔNG kiểm tra is_active ở đây để form còn báo "tài khoản bị khóa" (xem forms.py)
        return None  # sai mật khẩu thì thất bại
