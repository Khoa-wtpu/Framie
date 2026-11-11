# notifications/mau_email.py - P9 và P12: 28 nội dung mẫu theo TO-BE (Phanh). Các mẫu đánh dấu NGOÀI TO-BE là sự kiện nhóm bổ sung, đã hoặc đang chờ Khoa duyệt
MAU = {  # giá trị giả điền vào các chỗ trống
    'ten': 'Nguyễn Văn A',  # tên người liên quan
    'ma': 15,  # mã Booking
    'han': '18:00 06/11/2026',  # hạn đặt cọc, chọn ảnh hoặc thanh toán
    'ly_do': 'Lịch chụp bị trùng',  # lý do từ chối hoặc hủy
    'so_tien': '2.000.000đ',  # số tiền cọc hoặc phần còn lại
}  # hết giá trị giả

SU_KIEN = {  # khóa là tên sự kiện; giá trị là (tiêu đề, nội dung có chỗ trống)
    'ho_so_moi': ('Có hồ sơ mới chờ duyệt', 'Nhiếp ảnh gia {ten} vừa gửi hồ sơ. Vui lòng vào mục Duyệt hồ sơ để xem xét.'),  # gửi Quản trị viên
    'ho_so_duoc_duyet': ('Hồ sơ của bạn đã được duyệt', 'Hồ sơ của bạn đã được phê duyệt. Bạn có thể nhận Booking từ Khách hàng.'),  # gửi Nhiếp ảnh gia
    'ho_so_bi_tu_choi': ('Hồ sơ của bạn bị từ chối', 'Hồ sơ chưa được duyệt. Lý do: {ly_do}. Vui lòng chỉnh sửa và gửi lại.'),  # gửi Nhiếp ảnh gia
    'booking_moi': ('Bạn có Booking mới', 'Khách hàng {ten} vừa gửi Booking #{ma}. Vui lòng chấp nhận hoặc từ chối.'),  # gửi Nhiếp ảnh gia
    'booking_chap_nhan': ('Booking đã được chấp nhận', 'Booking #{ma} đã được chấp nhận. Vui lòng đặt cọc 40% trước {han}.'),  # gửi Khách hàng
    'booking_tu_choi': ('Booking bị từ chối', 'Booking #{ma} đã bị từ chối. Lý do: {ly_do}.'),  # gửi Khách hàng
    'nhac_dat_coc': ('Nhắc đặt cọc Booking', 'Booking #{ma} cần được đặt cọc 40% trước {han}.'),  # gửi Khách hàng
    'xac_nhan_coc': ('Đã xác nhận tiền cọc', 'Nhiếp ảnh gia đã nhận cọc {so_tien} cho Booking #{ma}. Lịch chụp chính thức được chốt.'),  # gửi Khách hàng
    'huy_chua_coc': ('Booking đã bị hủy', 'Booking #{ma} đã được hủy. Lý do: {ly_do}. Chưa phát sinh tiền cọc.'),  # gửi bên còn lại
    'huy_mat_coc': ('Khách hàng đã hủy Booking', 'Booking #{ma} bị hủy, lý do: {ly_do}. Khoản cọc {so_tien} không được hoàn.'),  # gửi Nhiếp ảnh gia
    'huy_hoan_coc': ('Nhiếp ảnh gia đã hủy Booking', 'Booking #{ma} bị hủy, lý do: {ly_do}. Nhiếp ảnh gia hoàn lại cọc {so_tien} cho bạn.'),  # gửi Khách hàng
    'minh_chung_coc': ('Có minh chứng đặt cọc', 'Khách hàng {ten} đã tải minh chứng cọc {so_tien} cho Booking #{ma}.'),  # gửi Nhiếp ảnh gia
    'minh_chung_60': ('Có minh chứng thanh toán 60%', 'Khách hàng {ten} đã tải minh chứng thanh toán {so_tien} cho Booking #{ma}.'),  # gửi Nhiếp ảnh gia
    'anh_chua_hau_ky': ('Ảnh gốc đã sẵn sàng để chọn', 'Vui lòng chọn ảnh cần hậu kỳ cho Booking #{ma} trước {han}.'),  # gửi Khách hàng
    'anh_da_hau_ky': ('Ảnh hậu kỳ đã sẵn sàng', 'Ảnh hậu kỳ của Booking #{ma} đã được tải lên. Vui lòng kiểm tra.'),  # gửi Khách hàng
    'yeu_cau_chinh_sua': ('Có yêu cầu chỉnh sửa ảnh', 'Khách hàng {ten} yêu cầu chỉnh sửa ảnh của Booking #{ma}.'),  # gửi Nhiếp ảnh gia
    'ban_giao_nag': ('Khách hàng đã xác nhận bàn giao', 'Khách hàng {ten} đã xác nhận hoàn tất bàn giao Booking #{ma}.'),  # gửi Nhiếp ảnh gia
    'ban_giao_kh': ('Vui lòng thanh toán phần còn lại', 'Bạn cần thanh toán {so_tien} cho Booking #{ma} trước {han}.'),  # gửi Khách hàng
    'thanh_toan': ('Đã xác nhận thanh toán', 'Ảnh hoàn chỉnh của Booking #{ma} có thể tải về trong 3 ngày.'),  # gửi Khách hàng
    'moi_danh_gia': ('Mời bạn đánh giá', 'Booking #{ma} đã hoàn thành. Mời bạn đánh giá Nhiếp ảnh gia.'),  # gửi Khách hàng
    'ho_so_nop_lai': ('Hồ sơ nhiếp ảnh gia vừa được cập nhật', '{ten} vừa cập nhật hồ sơ (lần nộp 2). Hồ sơ đang chờ bạn duyệt lại.'),  # gửi Quản trị viên
    'ho_so_chinh_sua': ('Hồ sơ của bạn cần chỉnh sửa', 'Quản trị viên yêu cầu bạn chỉnh sửa hồ sơ: {ly_do}. Vui lòng cập nhật và gửi lại hồ sơ.'),  # gửi Nhiếp ảnh gia (email là NGOÀI TO-BE, theo code của Khoa)
    'bo_sung_minh_chung': ('Nhiếp ảnh gia yêu cầu bổ sung minh chứng', 'Booking #{ma}: {ly_do}'),  # gửi Khách hàng, chỉ web, dùng cho cả cọc và 60%
    'khach_chon_xong_anh': ('Khách hàng đã chọn ảnh cần hậu kỳ', 'Khách hàng {ten} đã gửi danh sách ảnh cần hậu kỳ của Booking #{ma}.'),  # gửi Nhiếp ảnh gia, chỉ web
    'het_han_dat_coc': ('Booking #{ma} đã hết thời hạn đặt cọc', 'Booking #{ma} đã bị hủy tự động vì quá 1 ngày chưa đặt cọc. Khung giờ đã được trả về lịch trống.'),  # NGOÀI TO-BE: gửi cả hai bên, email chỉ cho Khách
    'qua_han_60': ('Booking #{ma}: quá hạn thanh toán', 'Khoản thanh toán 60% còn lại của Booking #{ma} đã quá hạn. Vui lòng liên hệ Nhiếp ảnh gia để được hỗ trợ.'),  # NGOÀI TO-BE: gửi cả hai bên, chỉ web
    'anh_het_han_tai': ('Ảnh Booking #{ma} đã hết hạn tải', 'Đã quá 3 ngày kể từ khi mở quyền tải, ảnh của Booking #{ma} đã được xóa khỏi hệ thống.'),  # NGOÀI TO-BE: gửi Khách hàng, chỉ web
    'xac_nhan_hoan_coc': ('Khách hàng đã nhận lại tiền cọc - Booking #{ma}', '{ten} đã xác nhận nhận lại {so_tien} tiền cọc của Booking #{ma}.'),  # NGOÀI TO-BE: gửi Nhiếp ảnh gia, web và email
}  # hết 28 sự kiện
