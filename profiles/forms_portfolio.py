# =====================================================================
# profiles/forms_portfolio.py  -  K5: form thêm / sửa project Portfolio (UC1.3) (Khoa)
#
#   ProjectForm(request.POST or None, request.FILES or None, nag=nag, instance=project_hoac_None)
#   Lưu: form.save() -> gán chủ project, xóa các hình đã đánh dấu, sắp lại thứ tự theo số đã nhập,
#        rồi nối các hình mới vào cuối danh sách. Tất cả trong MỘT lần bấm Lưu.
#   Tên ô trong form sửa: thu_tu_<mã hình> (vị trí mong muốn), xoa_hinh (mã các hình cần gỡ).
#
# Quy tắc (wireframe C1.5): Tên project, Loại hình, Ngày chụp, Ảnh bìa bắt buộc; Concept không bắt buộc.
# Ảnh bìa JPG/PNG tối đa 5MB. Hình trong project JPG/PNG tối đa 10MB/hình, mỗi project cần ít nhất 1 hình.
# =====================================================================
from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Max
from django.utils import timezone

from profiles.models import CHI_NHAN_ANH, HinhAnhProject, LoaiHinhChup, Project

TOI_DA_ANH_BIA = 5 * 1024 * 1024        # ảnh bìa tối đa 5MB
TOI_DA_MOI_HINH = 10 * 1024 * 1024      # mỗi hình trong project tối đa 10MB
TOI_DA_HINH_MOI_PROJECT = 30            # một project tối đa 30 hình
DINH_DANG_CHO_PHEP = ('JPEG', 'PNG')


def xoa_file_neu_khong_dung(kho, ten_file):
    """Xóa file ảnh khỏi ổ đĩa khi KHÔNG còn dòng dữ liệu nào trỏ tới nó (chạy sau khi giao dịch xong).
    Lỗi khi xóa file chỉ bỏ qua, không làm hỏng thao tác chính."""
    def xoa():
        if (Project.objects.filter(AnhBia=ten_file).exists()
                or HinhAnhProject.objects.filter(DuongDanHinhAnh=ten_file).exists()):
            return
        try:
            kho.delete(ten_file)
        except OSError:
            pass
    transaction.on_commit(xoa)


class _NhieuAnhInput(forms.FileInput):
    allow_multiple_selected = True       # cho chọn nhiều file cùng lúc


class _NhieuAnhField(forms.ImageField):
    widget = _NhieuAnhInput

    def clean(self, data, initial=None):
        if not data:
            return []
        cac_tep = data if isinstance(data, (list, tuple)) else [data]
        return [super(_NhieuAnhField, self).clean(tep, initial) for tep in cac_tep]


class ProjectForm(forms.ModelForm):
    anh_moi = _NhieuAnhField(required=False, label='Hình ảnh trong project')

    class Meta:
        model = Project
        fields = ['TenProject', 'MaLoaiHinh', 'NgayChup', 'Concept', 'AnhBia']
        labels = {'TenProject': 'Tên project', 'MaLoaiHinh': 'Loại hình chụp',
                  'NgayChup': 'Ngày chụp', 'Concept': 'Concept', 'AnhBia': 'Ảnh bìa'}
        help_texts = {'AnhBia': 'JPG, PNG · tối đa 5 MB'}
        widgets = {
            'TenProject': forms.TextInput(attrs={'placeholder': 'Nhập tên project'}),
            'NgayChup': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'Concept': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Mô tả concept, ý tưởng của project'}),
            'AnhBia': forms.FileInput(attrs={'accept': 'image/png,image/jpeg'}),
        }
        error_messages = {
            'TenProject': {'required': 'Vui lòng nhập tên project.'},
            'MaLoaiHinh': {'required': 'Vui lòng chọn loại hình chụp.'},
            'NgayChup': {'required': 'Vui lòng chọn ngày chụp.', 'invalid': 'Ngày chụp không hợp lệ.'},
            'AnhBia': {'required': 'Vui lòng tải ảnh bìa.'},
        }

    def __init__(self, *args, nag, **kwargs):
        super().__init__(*args, **kwargs)
        self.nag = nag
        self.fields['NgayChup'].required = True            # model cho phép trống, wireframe bắt buộc
        self.fields['MaLoaiHinh'].queryset = LoaiHinhChup.objects.all()
        self.fields['MaLoaiHinh'].empty_label = 'Chọn loại hình chụp'
        self.fields['anh_moi'].widget.attrs.update({'accept': 'image/png,image/jpeg', 'multiple': True})
        self._anh_bia_cu = self.instance.AnhBia.name if self.instance.pk else ''
        self.hinh_hien_co = list(self.instance.hinh_anh.order_by('ThuTu')) if self.instance.pk else []

    def clean_TenProject(self):
        ten = ' '.join(self.cleaned_data['TenProject'].split())
        if not ten:
            raise ValidationError('Vui lòng nhập tên project.')
        return ten

    def clean_NgayChup(self):
        ngay = self.cleaned_data['NgayChup']
        if ngay and ngay > timezone.localdate():
            raise ValidationError('Ngày chụp không được ở tương lai.')
        return ngay

    def clean_AnhBia(self):
        tep = self.cleaned_data.get('AnhBia')
        if hasattr(tep, 'size') and getattr(tep, 'image', None) is not None:    # chỉ kiểm file MỚI tải lên
            if tep.size > TOI_DA_ANH_BIA:
                raise ValidationError('Ảnh bìa không được lớn hơn 5MB.')
            if tep.image.format not in DINH_DANG_CHO_PHEP:
                raise ValidationError('Chỉ nhận ảnh JPG hoặc PNG.')
        return tep

    def clean_anh_moi(self):
        cac_tep = self.cleaned_data['anh_moi']
        for tep in cac_tep:
            CHI_NHAN_ANH(tep)                             # đuôi .jpg / .jpeg / .png
            if tep.image.format not in DINH_DANG_CHO_PHEP:
                raise ValidationError(f'"{tep.name}": chỉ nhận ảnh JPG hoặc PNG.')
            if tep.size > TOI_DA_MOI_HINH:
                raise ValidationError(f'"{tep.name}": mỗi hình không được lớn hơn 10MB.')
        return cac_tep

    # ---- thứ tự và hình cần xóa (đọc từ dữ liệu người dùng gửi lên) ----
    def _doc_hinh_can_xoa(self):
        gui_len = self.data.getlist('xoa_hinh') if hasattr(self.data, 'getlist') else []
        hop_le = {str(h.pk) for h in self.hinh_hien_co}      # chỉ nhận mã hình CỦA project này
        return {int(ma) for ma in gui_len if ma in hop_le}

    def _doc_vi_tri(self):
        """{mã hình: số người dùng nhập}; ô trống thì không có khóa. Số sai -> ném ValueError."""
        ket_qua = {}
        for hinh in self.hinh_hien_co:
            tho = str(self.data.get(f'thu_tu_{hinh.pk}', '')).strip()
            if tho == '':
                continue
            if not tho.isascii() or not tho.isdigit() or int(tho) < 1:
                raise ValueError(tho)
            ket_qua[hinh.pk] = int(tho)
        return ket_qua

    def _xep_hinh(self, cac_hinh, vi_tri):
        """Hình nào có nhập số thì được CHÈN vào đúng vị trí đó giữa các hình còn lại (như kéo thả);
        hình không nhập số giữ thứ tự cũ. Số trùng hoặc quá lớn vẫn ra kết quả 1..n hợp lệ."""
        ket_qua = [h for h in cac_hinh if h.pk not in vi_tri]            # hình không nhập số, giữ thứ tự cũ
        co_so = sorted((h for h in cac_hinh if h.pk in vi_tri), key=lambda h: (vi_tri[h.pk], h.ThuTu))
        for hinh in co_so:
            ket_qua.insert(min(vi_tri[hinh.pk] - 1, len(ket_qua)), hinh)
        return ket_qua

    def hinh_de_hien_thi(self):
        """Danh sách cho template: [{'hinh', 'vi_tri', 'xoa'}]. Form lỗi được hiện lại vẫn giữ số và dấu xóa vừa nhập."""
        xoa, vi_tri = set(), {}
        if self.is_bound:
            xoa = self._doc_hinh_can_xoa()
            try:
                vi_tri = self._doc_vi_tri()
            except ValueError:
                vi_tri = {}
        return [{'hinh': h, 'vi_tri': i, 'xoa': h.pk in xoa}
                for i, h in enumerate(self._xep_hinh(self.hinh_hien_co, vi_tri), start=1)]

    def clean(self):
        data = super().clean()
        try:
            self._vi_tri = self._doc_vi_tri()
        except ValueError:
            self._vi_tri = {}
            self.add_error(None, 'Thứ tự hình phải là số nguyên từ 1 trở lên.')
        self._xoa = self._doc_hinh_can_xoa()
        if 'anh_moi' in data:                              # bỏ qua khi ô hình đã tự báo lỗi
            tong = len(self.hinh_hien_co) - len(self._xoa) + len(data['anh_moi'])
            if tong == 0:
                self.add_error('anh_moi', 'Vui lòng giữ hoặc tải lên ít nhất một hình cho project.'
                               if self.hinh_hien_co else 'Vui lòng tải lên ít nhất một hình cho project.')
            elif tong > TOI_DA_HINH_MOI_PROJECT:
                self.add_error('anh_moi', f'Mỗi project tối đa {TOI_DA_HINH_MOI_PROJECT} hình.')
        return data

    def save(self, commit=True):
        file_can_don = []
        with transaction.atomic():
            project = super().save(commit=False)
            project.MaNhiepAnhGia = self.nag
            project.save()
            con_lai = []
            for hinh in self.hinh_hien_co:                     # 1) gỡ các hình đã đánh dấu xóa
                if hinh.pk in self._xoa:
                    file_can_don.append((hinh.DuongDanHinhAnh.storage, hinh.DuongDanHinhAnh.name))
                    hinh.delete()
                else:
                    con_lai.append(hinh)
            if con_lai:                                        # 2) sắp lại thứ tự 1..n
                # Đẩy tất cả ra xa trước, để lúc gán số mới không bao giờ trùng thứ tự với hình khác.
                project.hinh_anh.update(ThuTu=F('ThuTu') + 1000000)
                for vi_tri, hinh in enumerate(self._xep_hinh(con_lai, self._vi_tri), start=1):
                    HinhAnhProject.objects.filter(pk=hinh.pk).update(ThuTu=vi_tri)
            thu_tu = len(con_lai)
            for tep in self.cleaned_data['anh_moi']:           # 3) hình mới nối vào CUỐI danh sách
                thu_tu += 1
                HinhAnhProject.objects.create(MaProject=project, DuongDanHinhAnh=tep, ThuTu=thu_tu)
        for kho, ten_file in file_can_don:                     # dọn file trên ổ đĩa sau khi lưu thành công
            xoa_file_neu_khong_dung(kho, ten_file)
        if self._anh_bia_cu and project.AnhBia.name != self._anh_bia_cu:     # thay ảnh bìa -> dọn file cũ
            xoa_file_neu_khong_dung(project.AnhBia.storage, self._anh_bia_cu)
        return project
