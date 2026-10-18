# -*- coding: utf-8 -*-
"""utils/rank_urls.py — P3-1: --rank-urls — trang nào đang xếp hạng cho kw nào.

Đọc lại top_urls mà rank tracker đã lưu từ phiên có tính năng (0 request mạng mới):
- "Trang đang rank": history lưu url cho từng kw + vị trí trang đó trong top 10.
- "Đổi trang rank": kw đổi URL giữa 2 entry gần nhất → dấu hiệu Google chưa
  quyết trang "chính" (cannibalization / nội dung chồng nhau). Chỉ ghi chú,
  không tự sửa gì.
- "Đa trang trên SERP": một lần check có > 1 trang cùng site trong top 10.

Các mốc lịch sử không có top_urls (lần check cũ) bị bỏ qua lặng lẽ —
giống mọi consumer khác, không migrate.
"""
from utils.rank_tracker import _load_history, _norm_domain
from urllib.parse import urlsplit


def _own_domain(url: str) -> str:
    """URL → netloc thường (www-fold). Không parse được → ''."""
    netloc = (urlsplit(str(url or "")).netloc or "").lower()
    return _norm_domain(netloc)


def _path_of(url: str) -> str:
    """URL gọn để hiển thị: path + 12 ký tự query đầu nếu có."""
    p = urlsplit(str(url or ""))
    out = (p.path or "/").rstrip("/")
    if p.query:
        out += "?" + p.query[:12] + ("…" if len(p.query) > 12 else "")
    return out or "/"


def build_url_map(history: dict) -> dict:
    """{kw: {"entries": [{stamp, url, pos, idx}]}} — idx = vị trí của url rank
    trong top_urls (0-based; None nếu top_urls không chứa trang đó).

    Entry chỉ được đếm khi CẢ `url` và `top_urls` có sẵn (kw có rank + mốc mới)."""
    checks = history.get("checks") or {}
    out = {}
    for stamp in sorted(checks.keys()):
        for kw, rec in (checks[stamp] or {}).items():
            rec = rec or {}
            top = rec.get("top_urls") or []
            url = rec.get("url") or ""
            if not top or not url:
                continue
            idx = next((i for i, u in enumerate(top)
                        if _own_domain(u) == _own_domain(url)), None)
            out.setdefault(kw, [] ).append(
                {"stamp": stamp, "url": url, "pos": rec.get("pos"), "idx": idx})
    return out


def find_moved(url_map: dict) -> list:
    """kw đổi trang rank giữa 2 entry có top_urls gần nhất. ["kwTrước"→"bây giờ"]"""
    moved = []
    for kw, entries in url_map.items():
        if len(entries) < 2:
            continue
        prev, last = entries[-2], entries[-1]
        if last["url"] != prev["url"]:
            moved.append({"keyword": kw, "prev_url": prev["url"], "prev_pos": prev["pos"],
                          "last_url": last["url"], "last_pos": last["pos"]})
    return moved


def serp_pages(kw_rec: dict) -> list:
    """[url] các trang cùng site trong top_urls của 1 entry (đa trang trên SERP)."""
    dom = _own_domain(kw_rec.get("url") or "")
    if not dom:
        # kw không rank — coi trang rank là không có, không suy domain từ top_urls
        return []
    return [u for u in (kw_rec.get("top_urls") or []) if _own_domain(u) == dom]


def build_report_text() -> tuple[str, int]:
    """(text, số kw có dữ liệu). Trả text gợi ý khi chưa có mốc nào có top_urls."""
    history = _load_history()
    url_map = build_url_map(history)
    if not url_map:
        return ("  Chưa có mốc check nào lưu top_urls — chạy `python main.py --rank`;"
                "\n  từ lần check sau khi có tính năng này, top 10 URL được lưu cùng hạn."
                "\n  Lịch sử cũ không được migrate (dữ liệu thô không có gì để đoán)."), 0

    lines = [f"  TRANG ĐANG RANK THEO TỪ KHÓA ({len(url_map)} kw có dữ liệu URL)",
             "  " + "-" * 68,
             f"  {'Từ khóa':<34}{'Hạng':>5}  Trang (path)"]
    for kw, entries in sorted(url_map.items()):
        cur = entries[-1]
        lines.append(f'  {kw[:34]:<34}{str(cur["pos"] or "-"):>5}  {_path_of(cur["url"])}')
        top = ((history.get("checks") or {}).get(cur["stamp"]) or {}).get(kw)
        pages = serp_pages({"url": cur["url"], "top_urls": (top or {}).get("top_urls") or []})
        if len(pages) > 1:
            extra = [_path_of(u) for u in pages if u != cur["url"]][:3]
            lines.append(f'  {"":>40}+ đa trang SERP: {"; ".join(extra)}')
    lines.append("  " + "-" * 68)

    moved = find_moved(url_map)
    if moved:
        lines.append(f"  ⚠️ ĐỔI TRANG RANK ({len(moved)} kw — giữa 2 lần check gần nhất):")
        for m in moved:
            lines.append(f'  • "{m["keyword"]}": {_path_of(m["prev_url"])} '
                         f'(hạng {m["prev_pos"] if m["prev_pos"] else "-"})'
                         f' → {_path_of(m["last_url"])} '
                         f'(hạng {m["last_pos"] if m["last_pos"] else "-"})')
        lines.append("  Đổi trang = Google chưa chốt trang 'chính' cho kw — xem --internal-links")
        lines.append("  hoặc hợp nhất nội dung hai trang (301 cũng đi được nếu nội dung trùng).")
    return "\n".join(lines), len(url_map)


def run_rank_urls_cli() -> int:
    """`--rank-urls`: bảng kw → trang đang rank + cảnh báo đổi trang."""
    import config.settings as cfg

    text, n = build_report_text()
    print("=" * 76)
    print(f"  RANK THEO URL — {cfg.TARGET_URL or '(chưa cấu hình site)'}")
    print("=" * 76)
    print(text)
    print("=" * 76)
    return 0
