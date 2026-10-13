"""
utils/exporter.py — F1: xuất dữ liệu SEO đã thu ra CSV mở bằng Excel.

Đọc (không sửa) hai file state:
- rank_history.json  → một dòng mỗi (lần check × từ khóa), toàn bộ lịch sử
- gsc_history.json   → các query của snapshot GSC mới nhất

File ghi vào `reports/export_<YYYYMMDD>_<HHMMSS>_<rank|gsc>.csv`, mã UTF-8 có BOM
(Excel bản tiếng Việt cần BOM để không lỗi dấu), mỗi lần export một file mới.

Chạy:
    python main.py --export rank      # chỉ xếp hạng
    python main.py --export gsc       # chỉ Search Console
    python main.py --export all       # cả hai (mặc định)
    GUI: tab "📈 Xếp Hạng" → nút "📤 XUẤT CSV"

Ghi chú:
- Thuần stdlib (`csv`, `os`, `datetime`) — không Playwright, không pandas.
- rank_tracker / gsc_client import bên trong hàm: module phải load được cả khi
  chưa cài playwright, chưa setup credentials, và để test trỏ được đường dẫn history.
"""
import csv
import os
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(ROOT, "reports")

RANK_HEADER = ["Thời gian check", "Từ khóa", "Vị trí", "URL"]
GSC_HEADER = ["Query", "Clicks", "Impressions", "Vị trí TB", "CTR %", "Khoảng ngày", "Fetch lúc"]

# Đường dẫn đã cấp trong phiên này — chặn hai lần export cùng giây ghi đè nhau
# (os.path.exists thôi không đủ vì file chưa được ghi ngay lúc cấp tên)
_ISSUED: set = set()


def _clean(v) -> str:
    """None/rỗng → '' (Excel hiểu là ô trống); mọi thứ khác → str."""
    if v is None:
        return ""
    return str(v)


# ─── SERIALIZE: rank history ────────────────────────────────────────────────

def rank_rows() -> tuple[list[str], list[list[str]]]:
    """Toàn bộ lịch sử xếp hạng → (header, rows). Không có history → rows = []."""
    from utils.rank_tracker import _load_history  # import lười (kéo playwright nếu ở đầu file)

    checks = _load_history().get("checks", {}) or {}
    rows: list[list[str]] = []
    for checked_at in sorted(checks.keys()):
        stamp = str(checked_at).replace("T", " ")
        results = checks[checked_at] or {}
        for kw in sorted(results.keys()):
            r = results[kw] or {}
            rows.append([stamp, kw, _clean(r.get("pos")), _clean(r.get("url"))])
    return list(RANK_HEADER), rows


# ─── SERIALIZE: GSC snapshot ────────────────────────────────────────────────

def gsc_rows() -> tuple[list[str], list[list[str]]]:
    """Các query của snapshot Search Console mới nhất → (header, rows).

    CTR xuất dạng đã ×100 làm tròn 2 số, KHÔNG kèm ký hiệu % trong ô số — để Excel
    còn tính toán được (định dạng % làm ở đầu Excel).
    """
    from utils.gsc_client import _load_history  # import lười (đọc file key chỉ lúc cần)

    snaps = _load_history().get("snapshots", {}) or {}
    if not snaps:
        return list(GSC_HEADER), []

    snap = snaps[sorted(snaps.keys())[-1]]
    rows = snap.get("rows", {}) or {}
    span = f"{snap.get('start_date', '?')} → {snap.get('end_date', '?')}"
    fetched = _clean(snap.get("fetched_at"))

    def _sort_key(q: str):
        return (-(rows[q].get("impressions") or 0), q)

    out = []
    for q in sorted(rows.keys(), key=_sort_key):
        r = rows[q] or {}
        out.append([
            q,
            _clean(r.get("clicks")),
            _clean(r.get("impressions")),
            f"{float(r.get('position') or 0):.1f}",
            f"{float(r.get('ctr') or 0) * 100:.2f}",
            span,
            fetched,
        ])
    return list(GSC_HEADER), out


# ─── GHI FILE ────────────────────────────────────────────────────────────────

def _unique_path(kind: str) -> str:
    """reports/export_<ngày>_<giờ>_<kind>[._N].csv — không bao giờ trả tên đã dùng."""
    base = f"export_{datetime.now():%Y%m%d_%H%M%S}_{kind}"
    path = os.path.join(REPORTS_DIR, f"{base}.csv")
    n = 1
    while path in _ISSUED or os.path.exists(path):
        n += 1
        path = os.path.join(REPORTS_DIR, f"{base}_{n}.csv")
    _ISSUED.add(path)
    return path


def _write_csv(path: str, header: list[str], rows: list[list]) -> int:
    """Tạo thư mục nếu cần, ghi BOM + header + rows. Trả về số dòng dữ liệu."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return len(rows)


# ─── EXPORT ─────────────────────────────────────────────────────────────────

def export_rank() -> tuple[str, int]:
    path = _unique_path("rank")
    header, rows = rank_rows()
    return path, _write_csv(path, header, rows)


def export_gsc() -> tuple[str, int]:
    path = _unique_path("gsc")
    header, rows = gsc_rows()
    return path, _write_csv(path, header, rows)


def export_all() -> list[tuple[str, int]]:
    """Cả hai loại — mỗi loại một file CSV (kể cả khi một loại trống)."""
    return [export_rank(), export_gsc()]


# ─── CLI ─────────────────────────────────────────────────────────────────────

KINDS = ("rank", "gsc", "all")

_LABELS = {"rank": "xếp hạng", "gsc": "Search Console"}


def run_export_cli(kind: str = "all") -> int:
    """Entry `--export`: xuất CSV theo loại, in đường dẫn từng file. Trả exit code."""
    kind = (kind or "all").strip().lower()
    if kind not in KINDS:
        print(f"[Export] ⚠️ Loại không hiểu: '{kind}' — hợp lệ: rank | gsc | all")
        return 2

    selected = [("rank", export_rank), ("gsc", export_gsc)] if kind == "all" else \
               [("gsc", export_gsc)] if kind == "gsc" else \
               [("rank", export_rank)]

    for label, fn in selected:
        path, n = fn()
        print(f"[Export] ✅ Đã lưu {path} ({n} dòng {_LABELS[label]})")
        if n == 0:
            cmd = "--rank" if label == "rank" else "--gsc"
            print(f"[Export]    Chưa có dữ liệu {_LABELS[label]} — file chỉ có tiêu đề."
                  f" Lấy dữ liệu: python main.py {cmd}")
    return 0
