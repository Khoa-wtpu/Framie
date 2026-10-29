import re  # thư viện biểu thức chính quy, dùng để dò từng loại ký tự trong mật khẩu

from django.core.exceptions import ValidationError  # lỗi chuẩn của Django để báo mật khẩu không hợp lệ


class DoPhucTapMatKhau:  # luật độ phức tạp mật khẩu của FRAMIE (P4)
    """Mật khẩu phải có chữ hoa, chữ thường, số và ký tự đặc biệt."""  # mô tả ngắn cho người đọc code

    def validate(self, password, user=None):  # hàm Django gọi để kiểm tra; user có thể không dùng đến
        loi = []  # danh sách các thông báo lỗi còn thiếu
        if not re.search(r'[A-Z]', password):  # không có chữ hoa
            loi.append('Mật khẩu phải có ít nhất một chữ hoa.')  # ghi nhận thiếu chữ hoa
        if not re.search(r'[a-z]', password):  # không có chữ thường
            loi.append('Mật khẩu phải có ít nhất một chữ thường.')  # ghi nhận thiếu chữ thường
        if not re.search(r'[0-9]', password):  # không có chữ số
            loi.append('Mật khẩu phải có ít nhất một chữ số.')  # ghi nhận thiếu số
        if not re.search(r'[^A-Za-z0-9]', password):  # không có ký tự nào ngoài chữ và số
            loi.append('Mật khẩu phải có ít nhất một ký tự đặc biệt.')  # ghi nhận thiếu ký tự đặc biệt
        if loi:  # có ít nhất một loại ký tự bị thiếu
            raise ValidationError(loi)  # ném tất cả lỗi cùng lúc để form hiển thị đầy đủ

    def get_help_text(self):  # Django dùng để hiển thị gợi ý quy tắc cho người dùng
        return 'Mật khẩu phải có chữ hoa, chữ thường, số và ký tự đặc biệt.'  # gợi ý hiển thị
