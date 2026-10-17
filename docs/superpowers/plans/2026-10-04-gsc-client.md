# GSC Client (Google Search Console API) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lấy dữ liệu SEO thật (clicks/impressions/position/CTR) từ Google Search Console API bằng service account, lưu snapshot JSON và in báo cáo gộp với Rank Tracker — không scrape, không CAPTCHA.

**Architecture:** Một module mới `utils/gsc_client.py` (đồng bộ, thuần HTTP qua `requests` + `google-auth`) song song với `utils/rank_tracker.py`; báo cáo gộp tái dùng sparkline/delta của rank tracker (đổi tên public). Điểm vào: CLI `--gsc`/`--gsc-report` và nút trong tab "📈 Xếp Hạng" của `ui.py`. Dữ liệu lưu `gsc_history.json` (90 ngày), rate limit riêng.

**Tech Stack:** Python 3.11, `google-auth` (mới thêm), `requests` (có sẵn), JSON file persistence. Không Playwright/browser.

**Spec:** `docs/superpowers/specs/2026-10-04-gsc-client-design.md` (đọc kèm — plan này lập luận từ spec).

## Global Constraints

- Chỉ thêm dependency `google-auth` vào `requirements.txt`; `requests` đã có.
- `gsc_client.py` KHÔNG import Playwright/browser_manager — thuần HTTP.
- Mọi file ghi JSON: `open(..., encoding="utf-8")`, `json.dump(..., ensure_ascii=False, indent=1)`.
- Dữ liệu GSC: `dimensions=["query"]`, `rowLimit=250`, `dataState="all"`, scope `https://www.googleapis.com/auth/webmasters.readonly`, timeout 30s.
- Thông điệp người dùng tiếng Việt, prefix log `[GSC]`. Không in nội dung file key/token ra console.
- Không sửa lỗi mojibake có sẵn trong các file cũ; các block code mới viết UTF-8 chuẩn.
- Test theo pattern hiện có của repo: script assert thuần `_quick_gsc_test.py` ở root (gitignored), chạy `python _quick_gsc_test.py` — KHÔNG dùng pytest.
- Backup đích: mỗi task kết thúc bằng commit riêng.

## Review Focus

Các đầu vào spec ngầm hiểu nhưng không task test nào phủ — mỗi dòng có test gắn vào task sở hữu:

1. Query GSC lệch dấu/dấu tiếng Việt so với keyword cấu hình (`"noi mi quan 2"` vs `"nối mi quận 2"`) — matching phải fold Unicode (NFD bỏ dấu combining) trước khi so, nếu không lệch dấu là coi như không khớp → test trong Task 3.
2. Row GSC thiếu key (`clicks`/`position` vắng mặt hoặc `null`) — `parse_api_response` phải mặc định 0 / 0.0, không KeyError → test trong Task 1.
3. `rank_history.json` không tồn tại trong khi GSC có dữ liệu — báo cáo gộp hiển thị "—" ở cột SERP, không crash → test trong Task 3.
4. Property GSC mới verify, API trả 0 rows — `save_snapshot` + báo cáo phải empty state thân thiện → test trong Task 1 + Task 3.
5. Rate limit qua ranh giới ngày (state `date` khác hôm nay) — phải reset count về 0 → test trong Task 1.

---

### Task 1: Lõi `gsc_client.py` — credentials, fetch, parse, lưu snapshot, rate limit

**Files:**
- Create: `utils/gsc_client.py`
- Create: `_quick_gsc_test.py` (gitignored)
- Modify: `config/settings.py` (cuối file, sau block RANK_KEYWORD_DELAY_MAX)
- Modify: `requirements.txt` (thêm dòng)
- Modify: `.gitignore` (đổi dòng `_quick_test.py` thành `_quick_*.py` — phủ cả file test cũ)

**Interfaces (Produces — Task 3, 4, 5 dựa vào đây):**
- `class GSCSetupError(Exception)` — thiếu/lỗi credentials.
- `DATA_FILE` — đường dẫn tuyệt đối tới `gsc_history.json` (root project, cùng pattern `rank_tracker.HISTORY_FILE`).
- `parse_api_response(payload: dict) -> dict[str, dict]` — payload JSON của API → `{query: {"clicks": int, "impressions": int, "position": float, "ctr": float}}`.
- `load_credentials()` → google credentials object; raise `GSCSetupError` khi thiếu file.
- `fetch_search_analytics(days: int = None) -> dict[str, dict]` — đồng bộ; raise `GSCSetupError` / `requests.HTTPError`.
- `save_snapshot(rows: dict, start_date: str, end_date: str) -> None`
- `can_run_fetch() -> tuple[bool, str]`, `mark_fetch_run() -> None`
- `_load_history() -> dict`, `_save_history(data: dict) -> None`
- `GSC_API_BASE = "https://searchconsole.googleapis.com/webmasters/v3/sites"`, `SCOPE`, `MAX_SNAPSHOTS_KEPT = 90`

- [ ] **Step 1: Viết test fail trước** — `_quick_gsc_test.py` với các assert (import `utils.gsc_client as gsc`, không gọi network):
  - `gsc.parse_api_response({"rows": [{"keys": ["nối mi quận 2"], "clicks": 3, "impressions": 154, "position": 18.7, "ctr": 0.019}]})` → `{"nối mi quận 2": {"clicks": 3, "impressions": 154, "position": 18.7, "ctr": 0.019}}`.
  - Row thiếu key: `{"keys": ["x"]}` → `{"x": {"clicks": 0, "impressions": 0, "position": 0.0, "ctr": 0.0}}`; row `"position": None` → 0.0.
  - Payload `{"rows": []}` và `{}` → `{}`.
  - Snapshot: ghi `gsc.DATA_FILE` tạm (trỏ `gsc.DATA_FILE` sang `_test_gsc_history.json` như `_quick_test.py` đã làm với rank) 2 snapshot ngày khác nhau + 1 snapshot cũ 100 ngày → `save_snapshot` lần nữa → file còn ≤ 90 snapshot, ngày mới nhất đúng; fetch lại cùng ngày ghi đè không nhân đôi.
  - Rate limit: state `date` khác hôm nay → `can_run_fetch()` = `(True, "")`; đếm vượt `cfg.GSC_MAX_FETCH_PER_DAY` → `(False, <thông điệp có số>)`.
  - `load_credentials()` khi file không tồn tại → raise `GSCSetupError`, message chứa "SETUP_GSC".
- [ ] **Step 2: Chạy fail** — `python _quick_gsc_test.py` → FAIL (`ModuleNotFoundError: utils.gsc_client`).
- [ ] **Step 3: Implement module** — signature đúng mục Interfaces; body theo spec:
  - Auth: `google.oauth2.service_account.Credentials.from_service_account_file(path, scopes=[SCOPE])`; token: `creds.refresh(google.auth.transport.requests.Request())` — fetch trong `requests` header `Authorization: Bearer <token>`.
  - POST `{GSC_API_BASE}/{quote(cfg.GSC_SITE_URL, safe="")}/searchAnalytics/query`, body `{"startDate": (today - timedelta(days-1)).isoformat(), "endDate": today, "dimensions": ["query"], "rowLimit": 250, "dataState": "all"}`; 401 → refresh token 1 lần rồi thử lại.
  - `_resolve_path` cho `cfg.GSC_CREDENTIALS_FILE` (tương đối → theo root project).
  - Snapshot/schema/rate limit đúng mục 3.2 spec; state `{date, count, last_fetch}`.
  - Settings block PHẦN E đúng spec (4 hằng số `GSC_SITE_URL` / `GSC_CREDENTIALS_FILE` / `GSC_LOOKBACK_DAYS` / `GSC_MAX_FETCH_PER_DAY`).
- [ ] **Step 4: Chạy pass** — `python _quick_gsc_test.py` → toàn bộ PASS, file test tự xóa `_test_gsc_history.json` khi thoát.
- [ ] **Step 5:** `python -m py_compile utils/gsc_client.py config/settings.py` → sạch.
- [ ] **Step 6: Commit** — `git add utils/gsc_client.py _quick_gsc_test.py(config-ignore) config/settings.py requirements.txt .gitignore` ; `git commit -m "feat: gsc_client - lay du lieu Search Console API qua service account"`.

### Task 2: `build_report()` — báo cáo gộp SERP + GSC

**Files:**
- Create (tiếp tục): bổ sung vào `_quick_gsc_test.py`
- Modify: `utils/gsc_client.py` (thêm phần báo cáo)
- Modify: `utils/rank_tracker.py` (rename 2 helper)

**Interfaces:**
- Consumes: `sparkline(positions: list, width: int = 8) -> str` và `delta_str(cur, prv) -> str` từ `utils.rank_tracker` (Task 2 này đổi tên `_sparkline`/`_delta_str` thành public, giữ nguyên logic, cập nhật mọi tham chiếu trong repo — `grep -rn "_sparkline\|_delta_str"` để bắt hết, gồm `_quick_test.py` nếu còn).
- Produces: `build_report(tail_spark: int = 8) -> str`, `print_report() -> None`, `_match_keywords(rows: dict, keywords: list) -> tuple[dict, dict]` (matched, unmatched).

- [ ] **Step 1: Test fail** — thêm assert vào `_quick_gsc_test.py` (fake cả 2 history file):
  - Matching: keyword `"nối mi quận 2"` khớp query `"noi mi quan 2"` (lệch dấu) và `"nối mi quận 2 giá"` (chứa); một query chỉ khớp MỘT keyword; query lạ `"microsoft surface"` → unmatched. Quyết định khi 1 keyword khớp nhiều query: lấy query có impressions cao nhất làm đại diện.
  - Bảng gộp: có cả 2 history → mỗi từ khóa có Clicks/Hiện/Vị trí TB/CTR + cột hạng SERP; rank history không tồn tại → cột SERP "—" không crash (Review Focus #3).
  - Unmatched → mục "Query mới phát hiện" top 15 theo impressions.
  - GSC rỗng (0 rows) → empty state chứa "chưa có dữ liệu" (Review Focus #4); GSC snapshot cũ > GSC_LOOKBACK_DAYS vẫn in kèm mốc ngày.
- [ ] **Step 2: Chạy fail** — `python _quick_gsc_test.py` → FAIL (`build_report` chưa có).
- [ ] **Step 3: Implement** — rename public 2 helper rank_tracker; `_match_keywords` fold Unicode (`unicodedata.normalize("NFD", s)` bỏ ký tự category `Mn`, lowercase, gộp khoảng trắng) rồi exact → chứa; `build_report` bố cục đúng mục 4 spec (bảng chính + query mới + footer tổng clicks/impressions + ghi chú dữ liệu GSC trễ 2–3 ngày + 3 trường hợp thiếu một phía dữ liệu).
- [ ] **Step 4: Chạy pass** — `python _quick_gsc_test.py` PASS; `python -m py_compile utils/gsc_client.py utils/rank_tracker.py` sạch.
- [ ] **Step 5: Commit** — `git commit -m "feat: bao cao gop SERP + Search Console, matching query lech dau"`.

### Task 3: CLI `--gsc` / `--gsc-report` trong `main.py`

**Files:**
- Modify: `main.py` (2 nhánh elif sau `--rank-report` + 2 dòng help trong `show_strategy()` sau dòng `--rank-report`)

**Interfaces:**
- Consumes: `run_gsc_fetch_cli()`, `print_report()` (Task 1, 2).
- Produces: `run_gsc_fetch_cli() -> None` (định nghĩa trong Task 1 đã — nếu chưa, định nghĩa ở đây: `can_run_fetch` → fetch → `save_snapshot` → `mark_fetch_run` → `print_report`; bắt `GSCSetupError` → in hướng dẫn + `sys.exit(1)`; `requests.HTTPError` → map status 403/400/429 theo bảng mục 5 spec qua `_explain_http_error(status: int) -> str`).

- [ ] **Step 1: Test fail** — thêm vào `_quick_gsc_test.py`: `_explain_http_error(403)` chứa "Restricted" và "SETUP_GSC"; `_explain_http_error(400)` chứa "GSC_SITE_URL"; `_explain_http_error(429)` chứa "quota"; status lạ → chuỗi chung không rỗng.
- [ ] **Step 2: Chạy fail** — `python _quick_gsc_test.py` → FAIL.
- [ ] **Step 3: Implement** — `run_gsc_fetch_cli` + `_explain_http_error` trong `gsc_client.py`; 2 nhánh elif + 2 dòng help trong `main.py` (đúng chuỗi `python main.py --gsc       Lay du lieu Search Console (clicks/impressions)` và `python main.py --gsc-report Xem bao cao Search Console da luu`).
- [ ] **Step 4: Chạy pass + smoke thật** — `python _quick_gsc_test.py` PASS; `python -m py_compile main.py utils/gsc_client.py`; chạy `python main.py --gsc` (máy dev CHƯA có credentials) → in đúng hướng dẫn setup + exit 1, KHÔNG traceback; `python main.py --gsc-report` → "Chưa có dữ liệu Search Console...".
- [ ] **Step 5: Commit** — `git commit -m "feat: cli --gsc / --gsc-report voi bao loi than thien"`.

### Task 4: GUI — nút Search Console trong tab "📈 Xếp Hạng"

**Files:**
- Modify: `ui.py:54` (thêm `self._gsc_running = False` cạnh `self._rank_running`)
- Modify: `ui.py:457-523` khu `_setup_tab_rank` (thêm button + 3 method mới, đặt cạnh nhóm method rank)

**Interfaces:**
- Consumes: `can_run_fetch`, `mark_fetch_run`, `fetch_search_analytics`, `save_snapshot`, `GSCSetupError`, `datetime`, `date` — và `build_report` đã có sẵn (Task 1, 2).
- Produces: methods `run_gsc_fetch_now`, `_gsc_fetch_worker`, `_gsc_fetch_sync` (thuần sync, KHÔNG asyncio — khác worker rank).

- [ ] **Step 1: Implement** — nút `self.btn_gsc` text `"📊  LẤY DỮ LIỆU SEARCH CONSOLE"`, `fg_color="#1a5a7a"`, `hover_color="#2478a8"`, `height=38`, `pack(side="left", padx=(16, 0))` ngay sau `btn_rank_check`; `run_gsc_fetch_now` chặn khi `self.is_running` hoặc `self._gsc_running`, disable nút text "⏳ Đang lấy..."; `_gsc_fetch_worker` chạy `threading.Thread` → `_gsc_fetch_sync` (rate limit → fetch → save → mark), lỗi in `[GSC]` ra console; `finally` bật lại nút + `self.after(0, self._refresh_rank_report)` (refresh tự hiển thị báo cáo gộp mới trong `txt_rank`).
- [ ] **Step 2: Verify** — `python -m py_compile ui.py` sạch (customtkinter chưa cài trong env → không launch được, ghi rõ trong commit message); đọc lại diff khớp pattern worker rank (`_rank_check_worker`).
- [ ] **Step 3: Commit** — `git commit -m "feat: nut Search Console trong tab Xep Hang (customtkinter)"`.

### Task 5: Tài liệu — `docs/SETUP_GSC.md` + README

**Files:**
- Create: `docs/SETUP_GSC.md`
- Modify: `README.md` (section tính năng, 2 dòng CLI, 4 dòng config PHẦN E, cây cấu trúc thêm `gsc_client.py` + `gsc_history.json`)

- [ ] **Step 1: Viết `docs/SETUP_GSC.md`** — 8 bước đúng mục 8 spec: (1) verify property trong Search Console (nankybeauty.com → Domain property khuyên dùng), (2) tạo project Google Cloud Console, (3) bật Search Console API, (4) tạo Service Account + tải JSON key, (5) copy email `...@...iam.gserviceaccount.com` → Search Console → Settings → Users → Add (quyền **Restricted**), (6) lưu key vào `config/gsc_service_account.json`, (7) chạy `python main.py --gsc`, (8) bảng lỗi thường gặp (403/400/429/thiếu file — khớp `_explain_http_error`). Tiếng Việt, UTF-8.
- [ ] **Step 2: Cập nhật README** — section "7. Google Search Console (dữ liệu SEO thật)" sau section Rank Tracker, link tới `docs/SETUP_GSC.md`; dòng CLI + config + cây cấu trúc.
- [ ] **Step 3: Verify + Commit** — link tương đối trong README hoạt động (`ls docs/SETUP_GSC.md`); `git commit -m "docs: huong dan setup Google Search Console + cap nhat README"`.

## Self-Review

1. **Spec coverage:** mục 3.1 (module + API call) → Task 1; 3.2 (schema) → Task 1; 3.3 (PHẦN E) → Task 1; 3.4 (main.py, ui.py, requirements) → Task 3, 4, 1; 3.5 (.gitignore) → Task 1; 4 (báo cáo gộp + matching) → Task 2; 5 (bảng lỗi) → Task 3; 6 (bảo mật — gitignore Task 1, không log token là ràng buộc Global) ; 7 (testing) → Task 1–3 + Global Constraints; 8 (docs) → Task 5. Không còn khoảng trống.
2. **Step scan:** mỗi bước là một hành động có kết quả kiểm chứng được; body chỉ viết cho thuật toán không bị signature+test quyết định (fold Unicode, auth flow).
3. **Type consistency:** `parse_api_response` → dict query→metrics dùng thống nhất ở Task 1/3; `sparkline`/`delta_str` public ở Task 2, `build_report` consume ngay trong cùng task; `_quick_gsc_test.py` thay `gsc.DATA_FILE` sang `_test_gsc_history.json` — khớp pattern `rt.HISTORY_FILE` cũ.
4. **Review Focus:** 5/5 dòng đã gắn test vào Task 1 (2, 4-parse, 5) và Task 3 (1, 3, 4-empty-state).
5. **Proportion:** plan ngắn hơn spec về code-body — chỉ signature + assert + command, không transcribe chương trình.
