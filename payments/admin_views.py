from django import forms
from django.core.paginator import Paginator
from django.db.models import F, Prefetch, Q
from django.shortcuts import render

from accounts.permissions import chi_quan_tri_vien
from core.constants import TrangThaiThanhToan
from payments.models import MinhChungThanhToan, ThanhToan


SO_DONG_MOI_TRANG = 10

TAB_TAT_CA = "tat_ca"
TAB_CHO_XAC_NHAN = "cho_xac_nhan"
TAB_DA_XAC_NHAN = "da_xac_nhan"
TAB_QUA_HAN = "qua_han"

TRANG_THAI_CHO_XAC_NHAN = (
    TrangThaiThanhToan.CHO_XAC_NHAN_COC,
    TrangThaiThanhToan.CHO_XAC_NHAN_60,
)
TRANG_THAI_DA_XAC_NHAN = (
    TrangThaiThanhToan.DA_DAT_COC,
    TrangThaiThanhToan.DA_THANH_TOAN,
)

TB_CHUA_CO_THANH_TOAN = "Chưa có khoản thanh toán nào."
TB_KHONG_KHOP_BO_LOC = "Không có khoản thanh toán nào khớp bộ lọc."


class BoLocThanhToanForm(forms.Form):
    """Tìm kiếm + bộ lọc của trang Quản lý thanh toán (GET) - cùng kiểu BoLocBookingQuanTriForm của trang Booking.
    Giá trị sai/lạ trên URL bị bỏ qua chứ không gây lỗi trang."""

    q = forms.CharField(
        label="Từ khóa (mã thanh toán, mã Booking, tên hoặc email)", required=False, max_length=100,
        widget=forms.TextInput(attrs={
            "placeholder": "Tìm theo mã Booking, mã thanh toán, tên hoặc email",
            "autocomplete": "off", "type": "search",
        }),
    )
    tu_ngay = forms.DateField(
        label="Gửi từ ngày", required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        error_messages={"invalid": "Ngày bắt đầu không hợp lệ."},
    )
    den_ngay = forms.DateField(
        label="Gửi đến ngày", required=False,
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        error_messages={"invalid": "Ngày kết thúc không hợp lệ."},
    )
    trang_thai = forms.MultipleChoiceField(
        label="Trạng thái thanh toán", required=False,
        widget=forms.CheckboxSelectMultiple, choices=TrangThaiThanhToan.CHOICES,
    )
    sap_xep = forms.ChoiceField(
        label="Sắp xếp", required=False,
        choices=[("moi", "Mới nhất trước"), ("cu", "Cũ nhất trước")],
    )

    def clean(self):
        du_lieu = super().clean()
        tu, den = du_lieu.get("tu_ngay"), du_lieu.get("den_ngay")
        if tu and den and tu > den:
            self.add_error("den_ngay", "Ngày kết thúc phải sau hoặc cùng ngày bắt đầu.")
        return du_lieu


def _so_bo_loc(du_lieu):
    """Mỗi trạng thái được tích tính 1, khoảng ngày tính 1. Từ khóa và sắp xếp không tính."""
    return len(du_lieu.get("trang_thai") or []) + (1 if (du_lieu.get("tu_ngay") or du_lieu.get("den_ngay")) else 0)


def _loc_theo_tab(queryset, tab):
    if tab == TAB_CHO_XAC_NHAN:
        return queryset.filter(TrangThai__in=TRANG_THAI_CHO_XAC_NHAN)
    if tab == TAB_DA_XAC_NHAN:
        return queryset.filter(TrangThai__in=TRANG_THAI_DA_XAC_NHAN)
    if tab == TAB_QUA_HAN:
        return queryset.filter(TrangThai=TrangThaiThanhToan.QUA_HAN)
    return queryset


def _loc_thanh_toan(ds, du_lieu):
    """Áp tìm kiếm + bộ lọc (cleaned_data) + sắp xếp lên danh sách khoản thanh toán. Lọc ngày theo NgayThanhToan (lúc gửi)."""
    for tu in (du_lieu.get("q") or "").split():
        dieu_kien = Q()
        for tien_to in ("MaBooking__MaKhachHang", "MaBooking__MaNhiepAnhGia__MaTaiKhoan"):
            for cot in ("username", "email", "first_name", "last_name"):
                dieu_kien |= Q(**{f"{tien_to}__{cot}__icontains": tu})
        if tu.lstrip("#").isdigit():
            ma = int(tu.lstrip("#"))
            dieu_kien |= Q(pk=ma) | Q(MaBooking_id=ma)
        ds = ds.filter(dieu_kien)
    if du_lieu.get("tu_ngay"):
        ds = ds.filter(NgayThanhToan__date__gte=du_lieu["tu_ngay"])
    if du_lieu.get("den_ngay"):
        ds = ds.filter(NgayThanhToan__date__lte=du_lieu["den_ngay"])
    if du_lieu.get("trang_thai"):
        ds = ds.filter(TrangThai__in=du_lieu["trang_thai"])
    if du_lieu.get("sap_xep") == "cu":
        return ds.order_by(F("NgayThanhToan").asc(nulls_last=True), "MaThanhToan")
    return ds.order_by(F("NgayThanhToan").desc(nulls_last=True), "-MaThanhToan")


@chi_quan_tri_vien
def quan_ly_thanh_toan(request):
    """Danh sách khoản thanh toán dành riêng cho Quản trị viên (bố cục giống trang "Tất cả Booking")."""
    tat_ca = ThanhToan.objects.all()
    so_tat_ca = tat_ca.count()
    so_cho_xac_nhan = tat_ca.filter(TrangThai__in=TRANG_THAI_CHO_XAC_NHAN).count()
    so_da_xac_nhan = tat_ca.filter(TrangThai__in=TRANG_THAI_DA_XAC_NHAN).count()
    so_qua_han = tat_ca.filter(TrangThai=TrangThaiThanhToan.QUA_HAN).count()

    tab = request.GET.get("tab", TAB_TAT_CA)
    if tab not in (TAB_TAT_CA, TAB_CHO_XAC_NHAN, TAB_DA_XAC_NHAN, TAB_QUA_HAN):
        tab = TAB_TAT_CA

    bo_loc = BoLocThanhToanForm(request.GET)
    bo_loc.is_valid()  # ô sai bị bỏ khỏi cleaned_data -> coi như không lọc
    du_lieu = bo_loc.cleaned_data

    ds = (ThanhToan.objects
          .select_related(
              "MaBooking",
              "MaBooking__MaKhachHang",
              "MaBooking__MaNhiepAnhGia",
              "MaBooking__MaNhiepAnhGia__MaTaiKhoan",
              "MaBooking__MaGoi",
          )
          .prefetch_related(
              Prefetch(
                  "minh_chungs",
                  queryset=MinhChungThanhToan.objects
                  .filter(Q(MaThanhToan__NgayXacNhan__isnull=True)
                          | Q(NgayTaiLen__lte=F("MaThanhToan__NgayXacNhan")))
                  .order_by("-NgayTaiLen", "-MaMinhChung"),
                  to_attr="minh_chungs_moi_nhat_truoc",
              )
          ))
    ds = _loc_theo_tab(ds, tab)
    ds = _loc_thanh_toan(ds, du_lieu)

    so_bo_loc = _so_bo_loc(du_lieu)
    page_obj = Paginator(ds, SO_DONG_MOI_TRANG).get_page(request.GET.get("page"))
    for tt in page_obj:  # số tiền có dấu chấm ngăn nghìn (1.020.000), không phụ thuộc cấu hình ngôn ngữ
        tt.so_tien_hien = f"{int(tt.SoTien):,}".replace(",", ".")

    return render(request, "payments/admin_quan_ly_thanh_toan.html", {
        "tieu_de": "Quản lý thanh toán",
        "page_obj": page_obj,
        "tab": tab,
        "so_tat_ca": so_tat_ca,
        "so_cho_xac_nhan": so_cho_xac_nhan,
        "so_da_xac_nhan": so_da_xac_nhan,
        "so_qua_han": so_qua_han,
        "bo_loc": bo_loc,
        "so_bo_loc": so_bo_loc,
        "dang_loc": bool(so_bo_loc or du_lieu.get("q")),
        "sap_xep_chon": du_lieu.get("sap_xep") or "moi",
        "so_ket_qua": page_obj.paginator.count,
        "co_thanh_toan": so_tat_ca > 0,
        "TAB_TAT_CA": TAB_TAT_CA,
        "TAB_CHO_XAC_NHAN": TAB_CHO_XAC_NHAN,
        "TAB_DA_XAC_NHAN": TAB_DA_XAC_NHAN,
        "TAB_QUA_HAN": TAB_QUA_HAN,
        "TB_CHUA_CO_THANH_TOAN": TB_CHUA_CO_THANH_TOAN,
        "TB_KHONG_KHOP_BO_LOC": TB_KHONG_KHOP_BO_LOC,
    })
