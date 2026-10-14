# F4 — Scheduler tự động Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Windows Task Scheduler gọi `python main.py --run-job rank|gsc|traffic` đúng giờ; job tự biết "bây giờ có được chạy không", không bao giờ chồng nhau, và để lại dấu vết đọc được bằng `--scheduler-status` / GUI.

**Architecture:** `utils/scheduler.py` mỏng — bảng job + lock + state + status. **Không có bộ đếm giới hạn riêng**: mỗi job gọi lại `can_run_check` / `can_run_fetch` / `can_run_session` của chính module nó (nguồn sự thật đã có), rồi gọi lại entry CLI hiện hữu (`run_rank_check_cli`, `run_gsc_fetch_cli`, flow `--auto`). Đồng hồ thật nằm ngoài code (Task Scheduler).

**Tech Stack:** Python 3.11 stdlib (`json`, `os`, `time`, `asyncio`). Không thêm dependency — APScheduler/cron bị loại ở spec.

**Spec:** `docs/superpowers/specs/2026-10-13-f4-scheduler-design.md` (đã duyệt: phương án A, traffic TẮT tự chạy, không chạy bù qua ngày, lock stale 20 phút).

## Global Constraints

- **Không tự đếm:** scheduler không được có `count/max_per_day` riêng. AST test: `utils/scheduler.py` phải gọi `can_run_check`, `can_run_fetch`, `can_run_session` và **không** được chứa key mới trong state dạng "số lần đã chạy hôm nay".
- Job nào cũng phải **idempotent**: gọi 2 lần liền trong cùng giờ → lần 2 bị chặn bởi `can_run_*` hoặc bởi lock, không chạy trùng công việc.
- `run_job(name) -> int` **không bao giờ raise**, kể cả job internals gọi `sys.exit()` (`SystemExit` là `BaseException` — `except Exception` không bắt được, phải bắt riêng).
- Lock `data/scheduler.lock`: ghi `{"pid", "job", "heartbeat"}`; heartbeat mỗi ≤30s khi job dài; stale > `SCHEDULER_LOCK_STALE` (mặc định 1200s) → được giành. Job chết giữa chừng vẫn phải nhả lock (`finally`).
- Mọi path state đi qua **một hàm duy nhất** (`_state_path()`, `_lock_path()`) và nằm trong `data/` (hedge F10, roadmap line 168).
- `SCHEDULER_TRAFFIC_ENABLE = False` (mặc định) → `run_job("traffic")` trả 0 kèm thông điệp "đang tắt theo quyết định owner", **không** mở browser. Bật lên thì vẫn bị `rate_limiter` chặn như chạy tay.
- Job `rank` chạy nền phải **không đòi input**: `run_rank_check_cli(interactive=False)` → gặp CAPTCHA là dừng + lưu kết quả một phần, thay vì chờ người giải.
- State `data/scheduler_state.json`: `{"jobs": {name: {last_run, last_status, last_error, exit_code}}, "runs": [...]}`; `runs` giữ tối đa 50 dòng để GUI hiện chuỗi gần nhất. File hỏng JSON → coi như rỗng.
- Thông điệp tiếng Việt, prefix `[Scheduler]`. Không in đường dẫn credential.
- Test `_quick_scheduler_test.py` ở root (gitignored), assert thuần, KHÔNG pytest; không mở browser / không gọi network (monkeypatch `_run_rank`/`_run_gsc`/`_run_traffic`), không đụng state thật (patch `scheduler.STATE_FILE`/`LOCK_FILE` + `rt.HISTORY_FILE`).
- Console Windows: chạy test với `PYTHONIOENCODING=utf-8`.
- Mỗi task một commit.

## Review Focus

1. `SystemExit` từ `run_gsc_fetch_cli` (branch thiếu credentials) → `run_job("gsc")` phải trả exit code đó và ghi `last_error`, **không** làm chết cả process scheduler. Test Task 2.
2. Lock: hai `run_job` lồng nhau → job thứ hai bỏ qua (exit 0). Heartbeat cũ 25 phút → giành được. Test Task 1.
3. Job bị `can_run_*` chặn → state **không** bị ghi `last_run` (nếu ghi, GUI báo "đã chạy 19:00" trong khi chưa chạy gì). Test Task 2.
4. `traffic` mặc định tắt: test đếm số lần `_run_traffic` được gọi = 0 khi `SCHEDULER_TRAFFIC_ENABLE=False`. Test Task 2.
5. Không có bộ đếm ngày riêng: AST test. Test Task 2.
6. Nhả lock khi job raise: test Task 1 + hành vi Task 2.
7. `--run-job <tên sai>` → exit 2 + in danh sách hợp lệ (theo thông lệ `--export`). Test Task 3.

## Quyết định đã chốt

| Câu hỏi | Chốt | Lý do |
|---|---|---|
| Đồng hồ | Windows Task Scheduler (owner duyệt 2026-10-13) | Không process nằm chờ, chịu được reboot, không thêm dependency. |
| Job tự chạy | rank + gsc = BẬT; traffic = TẮT (owner duyệt) | Traffic là phần nhạy cảm nhất, chạy không có ai nhìn = lỗi tích âm thầm. |
| Bỏ lỡ thì sao | Không chạy bù qua ngày; trong ngày cho phép chạy khi tới lượt | Gộp 3 lần check một lúc = pattern bất thường gửi lên Google. |
| Chồng job | File lock theo PID + heartbeat stale 20 phút | Task Scheduler không biết job trước còn sống hay đã treo. |
| Trạng thái nhìn ở đâu | `data/scheduler_state.json` + `--scheduler-status` + GUI | GUI chạy process khác nên phải đọc file, không đọc biến in-process. |

---

### Task 1: State + lock (nền móng, chưa có job)

**Files:** Create `utils/scheduler.py`, Create `_quick_scheduler_test.py`, Modify `.gitignore` (data/ đã có từ F3 → verify).

**Interfaces (Produces):** `_state_path()`, `_lock_path()`, `STATE_FILE`, `LOCK_FILE`, `read_state() -> dict`, `record_run(name, status, exit_code, error="")`, `acquire_lock(job) -> tuple[bool, str]`, `release_lock()`, `touch_lock()`, `status() -> dict`, `recent_runs(limit=10) -> list[dict]`.

- [x] Step 1 — Test fail trước: state rỗng → `read_state()` = `{"jobs": {}, "runs": []}`; file hỏng JSON → như rỗng, không raise. `record_run` tạo `data/`, giữ ≤50 runs. `acquire_lock("rank")` → True; acquire lần 2 (PID khác, heartbeat mới) → False + reason chứa PID đang giữ; heartbeat cũ 25 phút → True (giành); `release_lock` xóa file và **chỉ xóa lock của mình** (PID khác ghi đè thì không xóa).
- [x] Step 2 — Chạy → FAIL (`ModuleNotFoundError: No module named 'utils.scheduler'`).
- [x] Step 3 — Implement `utils/scheduler.py` (paths + state + lock + `status`/`recent_runs`/`lock_holder`).
- [x] Step 4 — Test → ALL PASS (14 test) + `py_compile`; verify path thật: `data/scheduler_state.json`, `data/scheduler.lock`, `status()` trên máy chưa chạy gì → `{'jobs': {}, 'runs': [], 'running': None}`. `.gitignore` đã có `data/` từ F3 → không sửa.
- [x] Step 5 — Commit: `feat: F4 scheduler state + file lock (pid heartbeat, stale 20 phut)`

### Task 2: Bảng job + run_job (tái dùng guard cũ)

**Files:** Modify `utils/scheduler.py`, `utils/rank_tracker.py` (thêm `interactive: bool = True` cho `run_rank_check_cli`), Create `utils/automation.py` (tách flow `--auto` khỏi `main.py` — xem ghi chú Step 3), Modify `main.py`, Modify `_quick_scheduler_test.py`.

**Interfaces:** `JOBS`, `run_job(name) -> int`, `_run_rank()`, `_run_gsc()`, `_run_traffic()`, `describe_jobs() -> list[str]` (plan ban đầu ghi `describe_job(name) -> str`; bản test đã viết từ trước cần dạng list nhiều dòng cho CLI in danh sách → chốt `describe_jobs()`), `HEARTBEAT_INTERVAL`, `SCHEDULER_TRAFFIC_ENABLE`, `utils/automation.py::run_one_session(use_search=True) -> int`.

- [x] Step 1 — Test fail trước (monkeypatch `_run_*` bằng counter): job bị `can_run_check`/`can_run_fetch` chặn → exit 0, reason in ra, **không** `record_run(last_run)`, `_run_*` không được gọi. `_run_gsc` raise `SystemExit(1)` → `run_job` trả 1 + state `last_error` có mô tả, không lan exception. `_run_traffic` bật mặc định tắt → 0 lần gọi. Job raise RuntimeError → trả 1, lock vẫn nhả (`os.path.exists(LOCK_FILE)` False). AST: `scheduler.py` chứa `can_run_check`+`can_run_fetch`+`can_run_session`, và không chứa `max_per_day`/`count` tự khai.
- [x] Step 2 — Chạy → FAIL: 11 FAIL (`run_job`/`_guard_*`/`describe_jobs`/`HEARTBEAT_INTERVAL`/`SCHEDULER_TRAFFIC_ENABLE` chưa tồn tại + ràng buộc gọi guard gốc).
- [x] Step 3 — Implement: rank `asyncio.run(run_rank_check_cli(interactive=False))`; gsc `run_gsc_fetch_cli()` (tự `sys.exit(1)` khi thiếu credential → `run_job` bắt `SystemExit` riêng vì nó là `BaseException`); traffic `_run_traffic` → `automation.run_one_session(use_search=True)`.
  Ba chi tiết lệch plan nhưng có lý do, giữ lại:
  1. **`utils/automation.py` mới**: flow browser của `--auto` nằm inline trong `main.py`; scheduler mà copy lần 2 là có 2 chỗ phải sửa khi flow đổi. `main.py --auto|--search` giờ chỉ gọi `run_one_session()` (giữ nguyên exit 1 khi bị rate limit). `run_one_session` không raise, và `mark_session_run()` chỉ chạy khi session xong — session nổ giữa chừng không bị đếm oan.
  2. **`JOBS` lưu TÊN hàm** (`"guard": "_guard_rank"`), `run_job` resolve qua `globals()`: nếu lưu object thì monkeypatch `sc._run_rank` trong test không có tác dụng, và test sẽ thật sự mở browser.
  3. **`_write_lock` ghi nguyên tử** (tmp + `os.replace`): watchdog ghi heartbeat song song với runner đọc lock; ghi trực tiếp có cửa đọc phải file cụt.
- [x] Step 4 — Test → **ALL PASS (29 test)**; 5 suite cũ PASS (`LOGIC TEST PASS`, `[GSC-TEST]`, `[EXPORT-TEST]`, `[KEYWORD-TEST]`, `[ALERT-TEST] 59`); **6/6 mutation CAUGHT** (bỏ `can_run_session`, bỏ `release_lock`, `except BaseException`→`ValueError`, `interactive=True`, bỏ guard, bỏ `mark_session_run`). Live: `run_job("saymax")` → exit 2 + in 3 job; `run_job("traffic")` → exit 0 + "đang TẮT theo quyết định của owner"; `read_state()` vẫn `{"jobs": {}, "runs": []}` và không còn lock. Scan CJK trên 5 file touched: 0.
- [x] Step 5 — Commit: `feat: F4 job table + run_job (dung lai guard can_run cua module goc, not raise)`

### Task 3: Cấu hình PHẦN G + CLI

**Files:** Modify `config/settings.py`, `main.py`, `utils/scheduler.py` (`format_status`/`run_status_cli` + giờ trong `JOBS`), Modify `_quick_scheduler_test.py`.

**Interfaces:** `SCHEDULER_RANK_HOURS`/`SCHEDULER_GSC_HOURS`/`SCHEDULER_TRAFFIC_ENABLE`/`SCHEDULER_LOCK_STALE`; `scheduler.CLOCK_NOTE`, `_hours_text(job)`, `format_status() -> list[str]`, `run_status_cli() -> int`; `main.py --run-job <name>`, `--scheduler-status`.

- [x] Step 1 — Test fail trước: settings có `SCHEDULER_RANK_HOURS=[7,13,19]`/`SCHEDULER_GSC_HOURS=[9]`/`SCHEDULER_TRAFFIC_ENABLE=False`/`SCHEDULER_LOCK_STALE=1200` (+ "PHẦN G" trong file); `_lock_stale_after()` phải đổi theo cfg **lúc gọi** (không snapshot); `describe_jobs()` in giờ và nói rõ đồng hồ thật thuộc Task Scheduler; `run_status_cli()` trên state rỗng → 0 + "chưa chạy lần nào" + đủ 3 job, có run → hiện `last_status`/`last_error` + mục "Gần đây", có lock → "đang chạy"; `main.py` chứa `"--run-job"`/`"--scheduler-status"` và **help in 2 lệnh mới** (AST đọc body `show_strategy`).
- [x] Step 2 — Chạy → FAIL: 7 FAIL/ERROR (`run_status_cli` chưa tồn tại, chưa có PHẦN G, describe_jobs chưa có giờ).
- [x] Step 3 — Implement CLI: `--run-job rank` → `sys.exit(run_job(name))`; thiếu tên/tên sai → `run_job("")` rơi vào nhánh "Không có job" → exit 2 + in `describe_jobs()` (đúng thông lệ `--export`); `--scheduler-status` → `run_status_cli()` in `format_status()`, luôn trả 0 (xem trạng thái không phải là chạy việc). Giờ trong settings chỉ là **lịch mong muốn** → in cạnh mỗi job + `CLOCK_NOTE` nói thẳng đồng hồ thật ở Windows (rule không có enforcement trong code thì doc/CLI phải tự nhận).
- [x] Step 3b — **Sửa lỗi thật tìm thấy khi verify** (ngoài plan, thuộc entry point): console Windows ở máy này là cp1252 → `python main.py --scheduler-status` **crash `UnicodeEncodeError: '\u1edd'`, exit 1** ngay tại dòng `print(line)`. Job chạy không có ai nhìn mà chết vì in tiếng Việt thì vô dụng → `main.py` gọi `sys.stdout/stderr.reconfigure(encoding="utf-8", errors="replace")` (guard `hasattr` + try/except) ngay sau `import sys`. Đây là entry point CLI duy nhất, `ui.py` không liên quan (tự redirect stdout).
- [x] Step 4 — **Verify thật** (không `PYTHONIOENCODING`, tức đường Task Scheduler thật gọi): `--scheduler-status` state rỗng → exit 0, bảng 3 job "chưa chạy lần nào"; `--run-job saymax` → exit 2 + danh sách; `--run-job` (thiếu tên) → exit 2; `--run-job traffic` → exit 0 + "đang TẮT theo quyết định của owner"; `--run-job gsc` trên máy chưa có credentials → `[GSC] ❌ ...docs/SETUP_GSC.md` rồi `[Scheduler] gsc: lỗi — Job kết thúc sớm bằng sys.exit(1)...`, **exit 1, không traceback**, lock được nhả, `--scheduler-status` hiện đúng dòng error đó. State probe `data/scheduler_state.json` đã xóa sau verify. Test: **ALL PASS (36)**; 5 suite cũ PASS; **3/3 mutation CAUGHT** (snapshot `LOCK_STALE_DEFAULT`, bỏ dòng "đang chạy", `run_status_cli` return sớm); CJK scan 4 file touched = 0.
- [x] Step 5 — Commit: `feat: F4 cli --run-job va --scheduler-status + settings Phan G`

### Task 4: GUI trạng thái + tài liệu lịch

**Files:** Modify `ui.py`, `README.md`, `docs/superpowers/plans/2026-10-06-roadmap-10-tinh-nang.md`, Create `docs/SETUP_SCHEDULER.md`, Modify `_quick_scheduler_test.py`.

- [x] Step 1 — Test fail trước: `ui.py` có method `refresh_scheduler_status` + widget `btn_scheduler_refresh`/`txt_scheduler` + `command=self.refresh_scheduler_status`, **không có chuỗi `run_job` trong ui.py** (cấm nút chạy job); mọi `Name` trong method resolve được (helper `_resolve_ui_method` — tên import trong hàm + tên gán cục bộ + builtins); `docs/SETUP_SCHEDULER.md` có ≥4 `schtasks /Create`, `/Run`, `/Query`, `/Delete`, trỏ thẳng `venv\Scripts\python.exe main.py`, nói chỗ xem log + "bật đúng giờ"; README có `--run-job`, `--scheduler-status`, 3 biến PHẦN G, `utils/scheduler.py`, mục "Lịch chạy tự động".
- [x] Step 2 — Chạy → FAIL: 4 FAIL (đúng 4 test mới).
- [x] Step 3 — Implement: khung **🗓 LỊCH TỰ ĐỘNG** = `CTkFrame` row 4 của tab Xếp Hạng, label đầu + nút 🧾 + `CTkTextbox` 140px Consolas; `refresh_scheduler_status()` gọi `format_status()` **trên main thread** (chỉ đọc file, không IO dài) và bọc `try/except` để GUI không bao giờ chết vì state hỏng. **Không** có nút chạy job: `run_job` không xuất hiện trong `ui.py` (test) — GUI là nơi xem, CLI là nơi bấm.
- [x] Step 4 — `docs/SETUP_SCHEDULER.md`: 4 lệnh `/Create` (rank 07:00/13:00/19:00 + gsc 09:00, mỗi task một `/ST` vì `schtasks` chỉ nhận một giờ — đã đọc `schtasks /Create /?` để xác nhận cờ `/SC /ST /TN /TR /RL /F /SC ONLOGON`), task ONLOGON bắt kịp trong ngày, mục 3 trả lời thẳng "đổi giờ thì đổi trên Windows, sửa `SCHEDULER_RANK_HOURS` không làm Windows đổi lịch", `/Query /V /FO LIST` + `/Run` + `/Delete`, log `data\scheduler.log`, 5 lỗi thường gặp, mục giới hạn.
- [x] Step 5 — README: mục **"### 11. Lịch chạy tự động — Windows Task Scheduler (F4)"** (đồng hồ không ở trong code / không tự nới giới hạn / traffic TẮT / không chạy bù / job nền không ngồi chờ CAPTCHA / GUI không có nút chạy job), 2 dòng CLI mới, 3 dòng bảng cấu hình PHẦN G, cây project thêm `utils/scheduler.py` + `utils/automation.py` và `data/` giờ có `scheduler_state.json`/`scheduler.lock`.
- [x] Step 6 — **Verify GUI thật** (`_probe_f4_gui.py`, đã xóa sau khi chạy): khởi tạo `TrafficBotUI()`, state giả 2 job + lock PID 999999 do `rank` giữ → panel render `rank 07:00, 13:00, 19:00 lần cuối ... → ok (exit 0) — đang chạy`, `gsc ... → error (exit 1)` kèm dòng `lỗi: Job kết thúc sớm bằng sys.exit(1)`, `traffic không tự chạy chưa chạy lần nào`, mục "Gần đây" 2 dòng theo thứ tự mới nhất trước; `btn_scheduler_refresh.invoke()` không raise; label "LỊCH TỰ ĐỘNG" tìm thấy trong tab; 2 lỗi của chính probe (bắt `LỊCH` trong textbox, cấm mọi dòng "chưa chạy") đã sửa thành assertion đúng trước khi kết luận PASS. `[F4-GUI-PROBE] PASS`.
- [x] Step 7 — Commit: `feat: F4 bang trang thai scheduler trong GUI + docs SETUP_SCHEDULER (schtasks)` — kèm dòng **Trạng thái** của card F4 trong roadmap (ghi rõ lệch phương án A so với card gốc).

## Tiêu chí hoàn thành (của card F4)

- Không mở GUI, đúng giờ job chạy (do Task Scheduler gọi), chạy xong có dấu vết trong state.
- Hai job không bao giờ chồng nhau (lock + exit 0 khi bị giành).
- Scheduler không tự nới giới hạn ngày: vẫn là `can_run_check`/`can_run_fetch`/`can_run_session` quyết định.
- Traffic **không** tự chạy khi `SCHEDULER_TRAFFIC_ENABLE=False` (mặc định).

## Known limitations (ghi nhận, không sửa trong plan này)

- ~~**`cfg.MAX_SESSIONS_PER_DAY` vẫn bị bỏ qua** (pre-existing): `can_run_session` mặc định hardcode 25/300, `get_today_summary` hardcode `25 - count`.~~ **✅ ĐÃ SỬA (2026-10-14, ngoài plan F4 — tối ưu theo owner):** `rate_limiter` thêm `_max_per_day()`/`_min_interval()` đọc `cfg.MAX_SESSIONS_PER_DAY`/`MIN_INTERVAL_BETWEEN_SESSIONS` **lúc gọi**; `can_run_session` (default `None`→cfg, tham số truyền thẳng vẫn thắng) và `get_today_summary` (remaining + next_window) đều đi qua 2 helper đó. Đổi knob trong `settings.py` giờ có hiệu lực thật. **Không** đụng `scheduler.py` (AST test `max_per_day/MAX_SESSIONS` vẫn xanh vì sửa nằm ở rate_limiter). Test `_quick_rate_limit_test.py` 7/7; mutation `_mut_rate_limit` 2/2 KILLED (cố hardcode 25 / 300 → bị bắt). Scheduler vẫn cố ý KHÔNG truyền giới hạn riêng — giữ nguyên ý "module gốc quyết định". Scheduler cố ý KHÔNG truyền giới hạn riêng: AST test cấm chuỗi `max_per_day`/`MAX_SESSIONS` xuất hiện trong `scheduler.py` để không ai nhân bản bộ đếm ở đây.
- Job `rank`/`gsc` mà module gốc từ chối (đã đạt giới hạn) thì `run_job` trả 0 và in lý do — Task Scheduler coi là "chạy thành công". Đúng ý (không có gì để chạy) nhưng log `schtasks` sẽ không phân biệt được "bỏ qua" và "xong việc".

- Máy tắt đúng giờ thì không chạy; không chạy bù qua ngày (quyết định 2.3).
- Lock chỉ có hiệu lực trong một máy/một bản checkout — hai bản song song không thấy nhau.
- `schtasks` là Windows; chủ máy Linux/VPS cần tự viết cron (spec 2.1 phương án B) — chưa làm vì owner chạy Windows.
- Việc "bật traffic tự động" là quyết định của owner, code mặc định tắt và plan không tự bật.
- **Lệnh `schtasks` trong `docs/SETUP_SCHEDULER.md` chưa đăng ký thật** trên máy này: chỉ kiểm tra cờ hợp lệ bằng `schtasks /Create /?`, còn tạo task = sửa lịch của máy owner nên để owner chạy. Hệ quả: chưa có bằng chứng "job chạy đúng giờ lúc không có ai"; mới chỉ có bằng chứng `--run-job`/`--scheduler-status` chạy đúng khi gọi tay.
- Panel GUI đọc state **lúc mở tab và lúc bấm 🧾** — không tự refresh; mở GUI suốt ngày thì số liệu trên màn hình có thể cũ hơn `data/scheduler_state.json`.
