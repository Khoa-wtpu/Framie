from django.conf import settings

from .navigation import (ACCOUNT_MENUS, GUEST, MENUS, PREVIEW_KEYS, URL_NAMES,
                         count_unread, get_role, is_active, resolve)


def layout(request):
    user = request.user
    role = get_role(user)
    preview = False
    forced = PREVIEW_KEYS.get(request.GET.get("xem_voi_vai_tro")) if settings.DEBUG else None
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

    return {
        "role": role,
        "is_logged_in": logged_in,
        "display_name": name,
        "display_initial": name[:1].upper() if name else "",
        "unread_count": unread,
        "nav_items": build(MENUS[role]),
        "account_items": build(ACCOUNT_MENUS.get(role, [])),
        "urls": {key: resolve(val) for key, val in URL_NAMES.items()},
        "site_name": "FRAMIE",
    }
