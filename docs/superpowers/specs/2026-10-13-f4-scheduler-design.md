# Spec: F4 — Scheduler tự động (chạy nền không cần mở GUI)

- Ngày: 2026-10-13
- Trạng thái: **ĐÃ DUYẾT 2026-10-13** — owner chọn phương án A (Windows Task Scheduler làm đồng hồ) và job traffic **TẮT** tự chạy (chỉ rank + GSC). 2.3 (không chạy bù qua ngày) và 2.4 (`data/` + lock stale 20 phút) giữ như đề xuất. Plan: `docs/superpowers/plans/2026-10-13-f4-scheduler.md`.
- Phân loại: Architectural — thêm một vòng đời process mới, đụng file state mới và quyết định "để tự động chạy phần nào" (rủi ro thật).
- Card gốc: `docs/superpowers/plans/2026-10-06-roadmap-10-tinh-nang.md` (mục F4).

## 1. Mục tiêu & bối cảnh

Hôm nay mọi lệnh đều do người bấm: `--rank` (tối đa 3 lần/ngày), `--gsc` (4 lần/ngày), `--auto --search` (25 session/ngày, dồn vào peak hours). Các giới hạn đó đã có sẵn trong code (`rank_tracker.can_run_check`, `gsc_client.can_run_fetch`, `rate_limiter.can_run_session`) và **đã tự reset theo ngày** — nghĩa là phần "được chạy chưa" đã xong, chỉ thiếu phần "ai bấm lúc nào".

Mục tiêu card F4: đến giờ là job tự chạy, máy không cần mở GUI; GUI (khi mở) chỉ là bảng trạng thái.

Ví dụ cụ thể để hình dung (đúng lịch hiện tại của `nankybeauty.com`): 07:00 check hạng lần 1 → 09:00-11:00 loạt session traffic → 13:00 check hạng lần 2 + fetch GSC → 19:00 check hạng lần 3...Owner không phải nhớ bấm gì, và sáng hôm sau mở GUI lên thấy "lần check gần nhất 19:02, 18/18 từ khóa".

**Tiêu chí thành công:**
1. Không mở GUI, không cần có terminal nào đứng chờ: đúng giờ job chạy, sai giờ/sai ngày thì không.
2. Hai job **không bao giờ chồng nhau** (rank check đang mở browser mà GSC/traffic xen vào là source lỗi bùa không đoán được).
3. Chạy quá giới hạn ngày không thể xảy ra — scheduler **tái dùng** chính các hàm `can_run_*` đã có, không tự đếm lại.
4. GUI thêm bảng trạng thái đọc được từ file state, kể cả khi scheduler chạy ở process khác.
5. Tắt máy lúc 19:00 → không có chuyện 8 giờ sáng hôm sau nổ 3 job một lúc.

## 2. Quyết định cần owner duyệt

### 2.1. Ai làm "đồng hồ"?

| Phương án | Cách hoạt động | Đánh giá |
|---|---|---|
| **A — Windows Task Scheduler (khuyến nghị)** | Tool chỉ thêm `python main.py --run-job rank\|gsc\|traffic` (idempotent, tự biết "bây giờ có được chạy không"). Lịch thật nằm trong Task Scheduler, ghi bằng 3 lệnh `schtasks /create` trong `docs/SETUP_SCHEDULER.md`. | Không thêm dependency, không có process Python nằm chờ, chịu được reboot/đổi giờ máy. Nhiệm vụ của code chỉ còn: job entry + lock + state. |
| B — Daemon loop trong Python (`--daemon`) | Một process chạy `while True: ngủ đến giờ kế tiếp rồi chạy job`. | Tự chủ nền tảng nhưng phải có người giữ process sống; máy reboot là chết âm thầm, và "quên không bật daemon" đúng bằng cái rủi ro mà tính năng này sinh ra để xóa. |
| C — Thư viện APScheduler/cron | Cron thực sự trong process. | **Loại:** thêm dependency chỉ để tính giờ — thứ Windows đã có sẵn. |

→ Chọn **A**; B chỉ làm nếu owner muốn chạy trên máy không có Task Scheduler (Linux/VPS) — khi đó thêm đúng một file `--daemon` mỏng gọi lại cùng job table.

### 2.2. Job nào được phép tự chạy thật? (quyết định rủi ro, thuộc về owner)

| Job | Rủi ro | Đề xuất |
|---|---|---|
| `rank` (check hạng SERP) | Mở browser thật, có thể gặp CAPTCHA → gặp là dừng và lưu kết quả một phần (`on_captcha` CLI hiện đòi người giải). Chạy lúc 3 giờ sáng thì không có ai giải. | **Tự chạy được**, nhưng job tự động phải dùng chế độ "gặp CAPTCHA → bỏ, hẹn lần sau" thay vì chờ input. |
| `gsc` (Search Console API) | Không scrape, không CAPTCHA, chỉ gọi API có key. | **Tự chạy được**, an toàn nhất. |
| `traffic` (`--auto --search`: session mô phỏng người) | Đây là phần nhạy cảm nhất của tool (anti-detect, giới hạn 25 session/ngày). Chạy mà không có ai nhìn thì một chuỗi lỗi sẽ âm thầm tích cả ngày. | **Mặc định TẮT** (`SCHEDULER_TRAFFIC_ENABLE = False`). Bật khi nào? Khi nào rank/GSC đã chạy nền ổn định vài tuần. |

### 2.3. Job bị bỏ lỡ (máy tắt) có chạy bù không?

**Không chạy bù qua ngày** — quá nửa đêm, sổ ngày mới tự reset. Trong cùng ngày: nếu mở máy muộn và `can_run_check()` còn lượt, job kế tiếp chạy luôn khi được đánh thức (Task Scheduler đặt thêm một trigger "at log on"). Lý do: gộp 3 lần check vào một lúc = 3 lần Google thấy cùng một pattern liên tiếp, đúng thứ nên tránh.

### 2.4. State & lock để ở đâu?

`data/scheduler_state.json` (theo hedge F10 — mọi file state mới nằm trong `data/`, đi qua một hàm path duy nhất) và `data/scheduler.lock` (PID + heartbeat). Lock **stale sau 20 phút** không thấy heartbeat → bị coi là chết và bị giành, để một lần crash không khóa vĩnh viễn toàn bộ lịch.

## 3. Kiến trúc dự kiến (sau khi duyệt)

`utils/scheduler.py` — một nhiệm vụ: bảng job + decide "bây giờ có chạy không" + lock + state.

| Hàm | Chức năng |
|---|---|
| `JOBS` | `{"rank": _run_rank, "gsc": _run_gsc, "traffic": _run_traffic}` — mỗi hàm gọi lại đúng entry đã có (`run_rank_check_cli`, `run_gsc_fetch_cli`, flow `--auto`), không nhân bản logic. |
| `run_job(name) -> int` | Lock → kiểm tra `can_run_*` của chính module đó → chạy → ghi state (`last_run`, `last_status`, `last_error`) → nhả lock. Trả exit code. |
| `acquire_lock()` / `release_lock()` | `data/scheduler.lock`: ghi PID + timestamp, heartbeat mỗi 30s; stale > 20 phút thì giành. |
| `status() -> dict` | Đọc state: job nào chạy lúc nào, lần cuối kết quả ra sao, có đang chạy không — cho CLI `--scheduler-status` và GUI. |
| `next_runs() -> list[str]` | Suy ra lịch sắp tới **từ cấu hình** (`RANK_CHECK_MAX_PER_DAY`, `PEAK_HOURS`) để GUI hiện "lần chạy kế tiếp 19:00". |

Điểm vào: `python main.py --run-job rank|gsc|traffic`, `python main.py --scheduler-status`, GUI tab mới/trong tab 📈 Xếp Hạng (quyết ở plan). Hook cảnh báo F3 **không đổi**: scheduler gọi đúng `run_rank_check_cli` → `check_and_notify()` đã nằm trong đó.

Cấu hình mới (`config/settings.py`, PHẦN G): `SCHEDULER_RANK_HOURS`, `SCHEDULER_GSC_HOURS`, `SCHEDULER_TRAFFIC_ENABLE`, `SCHEDULER_LOCK_STALE`.

## 4. Xử lý lỗi

- Đang có job khác → in `[Scheduler] ⏭ Bỏ qua (job 'gsc' đang chạy, PID 1234)` + exit 0 (Task Scheduler coi là thành công, không báo lỗi lặp lại).
- Vượt giới hạn ngày → chính thông điệp tiếng Việt của `can_run_*` (`"Đã đạt giới hạn 3 lần check xếp hạng/ngày"`), exit 0.
- Job raise exception → bắt tại `run_job`, ghi `last_error` vào state, in `[Scheduler] ❌ ...`, exit 1 để Task Scheduler log. **Không** để lỗi scheduler làm hỏng rank/GSC chạy tay.
- State/lock JSON hỏng → coi như rỗng, ghi đè; scheduler phải tự khỏi.

## 5. Bảo mật

Không new surface: scheduler không nhận input từ network, không lưu credential. `docs/SETUP_SCHEDULER.md` dùng `schtasks` trỏ thẳng tới `venv\Scripts\python.exe main.py --run-job ...` — không PowerShell download, không chạy với quyền admin.

## 6. Testing

`_quick_scheduler_test.py` (assert thuần, không pytest):
- `run_job("rank")` với `can_run_check()` trả False → không gọi hàm chạy, exit 0, state không đổi.
- Lock: process "đang giữ" (PID giả + heartbeat mới) → job thứ hai bị bỏ qua; heartbeat cũ 25 phút → giành lock được.
- `run_job` raise inside → state có `last_error`, không exception lan ra, lock vẫn được nhả (kể cả khi job chết giữa chừng).
- `status()`/`next_runs()` với state rỗng/hỏng → không crash.
- Job table không tự đếm giới hạn ngày: AST test asserts scheduler gọi `can_run_check`/`can_run_fetch`/`can_run_session` chứ không có bộ đếm riêng.
- **Không test nào mở browser hay gọi network** — `_run_*` được monkeypatch.

## 7. Tài liệu

`docs/SETUP_SCHEDULER.md`: 3 lệnh `schtasks /create` (copy-paste được, kèm bản xóa), giải thích "máy phải bật đúng giờ", and cách tắt. README: mục 11 + bảng PHẦN G.

## 8. Rủi ro & giới hạn đã cân nhắc

- Task Scheduler chỉ chạy khi máy bật; đây là tool cá nhân trên máy Windows của owner, không phải server — chấp nhận, ghi rõ trong docs.
- `traffic` tự chạy vẫn là quyết định của owner (2.2); code mặc định tắt và plan không được "tiện tay" bật hộ.
- Proxy rotation (F5) **không** nằm trong F4 — đã từ chối từ đầu vì mục tiêu của nó là né CAPTCHA.
- Lock chống song song chỉ có hiệu lực trong cùng một máy/file state; hai bản checkout song song sẽ không thấy nhau.
