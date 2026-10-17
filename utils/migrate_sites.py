"""
utils/migrate_sites.py — F10 Task 3: dựng nhà per-site cho dữ liệu flat hiện có (NON-destructive).

Vì sao non-destructive: đây là dữ liệu THẬT của owner. Script chỉ COPY, KHÔNG BAO GIỜ xóa/move
bản gốc. Chủ đích tự xóa flat-file sau khi xác nhận GUI/CLI đọc đúng từ folder per-site.

    plan(target_url=None) -> list[Row]   # (src, dst, trạng thái) — không ghi gì
    migrate(dry_run=False)  -> dict       # {copied, same, conflict, rows}

Cơ chế bật per-site: `site_paths.is_multi_site()` đọc dấu `data/<slug>/.migrated`, do
`migrate()` ghi ở BƯỚC CUỐI. Migrate dựng `data/<slug>/` + `config/<slug>/` rồi copy file,
và chỉ đóng dấu khi xong → crash giữa chừng thì lần chạy sau vẫn đọc flat-file gốc
(dữ liệu thật), không đọc một nửa folder mới. Còn `conflict` thì KHÔNG đóng dấu: đích
đang có bản khác nội dung nghĩa là chưa ai xác nhận, bật per-site lúc đó là đổi nguồn
sự thật sau lưng owner.

Idempotent theo SHA256: src==dst → bỏ qua ('same'); dst tồn tại nhưng khác nội dung → 'conflict',
KHÔNG đè (tránh phá dữ liệu owner đã chỉnh ở đích). Mỗi bản copy đi qua file tạm + os.replace
nên dst chỉ có hai trạng thái: chưa có, hoặc đã đủ nội dung — không bao giờ cụt (file cụt sẽ
bị lần chạy sau xếp vào 'conflict' và chặn migration vĩnh viễn).

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


def _atomic_copy(src: str, dst: str) -> None:
    """Copy qua file tạm cùng thư mục rồi os.replace — đích không bao giờ ở trạng thái cụt.

    Copy thẳng vào dst mà đứt giữa chừng thì để lại file thiếu nội dung; lần migrate
    sau so SHA sẽ thấy 'conflict' và TỪ CHỐI chạy tiếp — migration kẹt vĩnh viễn.
    """
    tmp = f"{dst}.tmp-{os.getpid()}"
    try:
        shutil.copy2(src, tmp)      # giữ mtime
        os.replace(tmp, dst)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


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
    # Dựng nhà per-site trước (chưa bật per-site — cờ nằm ở dấu .migrated bên dưới)
    os.makedirs(os.path.join(sp.DATA_ROOT, slug), exist_ok=True)
    os.makedirs(os.path.join(sp.CONFIG_ROOT, slug), exist_ok=True)

    for r in rows:
        if r["state"] == "copied":
            os.makedirs(os.path.dirname(r["dst"]), exist_ok=True)
            _atomic_copy(r["src"], r["dst"])  # src VẪN CÒN (non-destructive)

    # Đóng dấu HOÀN TẤT — chỉ khi không còn conflict. Có conflict nghĩa là đích đang
    # giữ bản khác nội dung mà ta cố tình không đè: dữ liệu per-site CHƯA đủ, phải giữ
    # flat-file gốc làm nguồn sự thật.
    if not stats["conflict"]:
        sp.mark_migrated(slug)
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
    verb = "sẽ copy" if dry_run else "đã copy"
    print(f"[Migrate] {verb}={stats['copied']}  đã giống={stats['same']}  "
          f"conflict={stats['conflict']}  (không đụng flat-file gốc — owner tự xóa sau khi xác nhận)")
    if stats["conflict"]:
        print("[Migrate] Có file trùng tên nhưng khác nội dung ở đích — KHÔNG ghi đè. "
              "Kiểm tra thủ công rồi chạy lại.")
        print("[Migrate] Chưa đóng dấu hoàn tất → site vẫn đọc flat-file gốc, "
              "không đọc folder per-site còn thiếu file.")
        return 2
    if dry_run:
        print("[Migrate] DRY-RUN — chưa ghi gì, chưa đóng dấu hoàn tất.")
        return 0
    print(f"[Migrate] ✅ Đã đóng dấu hoàn tất data/{slug}/{sp.MIGRATED_MARKER} "
          "→ site này chuyển sang per-site.")
    return 0

