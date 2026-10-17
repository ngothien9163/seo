"""
utils/exporter.py — F1: xuất dữ liệu SEO đã thu ra CSV mở bằng Excel.

Đọc (không sửa) bốn file state:
- rank_history.json  → một dòng mỗi (lần check × từ khóa), toàn bộ lịch sử
- gsc_history.json   → các query của snapshot GSC mới nhất
- audit_last.json    → các finding của lần `--audit` gần nhất
- backlink_status.json → kết quả `--backlink-check` gần nhất (link chết/nofollow đầu bảng)

File ghi vào `reports/export_<YYYYMMDD>_<HHMMSS>_<kind>.csv` (multi-site thì thêm tiền
tố slug: `<slug>_export_...`), mã UTF-8 có BOM (Excel bản tiếng Việt cần BOM để không
lỗi dấu), mỗi lần export một file mới. Tên file được GIÀNH bằng `os.open(O_EXCL)` nên
hai process export cùng một giây (GUI + CLI) không bao giờ ghi đè nhau.

Chạy:
    python main.py --export rank       # chỉ xếp hạng
    python main.py --export gsc        # chỉ Search Console
    python main.py --export audit      # kết quả --audit lần gần nhất (data/audit_last.json)
    python main.py --export backlinks  # kết quả --backlink-check (data/backlink_status.json)
    python main.py --export all        # rank + gsc (audit/backlinks không đi kèm: phải chạy trước)
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


def _clean(v) -> str:
    """None/rỗng → '' (Excel hiểu là ô trống); mọi thứ khác → str."""
    if v is None:
        return ""
    return str(v)


def _as_dict(v) -> dict:
    """v là dict thì lấy, ngược lại {} — file state là JSON người sửa được, schema có thể lệch."""
    return v if isinstance(v, dict) else {}


def _fnum(v, default: float = 0.0) -> float:
    """Số thực từ ô có thể bẩn (None, 'abc', '14,3') — không parse được thì trả default.

    Một ô hỏng trong history không được làm nổ cả lần export (owner mất luôn phần còn lại).
    """
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# ─── SERIALIZE: rank history ────────────────────────────────────────────────

def rank_rows() -> tuple[list[str], list[list[str]]]:
    """Toàn bộ lịch sử xếp hạng → (header, rows). Không có history → rows = []."""
    from utils.rank_tracker import _load_history  # import lười (kéo playwright nếu ở đầu file)

    checks = _as_dict(_as_dict(_load_history()).get("checks"))
    rows: list[list[str]] = []
    for checked_at in sorted(checks.keys(), key=str):
        stamp = str(checked_at)[:19].replace("T", " ")
        results = _as_dict(checks[checked_at])
        for kw in sorted(results.keys(), key=str):
            r = _as_dict(results[kw])
            rows.append([stamp, _clean(kw), _clean(r.get("pos")), _clean(r.get("url"))])
    return list(RANK_HEADER), rows


# ─── SERIALIZE: GSC snapshot ────────────────────────────────────────────────

def gsc_rows() -> tuple[list[str], list[list[str]]]:
    """Các query của snapshot Search Console mới nhất → (header, rows).

    CTR xuất dạng đã ×100 làm tròn 2 số, KHÔNG kèm ký hiệu % trong ô số — để Excel
    còn tính toán được (định dạng % làm ở đầu Excel).
    """
    from utils.gsc_client import _load_history  # import lười (đọc file key chỉ lúc cần)

    snaps = _as_dict(_as_dict(_load_history()).get("snapshots"))
    if not snaps:
        return list(GSC_HEADER), []

    snap = _as_dict(snaps[sorted(snaps.keys(), key=str)[-1]])
    rows = _as_dict(snap.get("rows"))
    span = f"{snap.get('start_date') or '?'} → {snap.get('end_date') or '?'}"
    fetched = _clean(snap.get("fetched_at"))

    def _sort_key(q: str):
        return (-_fnum(_as_dict(rows[q]).get("impressions")), q)

    out = []
    for q in sorted(rows.keys(), key=_sort_key):
        r = _as_dict(rows[q])
        out.append([
            _clean(q),
            _clean(r.get("clicks")),
            _clean(r.get("impressions")),
            f"{_fnum(r.get('position')):.1f}",
            f"{_fnum(r.get('ctr')) * 100:.2f}",
            span,
            fetched,
        ])
    return list(GSC_HEADER), out


# ─── GHI FILE ────────────────────────────────────────────────────────────────

def _unique_path(kind: str) -> str:
    """reports/[<slug>_]export_<ngày>_<giờ>_<kind>[_N].csv — tên trả về đã được GIÀNH.

    Tên được tạo bằng `os.open(O_CREAT|O_EXCL)`: hai process export trong cùng một
    giây (GUI + CLI, hai cửa sổ) thì process thứ hai ăn FileExistsError và tự nhảy
    sang `_2`. Kiểu "kiểm tra os.path.exists rồi mới ghi" không chống được vì cả hai
    đều thấy "chưa có" trước khi ai kịp tạo file.

    File trả về đã tồn tại (0 byte); `_write_csv` mở lại bằng "w" nên ghi đè bình
    thường. Vì tên bị giành ngay lúc gọi, các hàm export_* phải tính rows TRƯỚC —
    nếu không, một lỗi khi đọc history sẽ để lại file CSV rỗng trong reports/.
    """
    from utils import site_paths  # import trong hàm: giữ exporter không phụ heavyweight ở top level
    stamp = f"{datetime.now():%Y%m%d_%H%M%S}"
    base = f"{site_paths.report_prefix()}export_{stamp}_{kind}"
    os.makedirs(REPORTS_DIR, exist_ok=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_BINARY"):  # Windows: không để '\n' trong tên file bị đổi thành '\r\n'
        flags |= os.O_BINARY
    n = 1
    while True:
        path = os.path.join(REPORTS_DIR, f"{base}.csv" if n == 1 else f"{base}_{n}.csv")
        try:
            fd = os.open(path, flags)
        except FileExistsError:
            if n >= 999:  # 999 lần trong một giây = có gì đó sai, không quay vô hạn
                raise RuntimeError(f"không giành được tên file mới trong {REPORTS_DIR}")
            n += 1
            continue
        os.close(fd)
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
    header, rows = rank_rows()   # tính trước khi giành tên (xem _unique_path)
    path = _unique_path("rank")
    return path, _write_csv(path, header, rows)


def export_gsc() -> tuple[str, int]:
    header, rows = gsc_rows()
    path = _unique_path("gsc")
    return path, _write_csv(path, header, rows)


# ─── SERIALIZE + EXPORT: kết quả audit on-page (F6) ─────────────────────────

def audit_rows() -> tuple[list[str], list[list[str]]]:
    """Findings của lần audit gần nhất → (header, rows).

    Việc sắp xếp/map finding sang dòng nằm trong site_auditor.audit_rows — exporter
    chỉ lo BOM + tên file, không tái định nghĩa thứ tự severity ở hai nơi.
    """
    from utils.site_auditor import audit_rows as _map, load_last_audit
    return _map(load_last_audit())


def export_audit() -> tuple[str, int]:
    header, rows = audit_rows()
    path = _unique_path("audit")
    return path, _write_csv(path, header, rows)


# ─── SERIALIZE + EXPORT: kết quả check backlink (F7) ─────────────────────────

def backlink_rows() -> tuple[list[str], list[list[str]]]:
    """Kết quả `--backlink-check` gần nhất → (header, rows), link có vấn đề trước.

    Header và thứ tự cột thuộc về backlink_checker (nơi sinh ra row) — exporter chỉ
    ghi BOM + tên file, giống hệt cách audit_rows ủy quyền mapping cho site_auditor.
    """
    from utils.backlink_checker import state_rows
    from utils.backlinks import load_state
    return state_rows(load_state())


def export_backlinks() -> tuple[str, int]:
    header, rows = backlink_rows()
    path = _unique_path("backlinks")
    return path, _write_csv(path, header, rows)


def export_all() -> list[tuple[str, int]]:
    """Cả hai loại — mỗi loại một file CSV (kể cả khi một loại trống).

    `all` chỉ rank + gsc vì đó là dữ liệu định kỳ scheduler tự lấy. Audit và
    backlink là thứ owner chủ động chạy (--audit / --backlink-check), bắt nó đi kèm
    nghĩa là export một đống số liệu của lần chạy cũ nhất không ai biết từ bao giờ.
    """
    return [export_rank(), export_gsc()]


# ─── CLI ─────────────────────────────────────────────────────────────────────

KINDS = ("rank", "gsc", "audit", "backlinks", "all")

_LABELS = {"rank": "xếp hạng", "gsc": "Search Console",
           "audit": "kết quả audit on-page", "backlinks": "kết quả check backlink"}
# Lệnh lấy dữ liệu tương ứng — in ra khi file chỉ có tiêu đề
_SOURCES = {"rank": "--rank", "gsc": "--gsc", "audit": "--audit",
            "backlinks": "--backlink-check"}

_EXPORTERS = {"rank": export_rank, "gsc": export_gsc, "audit": export_audit,
              "backlinks": export_backlinks}


def run_export_cli(kind: str = "all") -> int:
    """Entry `--export`: xuất CSV theo loại, in đường dẫn từng file. Trả exit code."""
    kind = (kind or "all").strip().lower()
    if kind not in KINDS:
        print(f"[Export] ⚠️ Loại không hiểu: '{kind}' — hợp lệ: {' | '.join(KINDS)}")
        return 2

    selected = [("rank", export_rank), ("gsc", export_gsc)] if kind == "all" else \
               [(kind, _EXPORTERS[kind])]

    for label, fn in selected:
        path, n = fn()
        print(f"[Export] ✅ Đã lưu {path} ({n} dòng {_LABELS[label]})")
        if n == 0:
            print(f"[Export]    Chưa có dữ liệu {_LABELS[label]} — file chỉ có tiêu đề."
                  f" Lấy dữ liệu: python main.py {_SOURCES[label]}")
    return 0
