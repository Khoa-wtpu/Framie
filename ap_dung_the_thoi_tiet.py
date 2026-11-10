"""Chạy 1 lần ở thư mục gốc dự án:  python ap_dung_the_thoi_tiet.py
Gắn thẻ thời tiết mới (include dùng chung) vào 2 trang chi tiết Booking. Chạy lại lần 2 sẽ báo "đã áp dụng", không làm hỏng gì."""
import re
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parent
INC = '{% include "bookings/includes/the_thoi_tiet.html" %}'


def doc(p):
    return p.read_text(encoding='utf-8')


def ghi(p, s):
    p.write_text(s, encoding='utf-8', newline='')


loi = []

# 1) Trang Khách: dọn mọi dạng thẻ thời tiết cũ (khối E8 gốc / include ở cột phụ / include ngang), rồi đặt thẻ GỌN cạnh tiêu đề + dải nhắc dưới tiêu đề
p = GOC / 'bookings/templates/bookings/theo_doi_chi_tiet.html'
s = doc(p)
THE = '{% include "bookings/includes/the_thoi_tiet.html" with gon=True %}'
NHAC = '{% include "bookings/includes/the_thoi_tiet_nhac.html" %}'
if THE in s and NHAC in s:
    print('theo_doi_chi_tiet.html: đã áp dụng trước đó')
else:
    m2 = re.search(r'[ \t]*<section class="ct__the"[^>]*aria-label="Dự báo thời tiết buổi chụp".*?</section>', s, re.S)
    if m2:  # còn khối E8 gốc: cắt luôn cả cặp {% if the_thoi_tiet %} ... {% endif %} bao quanh
        truoc = s.rfind('{% if the_thoi_tiet %}', 0, m2.start())
        sau = s.find('{% endif %}', m2.end())
        if truoc != -1 and sau != -1 and s[truoc + len('{% if the_thoi_tiet %}'):m2.start()].strip() == '':
            s = s[:truoc] + s[sau + len('{% endif %}'):]
        else:
            s = s[:m2.start()] + s[m2.end():]
    # bỏ các include thẻ thời tiết đã chèn ở lần chạy script trước (cột phụ hoặc dạng ngang)
    s = re.sub(r'[ \t]*\{% include "bookings/includes/the_thoi_tiet(?:_nhac)?\.html"[^%]*%\}(?:\{#.*?#\})?[ \t]*\n(?:[ \t]*\n)?', '', s)
    neo_nut = '    <div class="ct__hanh-dong">'
    neo_het = '  </header>\n'
    if s.count(neo_nut) == 1 and s.count(neo_het) == 1:
        s = s.replace(neo_nut, '    ' + THE + '{# E8: thẻ dự báo thời tiết dạng gọn, cùng hàng với tiêu đề #}\n' + neo_nut)
        s = s.replace(neo_het, neo_het + '\n  ' + NHAC + '{# E8: dải nhắc đổi lịch (chỉ hiện khi khả năng mưa cao) #}\n')
        ghi(p, s)
        print('theo_doi_chi_tiet.html: đã đặt thẻ thời tiết gọn cạnh tiêu đề')
    else:
        loi.append('theo_doi_chi_tiet.html: không tìm thấy đúng 1 chỗ \'<div class="ct__hanh-dong">\' và 1 chỗ \'</header>\' (file có thể đã khác)')

# 2) Trang Nhiếp ảnh gia (nag_chi_tiet.html): đã được thay nguyên file ở bản này, không cần script sửa.

# 3) View của Nhiếp ảnh gia: thêm 'the_thoi_tiet' vào context
p = GOC / 'bookings/tiep_nhan.py'
s = doc(p)
if "'the_thoi_tiet'" in s:
    print('tiep_nhan.py: đã áp dụng trước đó')
else:
    neo = "'tong_gia': _tien(booking.TongGiaTri),"
    if s.count(neo) == 1:
        s = s.replace(neo, neo + "\n        'the_thoi_tiet': lay_the_thoi_tiet(booking, False, True),  # E8: thẻ dự báo thời tiết cho Nhiếp ảnh gia")
        dong_import = 'from bookings.the_thoi_tiet import lay_the_thoi_tiet\n'
        if dong_import not in s:
            vt = [mm.end() for mm in re.finditer(r'^(?:from|import) [^\n]*\n', s, re.M)]
            s = s[:vt[-1]] + dong_import + s[vt[-1]:]
        ghi(p, s)
        print('tiep_nhan.py: đã thêm the_thoi_tiet vào context')
    else:
        loi.append("tiep_nhan.py: không tìm thấy đúng 1 dòng 'tong_gia': _tien(booking.TongGiaTri),")

if loi:
    print('\nCÓ LỖI:\n- ' + '\n- '.join(loi))
    sys.exit(1)
print('\nXong. Chạy: python manage.py test bookings')
