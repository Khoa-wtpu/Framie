import unicodedata  # chuẩn hóa chữ tiếng Việt về một dạng duy nhất (dấu dựng sẵn) trước khi kiểm tra

from django.core.exceptions import ValidationError  # lỗi chuẩn của Django để báo mật khẩu không hợp lệ


class DoPhucTapMatKhau:  # luật độ phức tạp mật khẩu của FRAMIE (P4)
    """Mật khẩu phải có chữ hoa, chữ thường, số và ký tự đặc biệt (chữ có dấu không tính là ký tự đặc biệt)."""  # mô tả ngắn

    def validate(self, password, user=None):  # hàm Django gọi để kiểm tra; user có thể không dùng đến
        mk = unicodedata.normalize('NFC', password)  # đưa về dạng dựng sẵn: "ẩ" là MỘT ký tự chữ, không bị tách thành chữ + dấu
        loi = []  # danh sách các thông báo lỗi còn thiếu
        if not any(c.isupper() for c in mk):  # không có chữ hoa nào (tính cả chữ hoa có dấu như "Ấ")
            loi.append('Mật khẩu phải có ít nhất một chữ hoa.')  # ghi nhận thiếu chữ hoa
        if not any(c.islower() for c in mk):  # không có chữ thường nào (tính cả "ẩ", "ê"...)
            loi.append('Mật khẩu phải có ít nhất một chữ thường.')  # ghi nhận thiếu chữ thường
        if not any(c in '0123456789' for c in mk):  # không có chữ số 0-9
            loi.append('Mật khẩu phải có ít nhất một chữ số.')  # ghi nhận thiếu số
        if not any(not c.isalnum() and not c.isspace() for c in mk):  # không có ký tự nào vừa không phải chữ/số, vừa không phải khoảng trắng
            loi.append('Mật khẩu phải có ít nhất một ký tự đặc biệt.')  # ghi nhận thiếu ký tự đặc biệt
        if loi:  # có ít nhất một loại ký tự bị thiếu
            raise ValidationError(loi)  # ném tất cả lỗi cùng lúc để form hiển thị đầy đủ

    def get_help_text(self):  # Django dùng để hiển thị gợi ý quy tắc cho người dùng
        return 'Mật khẩu phải có chữ hoa, chữ thường, số và ký tự đặc biệt.'  # gợi ý hiển thị