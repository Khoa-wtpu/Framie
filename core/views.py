from django import forms
from django.core.paginator import Paginator
from django.shortcuts import render

from .constants import TrangThaiBooking, TrangThaiHoSo, TrangThaiSlot, TrangThaiThanhToan


class DemoForm(forms.Form):
    ho_ten = forms.CharField(label="Họ và tên", help_text="Như trên giấy tờ tùy thân.")
    email = forms.EmailField(label="Email")
    goi = forms.ChoiceField(label="Gói dịch vụ", choices=[("", "Chọn gói"), ("c", "Chân dung"), ("g", "Gia đình")])
    ghi_chu = forms.CharField(label="Ghi chú", widget=forms.Textarea(attrs={"rows": 3}), required=False)


def ui_kit(request):
    """Trang xem thử toàn bộ thành phần giao diện (chỉ nên mở khi DEBUG)."""
    return render(request, "ui_kit.html", {
        "page_obj": Paginator(range(1, 201), 10).get_page(request.GET.get("page", 5)),
        "form": DemoForm({"ho_ten": "Nguyễn Văn A", "email": "abc"}),  # email sai để xem trạng thái lỗi
        "status_groups": [
            ("Booking", TrangThaiBooking.ALL),
            ("Hồ sơ Nhiếp ảnh gia", [TrangThaiHoSo.CHO_DUYET, TrangThaiHoSo.DA_DUYET, TrangThaiHoSo.DA_TU_CHOI]),
            ("Slot lịch", [TrangThaiSlot.TRONG, TrangThaiSlot.DANG_GIU, TrangThaiSlot.DA_DAT]),
            ("Thanh toán", [v for k, v in vars(TrangThaiThanhToan).items() if k.isupper() and k != "CHOICES"]),
        ],
    })
