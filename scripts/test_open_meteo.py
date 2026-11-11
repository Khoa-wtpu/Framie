"""E6 - Kiểm thử Open-Meteo (dự báo theo GIỜ, 16 ngày, 5 khu vực).
Chỉ dùng thư viện chuẩn (urllib). Chạy: python test_open_meteo.py
Chạy trên máy cá nhân VÀ trên máy chủ triển khai (D8), dán bảng in ra vào báo cáo E6.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 3  # giây
HOURLY = ["temperature_2m", "precipitation_probability", "weather_code"]
LOCATIONS = [
    ("TP. Hồ Chí Minh", 10.8231, 106.6297),
    ("Hà Nội", 21.0285, 105.8542),
    ("Đà Nẵng", 16.0544, 108.2022),
    ("Đà Lạt", 11.9404, 108.4583),
    ("Nha Trang", 12.2388, 109.1967),
]


def call(lat, lon, tz, days=16):
    qs = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "hourly": ",".join(HOURLY),
        "forecast_days": days,
        "timezone": tz,
    })
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(f"{BASE}?{qs}", timeout=TIMEOUT) as r:
            body = json.loads(r.read().decode("utf-8"))
            status = r.status
    except urllib.error.HTTPError as e:
        try:
            reason = json.loads(e.read().decode("utf-8")).get("reason", "")
        except Exception:
            reason = ""
        return {"ok": False, "status": e.code, "error": f"HTTP {e.code} {reason}".strip(),
                "sec": time.perf_counter() - t0}
    except Exception as e:  # timeout, DNS, SSL...
        return {"ok": False, "status": None, "error": f"{type(e).__name__}: {e}",
                "sec": time.perf_counter() - t0}
    return {"ok": status == 200, "status": status, "data": body, "sec": time.perf_counter() - t0}


def summarize(res):
    """Trả về (số phần tử mỗi biến, số null mỗi biến, giờ đầu, giờ cuối)."""
    h = res["data"]["hourly"]
    counts = {k: len(h[k]) for k in HOURLY}
    nulls = {k: sum(v is None for v in h[k]) for k in HOURLY}
    return len(h["time"]), counts, nulls, h["time"][0], h["time"][-1]


def main():
    # 1) Thử timezone Asia/Ho_Chi_Minh (E1) trước, nếu lỗi thử Asia/Bangkok (E6)
    tz_used = None
    print("== Kiểm tra timezone (Đà Nẵng) ==")
    for tz in ("Asia/Ho_Chi_Minh", "Asia/Bangkok"):
        r = call(16.0544, 108.2022, tz)
        print(f"{tz}: {'OK' if r['ok'] else 'LỖI - ' + r['error']} ({r['sec']:.2f}s)")
        if r["ok"] and tz_used is None:
            tz_used = tz
    if tz_used is None:
        print("Không gọi được API với cả hai timezone -> xem lỗi ở trên (mạng/DNS/timeout/429).")
        return
    print(f"-> Dùng timezone: {tz_used}\n")

    # 2) 5 toạ độ, mỗi nơi 1 lần
    print(f"== 5 khu vực, hourly={','.join(HOURLY)}, forecast_days=16, timeout={TIMEOUT}s ==")
    print("| Khu vực | Toạ độ | OK/lỗi | Thời gian (giây) | Số phần tử | Null |")
    print("|---|---|---|---|---|---|")
    for name, lat, lon in LOCATIONS:
        r = call(lat, lon, tz_used)
        coord = f"{lat}, {lon}"
        if not r["ok"]:
            print(f"| {name} | {coord} | LỖI: {r['error']} | {r['sec']:.2f} | - | - |")
            continue
        n, counts, nulls, first, last = summarize(r)
        total_null = sum(nulls.values())
        null_txt = "không có" if total_null == 0 else ", ".join(f"{k}: {v}" for k, v in nulls.items() if v)
        flag = "" if n == 384 and all(c == 384 for c in counts.values()) else " (khác 384!)"
        print(f"| {name} | {coord} | OK | {r['sec']:.2f} | {n}{flag} | {null_txt} |")
        print(f"|  |  |  |  | {first} -> {last} |  |")


if __name__ == "__main__":
    main()
