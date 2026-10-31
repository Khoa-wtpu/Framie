# profiles/views_portfolio.py - K5: quản lý Portfolio của nhiếp ảnh gia (UC1.3)
#   /portfolio/                        danh sách project            (name='portfolio', khớp menu)
#   /portfolio/them/                   thêm project                 (name='project_them')
#   /portfolio/<pk>/sua/               sửa project + sắp xếp hình   (name='project_sua')
#   /portfolio/<pk>/xoa/               hỏi xác nhận rồi xóa         (name='project_xoa')
# Chỉ nhiếp ảnh gia có hồ sơ 'Đã duyệt' mới dùng được; chỉ thấy và sửa project CỦA MÌNH.
from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from profiles.decorators import nhiep_anh_gia_da_duyet
from profiles.forms_portfolio import ProjectForm, xoa_file_neu_khong_dung
from profiles.models import Project


def _ve_portfolio():
    return redirect('portfolio')


@nhiep_anh_gia_da_duyet
def portfolio(request, nag):
    cac_project = (Project.objects.filter(MaNhiepAnhGia=nag).select_related('MaLoaiHinh')
                   .annotate(so_hinh=Count('hinh_anh')))
    return render(request, 'profiles/portfolio_danh_sach.html', {'cac_project': cac_project})


@nhiep_anh_gia_da_duyet
def project_them(request, nag):
    form = ProjectForm(request.POST or None, request.FILES or None, nag=nag)
    if request.method == 'POST' and form.is_valid():
        project = form.save()
        messages.success(request, f'Đã thêm project "{project.TenProject}".')
        return _ve_portfolio()
    return render(request, 'profiles/portfolio_form.html', {'form': form, 'project': None})


@nhiep_anh_gia_da_duyet
def project_sua(request, nag, pk):
    project = get_object_or_404(Project, pk=pk, MaNhiepAnhGia=nag)      # project của người khác -> 404
    form = ProjectForm(request.POST or None, request.FILES or None, nag=nag, instance=project)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Đã lưu project "{project.TenProject}".')
        return _ve_portfolio()
    return render(request, 'profiles/portfolio_form.html', {
        'form': form, 'project': project, 'cac_hinh': form.hinh_de_hien_thi()})


@nhiep_anh_gia_da_duyet
def project_xoa(request, nag, pk):
    project = get_object_or_404(Project, pk=pk, MaNhiepAnhGia=nag)
    if request.method == 'POST':
        ten = project.TenProject
        cac_file = [(project.AnhBia.storage, project.AnhBia.name)] + [
            (h.DuongDanHinhAnh.storage, h.DuongDanHinhAnh.name) for h in project.hinh_anh.all()]
        with transaction.atomic():
            project.delete()                                   # xóa project thì xóa luôn các hình bên trong
            for kho, ten_file in cac_file:
                xoa_file_neu_khong_dung(kho, ten_file)         # dọn file trên ổ đĩa sau khi xóa thành công
        messages.success(request, f'Đã xóa project "{ten}" cùng các hình ảnh bên trong.')
        return _ve_portfolio()
    return render(request, 'profiles/portfolio_xoa.html', {'project': project})
