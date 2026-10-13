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

**Files:** Modify `utils/scheduler.py`, `utils/rank_tracker.py` (thêm `interactive: bool = True` cho `run_rank_check_cli`), Modify `_quick_scheduler_test.py`.

**Interfaces:** `JOBS`, `run_job(name) -> int`, `_run_rank()`, `_run_gsc()`, `_run_traffic()`, `describe_job(name) -> str`.

- [ ] Step 1 — Test fail trước (monkeypatch `_run_*` bằng counter): job bị `can_run_check`/`can_run_fetch` chặn → exit 0, reason in ra, **không** `record_run(last_run)`, `_run_*` không được gọi. `_run_gsc` raise `SystemExit(1)` → `run_job` trả 1 + state `last_error` có mô tả, không lan exception. `_run_traffic` bật mặc định tắt → 0 lần gọi. Job raise RuntimeError → trả 1, lock vẫn nhả (`os.path.exists(LOCK_FILE)` False). AST: `scheduler.py` chứa `can_run_check`+`can_run_fetch`+`can_run_session`, và không chứa `max_per_day`/`count` tự khai.
- [ ] Step 2 — Chạy → FAIL.
- [ ] Step 3 — Implement (rank: `asyncio.run(run_rank_check_cli(interactive=False))`; gsc: `run_gsc_fetch_cli()`; traffic: import-lười flow `--auto`, chỉ khi `SCHEDULER_TRAFFIC_ENABLE`).
- [ ] Step 4 — Test → ALL PASS + 5 suite cũ PASS.
- [ ] Step 5 — Commit: `feat: F4 job table + run_job (dung lai guard can_run cua module goc, not raise)`

### Task 3: Cấu hình PHẦN G + CLI

**Files:** Modify `config/settings.py`, `main.py`, `_quick_scheduler_test.py`.

- [ ] Step 1 — Test fail trước: settings có `SCHEDULER_RANK_HOURS`/`SCHEDULER_GSC_HOURS`/`SCHEDULER_TRAFFIC_ENABLE=False`/`SCHEDULER_LOCK_STALE=1200`; `main.py` chứa `"--run-job"` và `"--scheduler-status"`; help in 2 lệnh mới.
- [ ] Step 2 — Chạy → FAIL.
- [ ] Step 3 — Implement CLI: `--run-job rank` → exit code từ `run_job`; tên sai → exit 2 + in `JOBS`; `--scheduler-status` → bảng job + 5 run gần nhất + "đang chạy".
- [ ] Step 4 — **Verify thật**: `python main.py --run-job gsc` (máy chưa có credentials → `[Scheduler] ...` exit 0 hoặc 1 tùy guard, không traceback); `--run-job saymax` → exit 2; `--scheduler-status` trên state rỗng → in bảng "chưa chạy lần nào".
- [ ] Step 5 — Commit: `feat: F4 cli --run-job va --scheduler-status + settings Phan G`

### Task 4: GUI trạng thái + tài liệu lịch

**Files:** Modify `ui.py`, `README.md`, Create `docs/SETUP_SCHEDULER.md`.

- [ ] Step 1 — Test fail trước: `ui.py` có method `refresh_scheduler_status` (AST, tên resolve được); README chứa `--run-job`, `SCHEDULER_TRAFFIC_ENABLE`, `SETUP_SCHEDULER`.
- [ ] Step 2 — Chạy → FAIL.
- [ ] Step 3 — Implement: khung "Lịch tự động" trong tab 📈 Xếp Hạng — bảng job (bật/tắt, lần cuối, kết quả) + nút "🧾 LOAD TRẠNG THÁI"; **không** có nút chạy job từ GUI (chạy từ GUI sẽ không có Task Scheduler log, và GUI không phải nơi bấm — nếu cần bấm thì dùng CLI).
- [ ] Step 4 — `docs/SETUP_SCHEDULER.md`: 3 lệnh `schtasks /create` (rank 07:00/13:00/19:00, gsc 09:00, logon trigger), cách kiểm tra `/run`, cách xóa `/delete`, và mục "máy phải bật đúng giờ".
- [ ] Step 5 — README: mục "### 11. Lịch chạy tự động" + bảng PHẦN G + cây project (`utils/scheduler.py`, `docs/SETUP_SCHEDULER.md`).
- [ ] Step 6 — **Verify GUI thật**: probe `TrafficBotUI()`, gọi `refresh_scheduler_status()`, đọc text widget xác nhận có dòng job rank/gsc, không raise.
- [ ] Step 7 — Commit: `feat: F4 bang trang thai scheduler trong GUI + docs SETUP_SCHEDULER (schtasks)`

## Tiêu chí hoàn thành (của card F4)

- Không mở GUI, đúng giờ job chạy (do Task Scheduler gọi), chạy xong có dấu vết trong state.
- Hai job không bao giờ chồng nhau (lock + exit 0 khi bị giành).
- Scheduler không tự nới giới hạn ngày: vẫn là `can_run_check`/`can_run_fetch`/`can_run_session` quyết định.
- Traffic **không** tự chạy khi `SCHEDULER_TRAFFIC_ENABLE=False` (mặc định).

## Known limitations (ghi nhận, không sửa trong plan này)

- Máy tắt đúng giờ thì không chạy; không chạy bù qua ngày (quyết định 2.3).
- Lock chỉ có hiệu lực trong một máy/một bản checkout — hai bản song song không thấy nhau.
- `schtasks` là Windows; chủ máy Linux/VPS cần tự viết cron (spec 2.1 phương án B) — chưa làm vì owner chạy Windows.
- Việc "bật traffic tự động" là quyết định của owner, code mặc định tắt và plan không tự bật.
