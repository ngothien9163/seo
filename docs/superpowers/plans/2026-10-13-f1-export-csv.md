# F1 — Export báo cáo CSV Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Toàn bộ dữ liệu đã thu (rank history + GSC snapshot) xuất ra file CSV mở được bằng Excel tiếng Việt (UTF-8 BOM), qua CLI `--export rank|gsc|all` và nút Export trong tab "📈 Xếp Hạng".

**Architecture:** Một module mới `utils/exporter.py` thuần stdlib (`csv`, `os`, `datetime`), chỉ **đọc** state qua `_load_history()` của `rank_tracker` và `gsc_client` — không ghi vào file state nào, không import Playwright. Hai hàm serialize thuần (`rank_rows`, `gsc_rows`) tách khỏi một hàm ghi file duy nhất (`_write_csv`) để test được logic mà không đụng đĩa. File xuất ra `reports/export_<YYYYMMDD>_<HHMMSS>_<loai>.csv`.

**Tech Stack:** Python 3.11, module `csv` stdlib. **Không thêm dependency** (không pandas — YAGNI theo roadmap line 46).

**Spec:** Không có spec riêng — tính năng bounded, thiết kế chốt trực tiếp trong chat (xem "Quyết định" bên dưới), theo card F1 của `docs/superpowers/plans/2026-10-06-roadmap-10-tinh-nang.md:42-50`.

## Global Constraints

- Không sửa `rank_tracker.py` / `gsc_client.py` — chỉ import hàm đọc có sẵn của chúng.
- Không import Playwright/browser ở bất kỳ đâu trong `utils/exporter.py`.
- CSV ghi bằng `encoding="utf-8-sig"` (BOM — bắt buộc để Excel bản tiếng Việt đọc đúng dấu) và `newline=""` theo khuyến cáo của module `csv`.
- Tên file: `reports/export_<ngày>_<giờ>_<rank|gsc>.csv`; mỗi lần export tạo file mới, **không bao giờ ghi đè** file đã tồn tại (trùng tên trong cùng giây → thêm hậu tố `_2`, `_3`).
- History rỗng → file vẫn được ghi, chỉ có dòng header, exit code 0, in thông báo nhắc chưa có dữ liệu.
- Thông điệp tiếng Việt, prefix log `[Export]`.
- Không sửa mojibake có sẵn ở file cũ; code mới viết UTF-8 chuẩn.
- Test theo pattern repo: script assert thuần `_quick_export_test.py` ở root (gitignored), chạy `python _quick_export_test.py` — **không dùng pytest**. Test không được đụng `rank_history.json` / `gsc_history.json` thật (pattern: gán lại `HISTORY_FILE` / `DATA_FILE` sang file `_test_*.json`).
- `reports/` là thư mục sinh ra dữ liệu → thêm vào `.gitignore`.
- Mỗi task kết thúc bằng một commit riêng.

## Review Focus

1. History rỗng dưới mọi dạng (file không tồn tại / file có nhưng `checks` = `{}` / snapshot có nhưng `rows` = `{}`) → chỉ header, không crash, không `ZeroDivisionError`. Test Task 1 + 2.
2. BOM thật sự nằm ở đầu file — kiểm bằng byte (`f.read(3) == b"\xef\xbb\xbf"`), không kiểm bằng string decode (decode utf-8-sig sẽ ẩn BOM và test luôn pass giả). Test Task 1.
3. Giá trị `None` (từ khóa không vào top, chưa có URL) → ô trống, **không phải** chuỗi `"None"` và không phải `0` (0 sẽ bị Excel/BI hiểu là hạng nhất). Test Task 1.
4. Tên file trùng lặp (export 2 lần trong cùng giây) → không mất dữ liệu lần đầu. Test Task 1.
5. Module load được khi chưa có `google-auth` / chưa setup GSC — `import utils.exporter` không được raise. Test Task 2.

## Quyết định đã chốt (mini design)

| Câu hỏi | Chốt | Lý do |
|---|---|---|
| Một file gộp hay mỗi loại một file? | **Mỗi loại một file** (`--export all` = 2 file) | CSV không có khái niệm sheet; gộp thì 2 loại có schema khác nhau phải chèn cột rỗng vô nghĩa. |
| Header tiếng Việt hay Anh? | **Tiếng Việt** | Người dùng mở Excel đọc trực tiếp, toàn bộ UI đang tiếng Việt. |
| Rank: export snapshot mới nhất hay toàn lịch sử? | **Toàn lịch sử** (mỗi lần check × mỗi từ khóa một dòng) | Giá trị của file nằm ở chuỗi thời gian để vẽ pivot; snapshot mới nhất đã có báo cáo trên màn hình. |
| GSC: snapshot nào? | **Snapshot mới nhất** (cùng logic `build_report`) | Khớp đúng thứ owner đang nhìn thấy; snapshot cũ vẫn còn trong JSON. |
| BOM | **utf-8-sig** | Yêu cầu của roadmap: mở Excel tiếng Việt không lỗi font. |

---

### Task 1: Lõi `utils/exporter.py` — đường dẫn, ghi CSV có BOM, export rank

**Files:**
- Create: `utils/exporter.py`
- Create: `_quick_export_test.py` (gitignored)
- Modify: `.gitignore` (thêm `reports/`)

**Interfaces (Produces — Task 2 + 3 dựa vào đây):**
- `REPORTS_DIR` — đường dẫn tuyệt đối `<root>/reports` (biến module, test gán lại được).
- `rank_rows() -> tuple[list[str], list[list[str]]]` — trả `(header, rows)` từ toàn bộ `rank_history.json`; không đọc file nếu chưa có gì.
- `gsc_rows() -> tuple[list[str], list[list[str]]]` — tương tự cho snapshot GSC mới nhất.
- `_unique_path(kind: str) -> str` — `reports/export_<YYYYMMDD>_<HHMMSS>_<kind>.csv`, tự thêm `_2`, `_3`… nếu trùng.
- `_write_csv(path: str, header: list[str], rows: list[list]) -> int` — tạo thư mục, ghi BOM, trả số dòng dữ liệu đã ghi.
- `export_rank() -> tuple[str, int]`, `export_gsc() -> tuple[str, int]` — serialize + ghi, trả `(đường dẫn, số dòng)`.
- `export_all() -> list[tuple[str, int]]`

- [x] **Step 1 — Test fail trước:** `_quick_export_test.py` (pattern `check(name, fn)` của `_quick_gsc_test.py`), trỏ `rt.HISTORY_FILE` sang `_test_rank_history.json`, `ex.REPORTS_DIR` sang `_test_reports/`, kết thúc xóa sạch:
  - `rank_rows()` với history `{checkA: {"kw1": {"pos": 5, "url": "u"}}, checkB: {"kw1": {"pos": 3}}}` → header 4 cột, 2 dòng, dòng đầu `["<checkA>", "kw1", "5", "u"]`, dòng hai ô URL **rỗng**.
  - History rỗng (`{"checks": {}}`) → `rank_rows()` = `(header, [])`; file không tồn tại → cũng `(header, [])`.
  - `pos` là `None` → ô rỗng, không phải `"None"`.
  - `_write_csv` → byte đầu file là `b"\xef\xbb\xbf"`; dòng đầu decode = header; số dòng = `1 + len(rows)`.
  - `export_rank()` trên history rỗng → file tồn tại, 1 dòng (chỉ header), trả `(path, 0)`.
  - `_unique_path("rank")` gọi 2 lần khi file thứ nhất đã ghi → 2 đường dẫn khác nhau, không ghi đè.
- [x] **Step 2 — Chạy:** `python _quick_export_test.py` → FAIL (`ModuleNotFoundError: utils.exporter`).
- [x] **Step 3 — Viết `utils/exporter.py`** (docstring + constants + `rank_rows` + `_unique_path` + `_write_csv` + `export_rank`; `gsc_rows`/`export_gsc` để Task 2).
- [x] **Step 4 — Chạy test → ALL PASS**, cộng `python -m py_compile utils/exporter.py`.
- [x] **Step 5 — Commit:** `feat: F1 export CSV — loi exporter + rank history (BOM, khong ghi de)`

### Task 2: GSC snapshot → CSV, `export_all`, export không phụ thuộc `google-auth`

**Files:**
- Modify: `utils/exporter.py`
- Modify: `_quick_export_test.py`

**Interfaces (Produces):** `gsc_rows()`, `export_gsc()`, `export_all()` (đã khai ở Task 1, hoàn thiện tại đây).

- [x] **Step 1 — Test fail trước:**
  - Trỏ `gsc.DATA_FILE` sang `_test_gsc_history.json`; snapshot 1 ngày với 2 rows → `gsc_rows()` trả đúng số dòng, mỗi dòng `[query, clicks, impressions, position, ctr%, start_date→end_date, fetched_at]`; `ctr` 0.0245 → `"2.45"` (đã ×100, làm tròn 2 số, **không** có dấu `%` trong ô số để Excel còn tính được).
  - `gsc_history.json` không tồn tại → `(header, [])`, `export_gsc()` vẫn ghi file header-only.
  - Snapshot có `rows: {}` → `(header, [])`.
  - `export_all()` với cả 2 history rỗng → 2 tuple, 2 file tồn tại, không exception.
  - Import module: `python -c "import utils.exporter"` chạy được trong môi trường chưa setup credentials (không đọc file key ở import time).
- [x] **Step 2 — Chạy → FAIL.**
- [x] **Step 3 — Implement** `gsc_rows` / `export_gsc` / `export_all`; đọc GSC qua `gsc_client._load_history()` import **trong hàm** (giữ module không phụ thuộc thứ tự import).
- [x] **Step 4 — Chạy test → ALL PASS.**
- [x] **Step 5 — Commit:** `feat: F1 export CSV — GSC snapshot + export all`

### Task 3: Wire CLI `--export` + nút GUI + tài liệu

**Files:**
- Modify: `main.py` (nhánh `elif "--export"` trước các nhánh khác, hỗ trợ `--export rank|gsc|all`; cập nhật khối help `show_strategy()`)
- Modify: `ui.py` (`_setup_tab_rank`: nút `📤 XUẤT CSV`; hàm `export_csv_now()`; `_quick_gsc_test.py` AST check không bị vỡ)
- Modify: `README.md` (mục tính năng + bảng CLI)

**Interfaces (Consumes):** `utils.exporter.export_rank/export_gsc/export_all`.

- [x] **Step 1 — Test fail trước:** thêm vào `_quick_export_test.py` một assert dùng AST (tái dùng pattern `test_ui_gsc_methods_no_unresolved_names`): hàm `export_csv_now` trong `ui.py` phải tồn tại và **không có Name chưa resolve**; `main.py` phải chứa nhánh `--export`.
- [x] **Step 2 — Chạy → FAIL.**
- [x] **Step 3 — Implement CLI:** `--export` thiếu loại → mặc định `all`; loại không hợp lệ → in danh sách hợp lệ, không traceback; in `[Export] ✅ Đã lưu <path> (<n> dòng)`.
- [x] **Step 4 — Implement GUI:** nút gọi `export_all()` (sync, nhanh, không cần thread), in đường dẫn ra console; không đổi state `is_running`.
- [x] **Step 5 — Chạy kiểm chứng thật:** `python main.py --export all` trên máy chưa có history → 2 file header-only trong `reports/`, exit 0. `python -m py_compile main.py ui.py`. `python _quick_gsc_test.py` vẫn ALL PASS (không vỡ test GSC cũ).
- [x] **Step 6 — README:** thêm `python main.py --export rank|gsc|all` vào bảng CLI + mô tả F1.
- [x] **Step 7 — Commit:** `feat: F1 nut Export CSV trong tab Xep Hang + cli --export, docs README`

## Tiêu chí hoàn thành ( của card F1 )

- File mở Excel không lỗi font tiếng Việt (BOM đã kiểm bằng byte).
- History rỗng → file chỉ có header, không crash.
- Mỗi lần export ghi file mới, không ghi đè file cũ cùng ngày.

## Known limitations (ghi nhận, không sửa trong plan này)

- **`_save_history` của rank_tracker (và gsc_client) từng ghi trực tiếp `open(path,"w")`** → process chết giữa lúc `json.dump` để lại file cụt/không parse được, `_load_history` `except` trả `{}` → **mất sạch lịch sử xếp hạng/GSC** không tái tạo được. **✅ ĐÃ SỬA (2026-10-14, audit code-health theo owner):** cả 2 chuyển sang idiom **atomic tmp + `os.replace`** (giống scheduler/alerts/backlinks/keywords/generator đã dùng sẵn). Test `_quick_atomic_history_test.py` 4/4 (crash giữa ghi → file gốc còn nguyên + load lại được; happy-path vẫn ghi; không sót `.tmp`); mutation `_mut_atomic_hist` 2/2 KILLED (cho `tmp = path` → reproduce mất dữ liệu).

- `--export gsc` chỉ lấy snapshot mới nhất; muốn chuỗi snapshot theo ngày cần thêm loại `gsc-history` (chưa có nhu cầu thực tế → YAGNI).
- Module không xuất `session_state.json` (dữ liệu traffic bot) — roadmap F1 chỉ định danh rank + GSC.
- GUI nút Export in đường dẫn ra console, không mở hộp thoại "Save As" — customtkinter không có file dialog sẵn; owner muốn chọn nơi lưu thì mở `reports/` trong Explorer.
- **`_ISSUED` trong `exporter._unique_path` (F1) là set chống trùng đường dẫn cùng phiên** — bản cũ giữ mọi path từng cấp → một phiên GUI dài chạy export nhiều sẽ leak. **✅ ĐÃ SỬA (2026-10-15, audit code-health):** giữ **đúng path của giây hiện tại** (stamp nằm trong tên file nên giây khác không thể trùng) → đổi giây là `clear()`. Hành vi chặn đè cùng giây giữ nguyên. Test `_quick_bugfix_test.py` (5/5: 2 path cùng giây vẫn khác nhau; sang giây mới set còn 1); mutation `_mut_bugfix` KILLED (`if stamp != _ISSUED_STAMP` → `if False` → reproduces phình set).
