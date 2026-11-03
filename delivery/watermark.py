# delivery/watermark.py - N4 / UC5.3 bước 6: chèn Watermark vào ảnh (chỉ dùng thư viện Pillow, không cần Django)
import io                                                    # BytesIO: "tệp" nằm trong bộ nhớ, để ghi kết quả ra bytes

from PIL import Image, ImageDraw, ImageFont, ImageOps        # Image: mở/lưu ảnh; ImageDraw: vẽ chữ; ImageFont: phông chữ; ImageOps: xoay ảnh theo EXIF

CHU_WATERMARK = 'FRAMIE'                                     # chữ đóng dấu lên ảnh (muốn đổi chữ thì sửa ở đây)
GIOI_HAN_GIAY = 5                                            # N5: mỗi ảnh phải xử lý xong trong tối đa 5 giây (services.py đo và ghi cảnh báo nếu vượt)


def _phong_chu(co_chu):                                      # lấy phông chữ có kích cỡ mong muốn
    try:
        return ImageFont.load_default(size=co_chu)           # Pillow mới: phông mặc định đổi được kích cỡ
    except TypeError:                                        # Pillow cũ không có tham số size
        return ImageFont.load_default()


def _con_dau(rong, cao):                                     # tạo 1 "con dấu" chữ FRAMIE đã xoay nghiêng, nền trong suốt
    co_chu = max(24, int(min(rong, cao) * 0.07))             # cỡ chữ tỉ lệ với ảnh (khoảng 7% cạnh ngắn)
    phong = _phong_chu(co_chu)
    ben_trai, ben_tren, ben_phai, ben_duoi = phong.getbbox(CHU_WATERMARK)  # kích thước vùng chứa chữ
    dai, cao_chu = ben_phai - ben_trai, ben_duoi - ben_tren
    le = max(4, co_chu // 8)                                 # chừa lề để bóng chữ không bị cắt
    tam = Image.new('RGBA', (dai + 2 * le, cao_chu + 2 * le), (0, 0, 0, 0))   # tấm nền trong suốt
    ve = ImageDraw.Draw(tam)
    ve.text((le - ben_trai + 2, le - ben_tren + 2), CHU_WATERMARK, font=phong, fill=(0, 0, 0, 80))        # bóng đen mờ (để đọc được trên nền sáng)
    ve.text((le - ben_trai, le - ben_tren), CHU_WATERMARK, font=phong, fill=(255, 255, 255, 120))         # chữ trắng mờ
    return tam.rotate(30, resample=Image.BICUBIC, expand=True)  # xoay nghiêng 30 độ


def chen_watermark(tep, dinh_dang):                          # hàm chính: nhận tệp ảnh, trả về BYTES ảnh đã đóng dấu
    """tep: tệp ảnh (file-like). dinh_dang: 'PNG' thì xuất PNG, còn lại xuất JPEG."""
    tep.seek(0)                                              # về đầu tệp (phòng khi đã bị đọc trước đó)
    anh = Image.open(tep)                                    # mở ảnh
    anh = ImageOps.exif_transpose(anh)                       # xoay đúng chiều theo thông tin máy ảnh (ảnh chụp dọc)
    nen = anh.convert('RGBA')                                # chuyển về hệ màu có kênh trong suốt để chồng lớp
    rong, cao = nen.size
    dau = _con_dau(rong, cao)
    buoc_x, buoc_y = int(dau.width * 1.5), int(dau.height * 1.6)   # khoảng cách giữa các con dấu
    for hang, y in enumerate(range(-dau.height // 2, cao, buoc_y)):  # duyệt từng hàng
        lech = buoc_x // 2 if hang % 2 else 0                # hàng lẻ lệch nửa bước cho đẹp
        for x in range(-dau.width // 2 + lech, rong, buoc_x):
            if x < rong and y < cao:                         # con dấu còn nằm trong ảnh
                nen.alpha_composite(dau, (max(x, 0), max(y, 0)), (max(-x, 0), max(-y, 0)))  # dán con dấu, tự cắt phần tràn ra ngoài
    ket_qua = nen                                             # watermark đã được dán trực tiếp lên nền để tiết kiệm RAM
    dem = io.BytesIO()
    if dinh_dang == 'PNG':
        ket_qua.save(dem, 'PNG', compress_level=3)           # PNG giữ nguyên định dạng (nén vừa phải để kịp 5 giây, không dùng optimize vì rất chậm)
    else:
        ket_qua.convert('RGB').save(dem, 'JPEG', quality=88)   # JPEG không có kênh trong suốt nên đổi về RGB
    return dem.getvalue()
