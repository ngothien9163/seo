# F3 — Cảnh báo tụt hạng Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hạng rơi quá N vị trí so với lần check trước, hoặc rớt khỏi Top 10 → gửi Telegram (fallback: in console). Bộ não cảnh báo dùng chung; scheduler (F4) sau này chỉ cần gọi lại đúng hàm này.

**Architecture:** Module mới `utils/alerts.py` chia làm 3 tầng tách rời: (1) **rules engine thuần** — input: 2 lần check gần nhất của rank history → output: list cảnh báo, không file I/O; (2) **lưu trữ chống spam** — `data/alerts_state.json`, chặn gửi lại cùng từ khóa trong cùng ngày; (3) **sender** — Telegram qua `requests`, lỗi mạng/token chỉ in log, không bao giờ nổ ngược vào flow chính. Điểm hook: sau khi rank check ghi xong kết quả, và sau khi GSC fetch xong. Điểm vào: CLI `--alerts` + nút "🧪 Gửi thử cảnh báo" trong tab 📈 Xếp Hạng.

**Tech Stack:** Python 3.11, `requests` (đã có trong requirements). Không thêm dependency.

**Spec:** Không có spec riêng — bounded, quyết định chốt trong chat (bảng dưới), theo card F3 của `docs/superpowers/plans/2026-10-06-roadmap-10-tinh-nang.md:64-76`.

## Global Constraints

- **Hedge F10 (roadmap line 168):** file state mới phải nằm trong `data/` và đi qua **một hàm path duy nhất** — `alerts.STATE_FILE` (biến module, test trỏ được) sinh ra từ `_state_path()` đọc `data/alerts_state.json`.
- `ALERTS_ENABLE = False` (mặc định) → **không gửi bất cứ gì**, rules engine vẫn chạy và in console để người dùng thấy thứ đáng lẽ đã gửi.
- Token/chat id **không bao giờ** in ra console/log (chỉ in "đã gửi tới chat ...").
- Sender bắt mọi exception (`requests.RequestException`, `GSCSetupError`-style config error, lỗi JSON response) → in thông báo tiếng Việt, trả `False`; flow rank check/GSC không được chết theo.
- Rules engine là hàm thuần, **không đọc file** trong thân hàm — nhận `dict` vào, trả `list[dict]` ra (test không cần disk).
- So sánh mốc: **lần check ngay trước** (không phải trung bình 3 lần — quyết định ở bảng dưới), ngưỡng `RANK_ALERT_DROP = 5` (rơi **>= 5** hạng mới báo).
- Chống spam: tối đa **1 tin/ngày/từ khóa**; state ghi theo `date.today().isoformat()`.
- Thông điệp tiếng Việt, prefix `[Alert]`.
- Test: `_quick_alert_test.py` ở root (gitignored), assert thuần, KHÔNG pytest; không được đụng `rank_history.json` thật (`rt.HISTORY_FILE` → file test) và không được gọi network (monkeypatch `requests.post`).
- Console Windows: chạy test với `PYTHONIOENCODING=utf-8`.
- Mỗi task một commit.

## Review Focus

1. History rỗng / chỉ 1 lần check / từ khóa mới xuất hiện lần đầu → **không** cảnh báo (không có mốc để so) → test Task 1.
2. `pos = None` (không vào top 100) — là "RỚT", không phải "rơi ∞ hạng"; hai nhánh `None→None`, `None→có hạng`, `có hạng→None` mỗi nhánh một kết luận → test Task 1.
3. Ngưỡng là ranh giới: rơi đúng 5 hạng → báo; rơi 4 hạng → im lặng → test Task 1.
4. Rớt khỏi Top 10 phải báo **một lần** kể cả khi đồng thời rơi ≥5 hạng (không gửi 2 tin cho cùng một chuyện) → test Task 1.
5. Sending fail (network/401) → state **không** bị đánh dấu "đã gửi" hôm nay, lần check sau còn cơ hội gửi lại → test Task 2.
6. `ALERTS_ENABLE=False` → `requests.post` không được gọi lần nào (monkeypatch đếm số lời gọi) → test Task 2.
7. Hook nằm **sau** bước ghi rank history (nếu đặt trước, lịch sử chưa có mốc mới → rules engine so nhầm) → test Task 3 bằng AST + verify thật.

## Quyết định đã chốt (mini design)

| Câu hỏi | Chốt | Lý do |
|---|---|---|
| Nguồn gửi | **Telegram bot** (fallback console khi chưa cấu hình) | Miễn phí, không cần SMTP server, owner tạo bot 1 lần qua @BotFather (hướng dẫn 5 dòng trong README). Email/Slack ngoài phạm vi card F3. |
| Mốc so sánh | **Lần check liền trước**, ngưỡng rơi `>= 5` hạng | Trung bình 3 lần làm chậm tín hiệu thêm 2 ngày; rank check đã có cooldown 1 giờ nên lần trước là mốc đủ tin cậy. |
| Ngưỡng | `RANK_ALERT_DROP = 5`, `RANK_ALERT_TOP10_FALL = True` | Theo khuyến nghị roadmap. |
| Chống spam | 1 tin/ngày/từ khóa, state `data/alerts_state.json` | Check 3 lần/ngày → không gửi 3 tin cho một chuyện. |
| Khi nào evaluate | **Trong** `run_rank_check` sau khi `save_check_result` (không phải một lệnh riêng) | Owner không phải nhớ chạy thêm bước; scheduler F4 tái dùng đúng hàm này. |
| GSC có vào rules không? | Chưa — F3 chỉ rank. GSC hook chỉ gọi lại cùng rules engine (dùng snapshot rank gần nhất) | CTR/rank GSC bất thường để phase sau (roadmap ghi rõ ngoài phạm vi). |
| Trạng thái "đã gửi" có xoá theo thời gian? | State giữ 14 ngày, prune mỗi lần ghi | File không phình vô hạn; 14 ngày đủ dài để debug. |

---

### Task 1: Rules engine thuần + state chống spam

**Files:**
- Create: `utils/alerts.py`
- Create: `_quick_alert_test.py` (gitignored)
- Modify: `config/settings.py` (thêm PHẦN F: `ALERTS_ENABLE`, `RANK_ALERT_DROP`, `RANK_ALERT_TOP10_FALL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`)
- Modify: `.gitignore` (thêm `data/`)

**Interfaces (Produces — Task 2, 3, 4 dựa vào đây):**
- `Alert = dict` có keys `{"keyword", "kind", "old_pos", "new_pos", "delta", "message"}`; `kind ∈ {"drop", "top10_fall"}`.
- `evaluate(checks: dict) -> list[Alert]` — `checks` là dict `{iso_time: {kw: {"pos":..,"url":..}}}` (đúng schema rank history); tự lấy 2 mốc gần nhất, sắp xếp trong hàm.
- `evaluate_from_history() -> list[Alert]` — đọc rank history qua `rank_tracker._load_history()` (import lười) rồi gọi `evaluate`.
- `STATE_FILE` — `<root>/data/alerts_state.json`; `_state_path()` là điểm duy nhất sinh ra path.
- `already_sent_today(keyword: str, day: str = None) -> bool`
- `mark_sent(keyword: str, day: str = None) -> None` — prune state cũ hơn 14 ngày.
- `pending_alerts() -> list[Alert]` — `evaluate_from_history()` lọc bỏ cái đã gửi hôm nay (đây là hàm mà Task 3 hook và Task 4 CLI/GUI gọi).

- [ ] **Step 1 — Test fail trước:**
  - `evaluate({})` → `[]`; 1 check → `[]`.
  - Drop: `{"t1": {"kw": {"pos": 5}}, "t2": {"kw": {"pos": 10}}}` → 1 alert `kind="drop"`, `delta=5`; `pos` 5→9 → `[]` (ranh giới dưới ngưỡng).
  - Top10 fall: 9 → 12 → **một** alert (kind `"top10_fall"`); 3 → 4 → `[]`; 12 → 20 → `[]` (đã ngoài top 10 từ trước, không báo lại).
  - `None` handling: 8 → None → `kind="top10_fall"`, message chứa "khỏi Top 10"; None → 8 → `[]` (hạng tốt lên, và không có mốc cũ để tính drop); None → None → `[]`.
  - Cải thiện hạng: 20 → 6 → `[]`; 12 → 8 → `[]` (đi lên, không phải đối tượng cảnh báo).
  - Nhiều từ khóa cùng rơi → mỗi kw một alert; message chứa con số (`"5"`), tên kw, và domain/không crash khi thiếu url.
  - `message` là chuỗi tiếng Việt hoàn chỉnh, tự gửi được (không cần caller ghép chữ).
  - State: `mark_sent("kw")` rồi `pending_alerts()` (seed history + STATE_FILE tạm) → kw đó biến mất; `day` hôm qua → **không** chặn; `ALERTS` state hỏng JSON → coi như rỗng, không raise.
- [ ] **Step 2 — Chạy → FAIL.**
- [ ] **Step 3 — Implement `utils/alerts.py`** (task 1 chỉ rules + state, chưa sender) + settings + `.gitignore`.
- [ ] **Step 4 — Chạy test → ALL PASS**, `py_compile`.
- [ ] **Step 5 — Commit:** `feat: F3 rules engine canh bao tut hang + state chong spam 1 tin/ngay/tu khoa`

### Task 2: Telegram sender (bất ngờ không được giết flow chính)

**Files:**
- Modify: `utils/alerts.py`
- Modify: `_quick_alert_test.py`
- Modify: `docs/SETUP_ALERTS.md` (mới — 5 bước tạo bot @BotFather + lấy chat id)

**Interfaces (Produces):**
- `is_configured() -> tuple[bool, str]` — (token+chat id đủ chưa, thông điệp tiếng Việt chỉ dẫn `docs/SETUP_ALERTS.md`).
- `send(message: str) -> bool` — `ALERTS_ENABLE=False` → in console, trả `True` (coi như đã thông báo, không spam state); chưa token → in console + trả `True` **nhưng** caller phải phân biệt được (xem `delivery_mode()`); lỗi network → in log, trả `False`.
- `delivery_mode() -> str` — `"telegram" | "console"`.
- `notify(alerts: list[Alert]) -> int` — gửi từng alert (bỏ qua kw đã gửi hôm nay), chỉ `mark_sent` khi send trả `True`, trả số tin đã gửi.
- `run_alert_check_cli()` — in danh sách cảnh báo hiện tại + mode giao hàng.

- [ ] **Step 1 — Test fail trước** (monkeypatch `alerts.requests.post` bằng fake đếm lời gọi):
  - `ALERTS_ENABLE=False` → `requests.post` **0** lần, output có prefix `[Alert]` và nội dung message.
  - `ALERTS_ENABLE=True`, token rỗng → 0 lần post, in hướng dẫn `SETUP_ALERTS`.
  - `ALERTS_ENABLE=True`, token+chat đủ → đúng 1 lần post, URL chứa token, payload `{"chat_id":..., "text":...}`, `parse_mode` không làm nổ; mock trả `{"ok": true}` → `send` trả True và `mark_sent` được gọi.
  - Mock post raise `requests.ConnectionError` → `send` trả False, `notify` **không** mark_sent, không exception lan ra ngoài.
  - Mock trả `{"ok": false, "description": "..."}` → trả False + in mô tả, không in token.
  - `notify([...3 alert, 1 đã gửi hôm nay...])` → chỉ gửi 2 tin.
- [ ] **Step 2 — Chạy → FAIL.**
- [ ] **Step 3 — Implement** sender + `notify` + `docs/SETUP_ALERTS.md`.
- [ ] **Step 4 — Chạy test → ALL PASS.**
- [ ] **Step 5 — Commit:** `feat: F3 telegram sender + notify (that bai khong giet flow, khong in token)`

### Task 3: Hook vào rank check và GSC fetch

**Files:**
- Modify: `utils/rank_tracker.py` (cuối `run_rank_check`, sau `save_check_result`)
- Modify: `utils/gsc_client.py` (cuối `run_gsc_fetch_cli` + `_gsc_fetch_sync` trong `ui.py` nếu cần)
- Modify: `_quick_alert_test.py`

- [ ] **Step 1 — Test fail trước (AST + hành vi):**
  - AST: trong `rank_tracker.run_rank_check`, lời gọi `alerts.check_and_notify(...)` (hoặc `notify(pending...)`) xuất hiện **sau** `save_check_result(...)` — so line number của hai node Call.
  - Behavior: seed history giả, `ALERTS_ENABLE=True` nhưng token rỗng → `run_rank_check` với một `FakePage` (chỉ cần các coroutine `goto/eval_on_selector_all`...) — nếu quá nặng, thay bằng test mức hàm: `check_and_notify()` chạy không raise khi chưa cấu hình, và raise-safe khi sender ném exception (monkeypatch `send` raise).
  - `check_and_notify()` trả `int` (số tin gửi) và không bao giờ raise ở mọi nhánh.
- [ ] **Step 2 — Chạy → FAIL.**
- [ ] **Step 3 — Implement** `alerts.check_and_notify()` + 2 hook (rank sau khi lưu; GSC sau khi fetch xong — rank history không đổi nên GSC hook chỉ in hint nếu có cảnh báo chờ, không gửi trùng).
- [ ] **Step 4 — Chạy test → ALL PASS** + toàn bộ 5 suite cũ vẫn PASS.
- [ ] **Step 5 — Commit:** `feat: F3 hook canh bao sau rank check va sau GSC fetch (khong bao loi khi Telegram chap chenh)`

### Task 4: CLI `--alerts` + nút GUI + tài liệu

**Files:**
- Modify: `main.py`, `ui.py`, `README.md`

- [ ] **Step 1 — Test fail trước:** `main.py` chứa `'"--alerts"'`; `ui.py` có method `run_alert_preview` không có Name chưa resolve; README có dòng `--alerts` + bảng cấu hình có `ALERTS_ENABLE`/`TELEGRAM_*`.
- [ ] **Step 2 — Chạy → FAIL.**
- [ ] **Step 3 — Implement:** CLI `--alerts` in danh sách + mode; GUI: nút "🧪 GỬI THỬ BÁO ĐỘNG" trong tab Xếp Hạng → gửi một tin test nếu đã cấu hình (in hướng dẫn nếu chưa), và label nhỏ "Alerts: Telegram / Console".
- [ ] **Step 4 — Verify thật:** `python main.py --alerts` trên máy chưa cấu hình → in console mode, exit 0; GUI probe: instantiate `TrafficBotUI()`, invoke `run_alert_preview()`, xác nhận không raise và log in ra.
- [ ] **Step 5 — README:** mục "### 10. Cảnh báo tụt hạng (Telegram)"; bảng cấu hình thêm 4 biến; link `docs/SETUP_ALERTS.md`.
- [ ] **Step 6 — Commit:** `feat: F3 cli --alerts + nut gui thu bao dong trong tab Xep Hang, docs SETUP_ALERTS`

## Tiêu chí hoàn thành (của card F3)

- `ALERTS_ENABLE = False` → không gửi gì (kể cả test button: in ra console là chính).
- Một từ khóa tụt hạng chỉ nhận đúng 1 tin trong ngày, dù check 3 lần.
- Rank check / GSC fetch / Ollama không chết khi Telegram sập (test bằng cách monkeypatch sender raise).

## Known limitations (ghi nhận, không sửa trong plan này)

- Chưa verify được việc gửi Telegram thật — cần owner tạo bot + cấp token/chat id (đây là hành động phía owner, code chỉ chạy tới mức mock test).
- Rules chỉ nhìn rank SERP; chưa cảnh báo CTR/impressions bất thường từ GSC (ngoài phạm vi card F3, để phase sau).
- Chưa có email/Slack/Discord.
- State chống spam theo ngày local máy, không theo timezone Search Console.
