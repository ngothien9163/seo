"""
utils/migrate_sites.py — F10 Task 3: dựng nhà per-site cho dữ liệu flat hiện có (NON-destructive).

Vì sao non-destructive: đây là dữ liệu THẬT của owner. Script chỉ COPY, KHÔNG BAO GIỜ xóa/move
bản gốc. Chủ đích tự xóa flat-file sau khi xác nhận GUI/CLI đọc đúng từ folder per-site.

    plan(target_url=None) -> list[Row]   # (src, dst, trạng thái) — không ghi gì
    migrate(dry_run=False)  -> dict       # {copied, same, conflict, rows}

Cơ chế bật per-site: `site_paths.is_multi_site()` dựa trên sự tồn tại của `data/<slug>/`.
Migrate tạo `data/<slug>/` + `config/<slug>/` và copy file vào → lần chạy sau module tự rẽ per-site.

Idempotent theo SHA256: src==dst → bỏ qua ('same'); dst tồn tại nhưng khác nội dung → 'conflict',
KHÔNG đè (tránh phá dữ liệu owner đã chỉnh ở đích).

Chỉ stdlib. Đọc cfg lúc gọi (hỗ trợ `--site` trước khi migrate).
"""
import hashlib
import os
import shutil

import config.settings as cfg
from utils import site_paths as sp

# (tên file, loại) — loại: 'root' = flat ở gốc project (rank/gsc/session legacy),
#                     'config' = config/<name>, 'data' = data/<name>
MANIFEST = [
    ("rank_history.json", "root"),
    ("gsc_history.json", "root"),
    ("session_state.json", "root"),
    ("keywords.json", "config"),
    ("backlinks.json", "config"),
    ("backlink_status.json", "data"),
    ("alerts_state.json", "data"),
    ("scheduler_state.json", "data"),
    ("audit_last.json", "data"),
    ("pagespeed.json", "data"),
]


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _flat_src(name: str, kind: str) -> str:
    if kind == "root":
        return os.path.join(sp.FLAT_ROOT, name)
    if kind == "config":
        return os.path.join(sp.CONFIG_ROOT, name)
    return os.path.join(sp.DATA_ROOT, name)


def _per_site_dst(name: str, kind: str) -> str:
    slug = sp.site_slug()
    if kind == "config":
        return os.path.join(sp.CONFIG_ROOT, slug, name)
    return os.path.join(sp.DATA_ROOT, slug, name)  # 'root' và 'data' đều đổ vào data/<slug>/


def _classify(src: str, dst: str) -> str:
    """ copied | same | conflict | absent — theo hiện trạng 2 file (không ghi)."""
    if not os.path.exists(src):
        return "absent"
    if not os.path.exists(dst):
        return "copied"
    try:
        return "same" if _sha256(src) == _sha256(dst) else "conflict"
    except OSError:
        return "conflict"


def plan(target_url: str = None) -> list:
    """Danh sách (src, dst, state, name) mà migrate SẼ làm — dry-run/preview, không ghi."""
    if target_url is not None:
        cfg.TARGET_URL = target_url
    rows = []
    for name, kind in MANIFEST:
        src = _flat_src(name, kind)
        dst = _per_site_dst(name, kind)
        rows.append({"name": name, "src": src, "dst": dst, "state": _classify(src, dst)})
    return rows


def migrate(dry_run: bool = False) -> dict:
    """Copy flat-file sang per-site. Không bao giờ xóa src. Trả {copied, same, conflict, absent, rows}."""
    rows = plan()
    stats = {"copied": 0, "same": 0, "conflict": 0, "absent": 0, "rows": rows}
    for r in rows:
        stats[r["state"]] += 1
    if dry_run:
        return stats  # 'copied' khi dry-run = "SẼ copy", không ghi gì

    slug = sp.site_slug()
    if not slug:
        raise ValueError("TARGET_URL rỗng — không suy được slug site; khai cfg.TARGET_URL trước khi migrate")
    # Tạo nhà per-site (bật is_multi_site) kể cả khi chưa có file nào để copy
    os.makedirs(os.path.join(sp.DATA_ROOT, slug), exist_ok=True)
    os.makedirs(os.path.join(sp.CONFIG_ROOT, slug), exist_ok=True)

    for r in rows:
        if r["state"] == "copied":
            os.makedirs(os.path.dirname(r["dst"]), exist_ok=True)
            shutil.copy2(r["src"], r["dst"])  # giữ mtime; src VẪN CÒN (non-destructive)
    return stats


_ICON = {"copied": "COPY", "same": "bỏ qua (đã giống)", "conflict": "CONFLICT (không đè)", "absent": "—"}


def run_migrate_cli(dry_run: bool = False) -> int:
    """Entry `--migrate-multi-site`: in bảng kế hoạch + chạy. Trả exit code (0 ok, 2 conflict/lỗi)."""
    slug = sp.site_slug()
    if not slug:
        print("[Migrate] TARGET_URL rỗng — khai cfg.TARGET_URL (hoặc --site) trước khi migrate.")
        return 2
    mode = "DRY-RUN (không ghi)" if dry_run else "MIGRATE"
    print(f"[Migrate] {mode} — site='{slug}'  →  data/{slug}/ + config/{slug}/")
    try:
        stats = migrate(dry_run=dry_run)
    except Exception as e:  # not raise cho CLI
        print(f"[Migrate] Lỗi: {e}")
        return 2
    for r in stats["rows"]:
        if r["state"] == "absent":
            continue
        print(f"  {_ICON[r['state']]:<24} {r['name']}")
    print(f"[Migrate] sẽ copy={stats['copied']}  đã giống={stats['same']}  "
          f"conflict={stats['conflict']}  (không đụng flat-file gốc — owner tự xóa sau khi xác nhận)")
    if stats["conflict"]:
        print("[Migrate] Có file trùng tên nhưng khác nội dung ở đích — KHÔNG ghi đè. "
              "Kiểm tra thủ công rồi chạy lại.")
        return 2
    return 0

