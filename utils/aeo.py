"""
utils/aeo.py — AEO tracking (F9): đo "AI trả lời có nhắc brand mình không?"

Hướng đã chốt trong roadmap (2026-10-06, phần F9): phương án (a) hỏi AI bằng
Playwright profile anti-detect bị LOẠI — rơi đúng lớp né phát hiện bot tuyên bố
không động từ đầu. Chỉ (c) paste tay câu trả lời (bản này) hoặc (b) API có key
(owner tự cung cấp) — phần (b) chỉ thêm khi owner chốt engine + key.

Vòng làm việc theo ngày:
    python main.py --aeo-check answer.txt --aeo-engine ChatGPT --aeo-keyword "nối mi"
    python main.py --aeo-report

answer.txt: nội dung câu trả lời AI người dùng tự hỏi (ChatGPT/Gemini/Perplexity/…)
rồi dán vào file. Công cụ CHỈ phân tích text đã có — không request ra ngoài.

Phân tích thuần: các biến thể brand (config AEO_BRANDS) được FOLD dấu tiếng Việt
(tái dùng _fold của gsc_client — một bản duy nhất trong repo) rồi khớp theo
TOKEN trọn vẹn: "nankybeautyva" không được tính là "nanky beauty"… trừ khi chủ
cửa hàng viết đúng từ. Kết quả: có nhắc / số nhắc / vị trí (word-index).

Lưu `aeo_history.json` per-site qua site_paths (chưa migrate → flat ở gốc
project, hành vi y hệt F10). Mỗi (date, engine, keyword) giữ MỘT bản ghi — dán
lại trong ngày thì thay thế, đúng rate limit "1 lần/ngày/từ khóa/engine" đã
chốt trong roadmap. Giới hạn tổng số bản ghi (AEO_HISTORY_KEEP) — cũ nhất bị cắt.
"""
import json
import os
from datetime import datetime

import config.settings as cfg
from utils import gsc_client
from utils import site_paths
from utils.gsc_client import _fold  # noqa: F401 — tái dùng chiến lược fold, không copy

__all__ = ["analyze_answer", "add_result", "load_history", "ai_matrix",
           "build_report", "run_aeo_check_cli", "run_aeo_report_cli"]

_AEO_NAME = "aeo_history.json"
_DEFAULT_AEO_PATH = site_paths.site_file(_AEO_NAME)
# Slot override cho test/CLI (test gán HISTORY_FILE); code đọc qua _history_path().
HISTORY_FILE = _DEFAULT_AEO_PATH

def _history_path() -> str:
    """Đường dẫn aeo history lúc gọi. Test gán HISTORY_FILE → tôn trọng; không → resolve per-site."""
    if HISTORY_FILE != _DEFAULT_AEO_PATH:
        return HISTORY_FILE
    return site_paths.site_file(_AEO_NAME)

# ─── PHÂN TÍCH THUẦN: câu trả lời có nhắc brand không ───────────────────────

def _tokens(text: str) -> list[str]:
    """Token fold-dấu bằng ký tự chữ/số: chữ & số tạo token, CÒN LẠI là ranh giới.

    Nếu chỉ split theo khoảng trắng, dấu câu dính vào token ('beauty.', 'đẹp,')
    và match token-trọn-vẹn mất nhắc cuối câu; tách theo category là đủ cho cả
    'Nanky Beauty.' lẫn 'nankybeauty.com' → ['nankybeauty', 'com'].
    """
    import re as _re
    folded = _fold(text or "")
    return [t for t in _re.split(r"[^0-9a-z]+", folded) if t]

def analyze_answer(answer: str, brands: list[str] | None = None) -> dict:
    """
    Input: text câu trả lời AI (paste tay) + danh sách biến thể brand.
    Output: {mentioned, mentions, positions} — positions là token-index các lần nhắc.

    Khớp TOKEN trọn vẹn sau fold dấu: 'nankybeauty.com' → ['nankybeauty', 'com'],
    nên brand 'nankybeauty.com' được: token chấm-phẩy/khoảng trắng đều là ranh giới.
    'nankybeautyva' vẫn là MỘT token riêng — không tính là 'nankybeauty' (char-substring
    match sẽ đếm sai biếtn음 gần đúng thành nhắc thật). Cùng vị trí bị biến thể brand
    trung lặp → đếm MỘT (gộp set vị trí).
    """
    brands = list(brands if brands is not None else getattr(cfg, "AEO_BRANDS", []))
    tokens = _tokens(answer)
    hits: set[int] = set()
    for brand in brands:
        sub = _tokens(str(brand or ""))
        if not sub or len(sub) > len(tokens):
            continue
        for i in range(len(tokens) - len(sub) + 1):
            if tokens[i:i + len(sub)] == sub:
                hits.add(i)  # 1 nhắc = 1 vị trí đối TRƯỚC; token thêu không gộp dupicate
    sorted_hits = sorted(hits)
    return {"mentioned": bool(sorted_hits), "mentions": len(sorted_hits), "positions": sorted_hits}

# ─── LỊCH SỬ: đọc / ghi ─────────────────────────────────────────────────────

def _load_history() -> dict:
    path = _history_path()
    if not os.path.exists(path):
        return {"records": []}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("history không phải dict")
    except (ValueError, OSError):
        # history hỏng → coi như rỗng thay vì chết cả lệnh; lần ghi kế sẽ thay file cũ
        return {"records": []}
    data.setdefault("records", [])
    if not isinstance(data["records"], list):
        data["records"] = []
    return data

def load_history() -> dict:
    """Bản ghi AEO đã lưu [{date, engine, keyword, mentioned, mentions, positions, added_at}]."""
    return _load_history()

def _save_history(data: dict) -> None:
    """Ghi atomic (tmp + os.replace) — crash giữa chừng không cụt file cũ."""
    path = _history_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass

def _prune(records: list, keep: int | None = None) -> list:
    """Cắt hết nếu vượt keep, giữ bản ghi MỚI NHẤT (cuối danh sách chèn).

    Records được append theo thứ tự thời gian chèn — kể cả các bản ghi có cùng date
    hay added_at (thêm trong cùng giây), thứ tự chèn vẫn là TRẬT TỰ đáng tin; sort
    theo (date, added_at) khi các key trùng gây mất ổn định thứ tựーチ gốc.
    """
    keep = keep if keep is not None else getattr(cfg, "AEO_HISTORY_KEEP", 500)
    if len(records) <= keep:
        return records
    return records[-keep:]

def add_result(answer: str, brands: list[str] | None = None, engine: str = "ChatGPT",
               keyword: str = "", date: str | None = None) -> dict:
    """
    Phân tích 1 câu trả lời rồi lưu. Cùng (date, engine, keyword) → thay bản ghi cũ
    (1 lần/ngày/từ khóa/engine — chủ nhân dán lại trong ngày là cập nhật, không spam).
    Trả bản ghi vừa lưu.
    """
    date = date or datetime.now().strftime("%Y-%m-%d")
    verdict = analyze_answer(answer, brands=brands)
    record = {
        "date": date,
        "engine": (engine or "AI").strip() or "AI",
        "keyword": (keyword or "").strip(),
        "mentioned": verdict["mentioned"],
        "mentions": verdict["mentions"],
        "positions": verdict["positions"],
        "chars": len(answer or ""),
        "added_at": datetime.now().isoformat(timespec="seconds"),
    }
    data = _load_history()
    records = [r for r in data["records"]
               if not (r.get("date") == record["date"] and r.get("engine") == record["engine"]
                       and r.get("keyword") == record["keyword"])]
    records.append(record)
    data["records"] = _prune(records)
    _save_history(data)
    return record

# ─── BÁO CÁO ────────────────────────────────────────────────────────────────

def ai_matrix() -> dict[str, dict[str, dict]]:
    """
    {keyword: {engine: {mentioned, mentions, date}}} — bản ghi MỚI NHẤT mỗi cặp.
    Rỗng khi chưa có dữ liệu AEO (báo cáo gộp sẽ bỏ cột AI — không breaking).
    """
    last: dict[tuple, dict] = {}  # (kw, engine) -> record
    for r in _load_history()["records"]:
        key = (r.get("keyword", ""), r.get("engine", ""))
        if key not in last or r.get("date", "") > last[key].get("date", ""):
            last[key] = r
    matrix: dict[str, dict] = {}
    for (kw, engine), r in last.items():
        matrix.setdefault(kw, {})[engine] = {
            "mentioned": r.get("mentioned", False),
            "mentions": r.get("mentions", 0),
            "date": r.get("date", ""),
        }
    return matrix

def build_report() -> str:
    """Báo cáo console per từ khóa × engine: ✓ nhắc / ✗ không nhắc + ngày đo."""
    domain = site_paths.site_domain() or "(chưa cấu hình TARGET_URL)"
    matrix = ai_matrix()
    lines = [
        "=" * 72,
        f"  BÁO CÁO AEO — AI CÓ NHẮC TỚI {domain}?  (cách dán: python main.py --aeo-check)",
        "=" * 72,
    ]
    if not matrix:
        lines.append("  Chưa có dữ liệu AEO. Mỗi ngày: hỏi 1 AI engine 1 câu theo từng từ khóa")
        lines.append("  → copy câu trả lời vào file → chạy:")
        lines.append('    python main.py --aeo-check answer.txt --aeo-engine ChatGPT --aeo-keyword "từ khóa"')
        lines.append("  Các engine thäch dán tay (không gửi request nào): ChatGPT / Gemini /")
        lines.append("  Perplexity / Copilot / … — engine nào cũng được, đặt tên rõ.")
        return "\n".join(lines)

    engines = sorted({e for per_kw in matrix.values() for e in per_kw})
    lines.append(f"  {'Từ khóa':<40}{'Engine':<14}{'Nhắc':<10}{'Ngày'}")
    lines.append("-" * 72)
    for kw in sorted(matrix):
        for engine in engines:
            info = matrix[kw].get(engine)
            if info is None:
                lines.append(f"  {kw[:40]:<40}{engine[:13]:<14}{'—':<10}{'—'}")
                continue
            mark = "✓" if info["mentioned"] else "✗"
            n = f"{info['mentions']} lần" if info["mentions"] > 1 else "có"
            lines.append(f"  {kw[:40]:<40}{engine[:13]:<14}{mark + ' ' + n:<10}"
                         f"{info.get('date', '')}")
    lines.append("-" * 72)
    return "\n".join(lines)

# ─── CLI ────────────────────────────────────────────────────────────────────

def run_aeo_report_cli() -> int:
    print(build_report())
    return 0

def run_aeo_check_cli(path: str, engine: str = "", keyword: str = "") -> int:
    """Đọc file câu trả lời (paste tay) → lưu kết quả phân tích. Không có request ra ngoài."""
    path = (path or "").strip().strip('"')
    keyword = (keyword or "").strip()
    if not keyword:
        print("[AEO] Thiếu từ khóa — thêm --aeo-keyword \"<từ khóa đang theo dõi>\".")
        return 2
    if not path:
        print('[AEO] Thiếu file câu trả lời — python main.py --aeo-check <answer.txt> '
              '--aeo-keyword "<kw>" [--aeo-engine ChatGPT]')
        return 2
    if not os.path.isfile(path):
        print(f"[AEO] Không tìm thấy file: {path}")
        return 2
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            answer = f.read()
    except OSError as e:
        print(f"[AEO] Không đọc được file {path}: {e}")
        return 2
    if not answer.strip():
        print(f"[AEO] File rỗng: {path}")
        return 2
    brands = getattr(cfg, "AEO_BRANDS", [])
    record = add_result(answer, brands=brands, engine=engine or "ChatGPT", keyword=keyword)
    engine = record["engine"]
    if record["mentioned"]:
        print(f"[AEO] ✓ {engine} nhắc brand trong \"{record['keyword']}\" "
              f"({record['mentions']} vị trí, ngày {record['date']}) — đã lưu {_history_path()}")
    else:
        print(f"[AEO] ✗ {engine} KHÔNG nhắc trong \"{record['keyword']}\" "
              f"(ngày {record['date']}) — đã lưu {_history_path()}")
    return 0
