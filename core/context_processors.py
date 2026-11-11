from django.conf import settings

from core.constants import TrangThaiHoSo

from .navigation import (ACCOUNT_MENUS, CUSTOMER, GUEST, MENUS, PHOTOGRAPHER, PREVIEW_KEYS,
                         URL_NAMES, count_unread, get_role, is_active, resolve)


def layout(request):
    user = request.user
    role = get_role(user)
    preview = False
    key = request.GET.get("xem_voi_vai_tro") if settings.DEBUG else None
    # Xem thử riêng: Nhiếp ảnh gia chưa được duyệt (Chờ duyệt / Đã từ chối)
    pending_preview = key == "nhiep_anh_gia_cho_duyet"
    forced = PHOTOGRAPHER if pending_preview else PREVIEW_KEYS.get(key)
    if forced:
        role, preview = forced, True

    logged_in = role != GUEST
    if user.is_authenticated:
        name = user.get_full_name() or user.get_username()
        unread = count_unread(user)
    else:
        name = "Người dùng demo" if logged_in else ""
        unread = 3 if preview and logged_in else 0

    def build(items):
        out = []
        for label, url_name in items:
            url = resolve(url_name)
            out.append({"label": label, "url": url, "active": is_active(request.path, url)})
        return out

    # Kế hoạch (P5) và wireframe: Nhiếp ảnh gia "Chờ duyệt" / "Đã từ chối" chỉ được dùng chức năng theo dõi hồ sơ.
    menu = MENUS[role]
    chua_duyet = pending_preview or (user.is_authenticated
                                     and user.trang_thai_ho_so != TrangThaiHoSo.DA_DUYET)
    if role == PHOTOGRAPHER and chua_duyet:
        menu = [m for m in menu if m[1] in ("photographer_profile", "about")]   # chỉ theo dõi hồ sơ + trang Giới thiệu (chỉ đọc)

    # Ảnh đại diện trên header: Nhiếp ảnh gia có AnhDaiDien thì hiện ảnh, không có thì hiện chữ cái đầu.
    avatar_url = ""
    if user.is_authenticated and role == PHOTOGRAPHER and not preview:
        try:
            anh = user.ho_so_nhiep_anh_gia.AnhDaiDien
            avatar_url = anh.url if anh else ""
        except Exception:  # chưa có hồ sơ Nhiếp ảnh gia hoặc file ảnh lỗi: dùng chữ cái đầu
            avatar_url = ""

    return {
        "role": role,
        "can_search": role in (GUEST, CUSTOMER),   # chỉ khách vãng lai và Khách hàng được dùng "Tìm nhiếp ảnh gia"; Nhiếp ảnh gia / Quản trị viên thì ẩn (header cũng không có mục này)
        "display_avatar_url": avatar_url,
        "is_logged_in": logged_in,
        "display_name": name,
        "display_initial": name[:1].upper() if name else "",
        "unread_count": unread,
        "nav_items": build(menu),
        "account_items": build(ACCOUNT_MENUS.get(role, [])),
        "urls": {key: resolve(val) for key, val in URL_NAMES.items()},
        "site_name": "FRAMIE",
    }
