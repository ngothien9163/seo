# F2 — Pipeline keyword từ Search Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mục "Query mới phát hiện" trong báo cáo gộp trở thành đầu vào thật: query có impressions đủ ngưỡng mà chưa theo dõi → đề xuất, người dùng xác nhận → thêm vào danh sách từ khóa, và rank tracker check được từ khóa mới ở lần chạy kế tiếp.

**Architecture:** Nguồn sự thật của danh sách từ khóa chuyển từ `SEO_KEYWORDS` hardcode trong `config/settings.py` sang **`config/keywords.json`**, đi qua **một module duy nhất** `utils/keywords.py` (`load_keywords` / `save_keywords` / `add_keyword`). Mọi chỗ đọc (rank_tracker, gsc_client, tests, ui) gọi hàm — không còn ai tự đọc `cfg.SEO_KEYWORDS`. Bộ đề xuất `suggest_keywords()` là hàm thuần, tái dùng `_match_keywords()` + `_fold()` đã có trong `gsc_client` (đừng viết lại logic matching dấu). Điểm vào: CLI `--gsc-keywords` / `--gsc-add-keyword` và khung "Từ khóa đề xuất" trong tab 📈 Xếp Hạng.

**Tech Stack:** Python 3.11, stdlib (`json`, `os`). Không thêm dependency.

**Spec:** Không có spec riêng — bounded, thiết kế chốt trong chat (bảng "Quyết định" dưới đây), theo card F2 của `docs/superpowers/plans/2026-10-06-roadmap-10-tinh-nang.md:52-62`.

## Global Constraints

- `config/keywords.json` là file **được track trong git** (không thêm vào .gitignore) — nó thay thế đúng phần `SEO_KEYWORDS` cũ vốn đang commit trong settings.py.
- Định dạng file: `{"site": "<domain>", "keywords": ["...", ...]}` — có `site` để F10 (multi-site) đọc tiếp được mà không đổi schema.
- Mọi chỗ đọc từ khóa đi qua `utils.keywords.load_keywords()` — **cấm** thêm `cfg.SEO_KEYWORDS` mới ở đâu ra sau plan này.
- Ghi file: UTF-8, `ensure_ascii=False`, `indent=2`, ghi qua file tạm rồi thay thế (không để lại file cụt khi lỗi giữa chừng); file luôn parse lại được bằng `json.load` sau khi ghi.
- So trùng từ khóa dùng `_fold()` của `gsc_client` ("noi mi quan 2" == "nối mi quận 2") — không so chuỗi thô.
- `utils/keywords.py` không import Playwright; `gsc_client` import lười (trong hàm) để giữ module nhẹ.
- Thông điệp tiếng Việt, prefix `[Keyword]` cho CLI/GUI log.
- Không sửa mojibake cũ; code mới UTF-8 chuẩn.
- Test: script assert thuần `_quick_keyword_test.py` ở root (gitignored), chạy `python _quick_keyword_test.py`, KHÔNG pytest. Test bắt buộc trỏ `kw.KEYWORDS_FILE` sang `_test_keywords.json` — không được ghi đè `config/keywords.json` thật.
- Console Windows: khi chạy test qua pipe phải `PYTHONIOENCODING=utf-8` (mặc định cp1252, in tiếng Việt là crash — đây là lỗi harness, không phải lỗi code).
- Mỗi task kết thúc bằng một commit riêng.

## Review Focus

1. **Không còn chỗ đọc cũ** — sau Task 1, `grep SEO_KEYWORDS` chỉ còn xuất hiện trong `config/settings.py` (dòng comment trỏ file mới), README (bảng cấu hình), và docs. Mọi file `.py` khác phải sạch → test bằng grep trong Task 1.
2. **GUI sửa từ khóa phải có hiệu lực thật** — hành vi cũ: `start_thread` gán `cfg.SEO_KEYWORDS` trong bộ nhớ, đóng GUI là mất; sau Task 1 textarea phải `save_keywords()` để rank/GSC lần chạy sau đọc đúng list đang thấy → test Task 1 (AST) + verify tay.
3. **_fold phải dùng được khi chưa cài `requests`/`google-auth`** — `add_keyword` import `_fold` trong hàm; module `keywords` load được ở máy chưa setup GSC → test Task 1.
4. **Đề xuất không được gợi ý lại thứ đang theo dõi**, kể cả khi người dùng gõ khác dấu → test Task 2.
5. **File keywords không bao giờ thành JSON cụt/sai** kể cả khi truyền vào dữ liệu lạ (`None`, list có chuỗi rỗng, list không phải str) → test Task 1.
6. **Không có dữ liệu GSC** → `--gsc-keywords` in hướng dẫn chạy `--gsc`, không traceback → test Task 2/3.

## Quyết định đã chốt (mini design)

| Câu hỏi | Chốt | Lý do |
|---|---|---|
| `SEO_KEYWORDS` ở settings.py hay `config/keywords.json`? | **`config/keywords.json`** | Đúng khuyến nghị roadmap line 58; là "hedging rẻ" cho F10 — một site vẫn đọc tốt, thêm site chỉ thêm file. |
| Đọc qua đâu? | **`utils/keywords.py` — một hàm duy nhất** | Một điểm để F10 chuyển sang `data/<site>/keywords.json`; hết cảnh mỗi nơi một kiểu đọc. |
| Ngưỡng impressions mặc định? | **`KEYWORD_SUGGEST_MIN_IMPRESSIONS = 30`** trong settings.py | 28 ngày, query dưới 30 impressions quá nhiễu để thành bài viết; chủ động chỉnh được. |
| Bao nhiêu đề xuất mỗi lần? | **top 20 theo impressions** | Đủ chọn, không tràn màn hình CLI/GUI. |
| Trùng khi thêm? | **Từ chối + báo dòng đang có** (không âm thầm bỏ qua) | Người dùng cần biết vì sao bấm không ăn. |
| CLI có hỏi xác nhận không? | **Có**, `input("Thêm? [Y/n] ")`; bypass bằng `--yes` (dành cho script) | Roadmap yêu cầu "xác nhận trước khi ghi". |
| GUI thêm bằng cách nào? | Khung đề xuất trong tab Xếp Hạng, mỗi dòng có nút **+ Thêm** bấm là ghi | Không tự động thêm không hỏi (ngoài phạm vi card F2). |

---

### Task 1: `config/keywords.json` + `utils/keywords.py` + chuyển toàn bộ chỗ đọc

**Files:**
- Create: `utils/keywords.py`
- Create: `config/keywords.json` (sinh ra đúng 18 từ khóa đang có trong settings.py — không gõ tay, đọc `cfg.SEO_KEYWORDS` rồi ghi file)
- Create: `_quick_keyword_test.py` (gitignored)
- Modify: `config/settings.py` (xóa list `SEO_KEYWORDS`, để comment trỏ file mới)
- Modify: `utils/rank_tracker.py:209`, `utils/gsc_client.py:270`, `tests/test_search_flow.py:402-406`, `tests/test_direct_access.py:27`, `ui.py:221-222`, `ui.py:715`

**Interfaces (Produces — Task 2, 3, 4 dựa vào đây):**
- `KEYWORDS_FILE` — path `<root>/config/keywords.json` (biến module, test gán lại được).
- `load_keywords() -> list[str]` — file thiếu/sai → `[]` (không raise).
- `save_keywords(keywords: list, site: str = None) -> None` — lọc rỗng/lặp, giữ thứ tự, chấp nhận list phần tử không phải str (bỏ qua), ghi atomic.
- `add_keyword(kw: str) -> tuple[bool, str]` — (đã thêm chưa, thông điệp tiếng Việt); trùng theo `_fold` → `(False, "Từ khóa đã có trong danh sách ('...')")`.
- `site_domain() -> str` — domain của `cfg.TARGET_URL` (tái dùng logic normalize có sẵn, không tự viết parser mới).

- [x] **Step 1 — Test fail trước** (`_quick_keyword_test.py`, 12 assert):
  - `load_keywords()` khi file chưa tồn tại → `[]`.
  - `save_keywords(["a","b"," a ","", None, 3])` → file JSON parse được, `keywords == ["a","b"]` (fold-dedupe + bỏ phần tử không hợp lệ, giữ thứ tự).
  - `load_keywords()` đọc lại đúng list vừa ghi, tiếng Việt không bị escape thành `\uXXXX` (kiểm tra chuỗi "nối mi" nằm raw trong file).
  - File chứa JSON hỏng (`"{oops"`) → `load_keywords()` trả `[]`, không raise.
  - `add_keyword("nối mi quận 2")` khi list đã có "noi mi quan 2" → `(False, thông điệp có tên dòng đang có)`.
  - `add_keyword("  ")` → `(False, ...)`, `add_keyword("from scratch")` → `(True, ...)` và load lại thấy nó.
  - `add_keyword` khi file chưa tồn tại → tạo file mới valid.
  - Atomic: simulate lỗi giữa chừng (monkeypatch `os.replace` raise) → file cũ vẫn còn nội dung cũ.
  - Grep sạch chỗ đọc: không file `.py` nào khác `config/settings.py` còn chứa `SEO_KEYWORDS`.
  - AST `ui.py`: `start_thread` gọi `save_keywords`, `_setup_tab_general` gọi `load_keywords`, `export_csv_now` vẫn còn.
  - `import utils.keywords` không import playwright ở đầu file.
- [x] **Step 2 — Chạy → FAIL** (module chưa tồn tại).
- [x] **Step 3 — Sinh `config/keywords.json`** từ list cũ bằng script tạm (in ra để đối chiếu đúng 18 dòng, không mất từ khóa nào), rồi xóa list khỏi `settings.py`.
- [x] **Step 4 — Viết `utils/keywords.py`**, sửa 6 chỗ đọc/ghi.
- [x] **Step 5 — Chạy:** `_quick_keyword_test.py` ALL PASS + `_quick_gsc_test.py` + `_quick_export_test.py` + `_quick_test.py` vẫn PASS (không vỡ harness cũ) + `py_compile` mọi file sửa.
- [x] **Step 6 — Verify thật:** `PYTHONIOENCODING=utf-8 python main.py --rank-report` chạy được (đọc keywords qua hàm mới), `python -c "import ui; ui.TrafficBotUI()"` mở được GUI không lỗi.
- [x] **Step 7 — Commit:** `refactor: F2 keyword thi truong ve config/keywords.json + utils/keywords.py (1 diem doc duy nhat)`

### Task 2: Bộ đề xuất `suggest_keywords()` (hàm thuần, tái dùng `_match_keywords`)

**Files:**
- Modify: `utils/gsc_client.py` (thêm hàm, cuối module trước CLI section)
- Modify: `config/settings.py` (thêm `KEYWORD_SUGGEST_MIN_IMPRESSIONS = 30`)
- Modify: `_quick_keyword_test.py`

**Interfaces (Produces):**
- `suggest_keywords(rows: dict, tracked: list, min_impressions: int = None, limit: int = 20) -> list[dict]` — mỗi phần tử `{"query", "impressions", "clicks", "position", "ctr"}`, sắp impressions giảm dần. `min_impressions=None` → đọc `cfg.KEYWORD_SUGGEST_MIN_IMPRESSIONS`.
- `latest_gsc_rows() -> dict` — rows của snapshot mới nhất, `{}` khi chưa có.

- [x] **Step 1 — Test fail trước:**
  - Query khớp keyword đang theo dõi (kể cả khác dấu: "noi mi quan 2" vs "nối mi quận 2") → **không** xuất hiện trong đề xuất.
  - Query impressions < ngưỡng → bị loại; đúng ngưỡng (== 30) → được giữ (ranh giới inclusive).
  - Kết quả sắp theo impressions giảm dần; `limit=2` cắt còn 2.
  - `rows={}` hoặc tracked rỗng → không crash (`[]` với rows rỗng; mọi query khi tracked = [] nhưng vẫn phải qua ngưỡng impressions).
  - `latest_gsc_rows()` khi `gsc_history.json` chưa tồn tại → `{}`.
- [x] **Step 2 — Chạy → FAIL.**
- [x] **Step 3 — Implement** (`suggest_keywords` gọi `_match_keywords(rows, tracked)` rồi lọc `unmatched`; `latest_gsc_rows` đọc `_load_history()`), `py_compile`.
- [x] **Step 4 — Chạy test → ALL PASS.**
- [x] **Step 5 — Commit:** `feat: F2 bo de xuat tu khoa tu GSC (suggest_keywords, nguong impressions)`

### Task 3: CLI `--gsc-keywords` + `--gsc-add-keyword`

**Files:**
- Modify: `utils/gsc_client.py` (2 hàm CLI), `main.py` (2 nhánh), `README.md`
- Modify: `_quick_keyword_test.py`

- [ ] **Step 1 — Test fail trước:** `run_add_keyword_cli("  ")` → không ghi file, trả exit code != 0; `--gsc-keywords` khi chưa có snapshot → in "python main.py --gsc" chứ không raise; `main.py` có chứa `'"--gsc-keywords"'` và `'"--gsc-add-keyword"'`.
- [ ] **Step 2 — Chạy → FAIL.**
- [ ] **Step 3 — Implement:** `run_keyword_suggest_cli(limit)` in bảng xếp hạng đề xuất (query | impressions | clicks | vị trí TB | CTR) kèm dòng hướng dẫn `python main.py --gsc-add-keyword "..."`; `run_add_keyword_cli(kw, assume_yes=False)` → in thông báo, hỏi `[Y/n]` (EOF/không phải y → hủy, không ghi), gọi `add_keyword`, in kết quả + tổng số từ khóa sau khi thêm.
- [ ] **Step 4 — Verify thật:** `PYTHONIOENCODING=utf-8 python main.py --gsc-keywords` (máy chưa có GSC data → phải in hướng dẫn, exit 0); `python main.py --gsc-add-keyword "test tu khoa tam" --yes` rồi `--rank-report` thấy nó, rồi xóa bằng cách ghi lại list cũ (khôi phục `config/keywords.json` đúng nguyên trạng — verify bằng `git diff` sạch).
- [ ] **Step 5 — Commit:** `feat: F2 cli --gsc-keywords va --gsc-add-keyword (xac nhan truoc khi ghi)`

### Task 4: Khung "Từ khóa đề xuất" trong tab 📈 Xếp Hạng

**Files:**
- Modify: `ui.py` (`_setup_tab_rank` + 2 method mới)
- Modify: `README.md`

- [ ] **Step 1 — Test fail trước (AST):** `ui.py` có method `refresh_keyword_suggestions` và `add_suggested_keyword`, cả hai không có Name chưa resolve (pattern `test_ui_gsc_methods_no_unresolved_names`).
- [ ] **Step 2 — Chạy → FAIL.**
- [ ] **Step 3 — Implement:** nút "💡 TỪ KHÓA ĐỀ XUẤT" đặt cạnh các nút đang có trong hàng nút; khung `CTkScrollableFrame` liệt kê tối đa 20 dòng `[query]  123 hiện  —  [+ Thêm]`; bấm + → `add_keyword()` → log `[Keyword] ✅ Đã thêm ...`, dòng đó đổi nhãn nút thành "✅ Đang theo dõi" và disable; list rỗng → ghi chú "Chưa có dữ liệu Search Console — bấm nút Lấy dữ liệu trước."
- [ ] **Step 4 — Verify:** launch GUI bằng script (instantiate `TrafficBotUI`, gọi `refresh_keyword_suggestions()`, `add_suggested_keyword("...")`, screenshot nếu cửa sổ hiện được). Nếu môi trường không cho phép mở cửa sổ, nói rõ chưa verify GUI.
- [ ] **Step 5 — Commit:** `feat: F2 khung de xuat tu khoa + nut them vao theo doi trong tab Xep Hang`

## Tiêu chí hoàn thành (của card F2)

- Query có dấu/không dấu vẫn nhận ra là trùng.
- Keyword đang theo dõi không bị đề xuất lại.
- Thêm xong, rank tracker check được từ khóa mới ở lần chạy sau.
- File `config/keywords.json` luôn valid JSON sau khi ghi (kể cả khi lỗi giữa chừng).

## Known limitations (ghi nhận, không sửa trong plan này)

- Đề xuất chỉ đến từ GSC snapshot mới nhất; chưa có nguồn volume/difficulty ngoài (Ahrefs/SEMrush) — ngoài phạm vi card F2.
- `content/keyword_research.py` vẫn là dữ liệu mẫu bịa (volume/difficulty) và nói về topdev.vn — không thuộc F2, sẽ xử lý ở F8 (content generation) hoặc một card riêng.
- Chưa có nút xóa từ khóa khỏi GUI (textarea tab Cài Đặt Chung là chỗ sửa tay).
