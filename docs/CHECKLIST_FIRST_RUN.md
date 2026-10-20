# Checklist "Bật nhà mới" — chạy thật từng tính năng lần đầu

> Mục đích: toàn bộ nhóm tính năng (T22–T54, code từ F1) đã xanh ~90 quick test
> **mock/offline**; checklist này bật từng nhóm theo thứ tự rẻ → đắt, mỗi bước có
> cách kiểm tra **kết quả mong đợi** và **nếu lỗi** rõ ràng. Làm theo thứ tự; đừng nhảy cóc.
>
> Lệnh nào in lỗi bạn không tự giải được → chạy `python main.py --doctor` trước —
> bảng ✓/! chỉ đúng chỗ thiếu; vẫn kẹt thì gửi nguyên đoạn log.

**Quy ước chung**

- Thực hiện tại thư mục project, python là `venv\Scripts\python` (hoặc đã activate venv — mọi lệnh dưới viết `python` cho gọn). Máy trắng: double-click **`run.bat`** tự build venv + deps + Chromium rồi mở GUI.
- Phần đăng ký lịch (schtasks) dùng **Command Prompt**, không phải PowerShell.
- Code đã ở origin (push đầy đủ) — checklist này chỉ bật dữ liệu/key phía bạn.

---

## Phần 1 — Khởi động sạch (0 request, 0 key, ~2 phút)

| # | Việc | Lệnh | Kết quả mong đợi | Nếu lỗi |
|---|---|---|---|---|
| 1.1 | CLI in guide đủ 10 nhóm | `python main.py` | Nhóm `── TRAFFIC ──` … `── NHIEU SITE ──` (T54) | Lỗi import → chạy `venv\Scripts\python main.py` thẳng |
| 1.2 | Doctor tổng quan | `python main.py --doctor` | Bảng ✓/! từng nhóm — **đi theo dấu ! từ trên xuống là lộ trình phần 2+** | Gửi log |
| 1.3 | Nguồn chưa có dữ liệu tự nói | `python main.py --aeo-report` / `--backlink-check` / `--rank-report` | Mỗi lệnh in "chưa có dữ liệu" + lệnh lấy — KHÔNG crash | Gửi log |
| 1.4 | GUI mở được | `python ui.py` (hoặc `run.bat`) | Cửa sổ CustomTkinter, tab 🧙 Cài Đặt Lần Đầu hiện bảng bước ✓/✗ | Thiếu customtkinter → dùng venv |

---

## Phần 2 — GSC thật (cần service account, xem docs/SETUP_GSC.md)

Điều kiện: `config/gsc_service_account.json` tồn tại, email service account đã được cấp quyền trên property, Search Console API đã bật. Chưa có → làm hết 5 bước trong **docs/SETUP_GSC.md** trước.

| # | Lệnh | Kết quả mong đợi | Nếu lỗi |
|---|---|---|---|
| 2.1 | `python main.py --gsc` | Lưu snapshot (rows + pages), in tổng clicks/impressions | **403** → email SA chưa vào property; **400** → `GSC_SITE_URL` sai format/trùng property |
| 2.2 | `python main.py --gsc-report` | Bảng từ khóa × clicks/impressions/vị trí/CTR + cột AI | Rỗng → property mới, chờ 2–3 ngày dữ liệu |
| 2.3 | `python main.py --html-report` | 13 section; **CTR cơ hội** và bảng trang GSC sống theo snapshot | Section GSC vẫn hint → chưa có snapshot, chạy 2.1 |
| 2.4 | `python main.py --export gsc` | CSV trong `reports/` mở bằng Excel tốt (UTF-8 BOM) | — |

Bật xong GSC: hàng loạt tính năng 0-request sống theo snapshot — `--page-impact`, `--content-gap`, `--ctr-ops`, `--cluster-gsc`, `--post-report`, SVG trend GSC trong report.

---

## Phần 3 — Rank check thật (~10 phút)

| # | Lệnh | Kết quả mong đợi | Nếu lỗi |
|---|---|---|---|
| 3.1 | `python main.py --rank` | Check từng từ khóa, lưu `rank_history.json` (cap 90 mốc — cũ nhất tự cắt); kw CAPTCHA bị bỏ qua (log ghi rõ) | Nhiều CAPTCHA liền → chạy bằng GUI (có ô hỏi người giải) |
| 3.2 | `python main.py --rank-report` | Bảng từ khóa có hạng thật + sparkline | Tất cả ">100" → kw quá mới hoặc `RANK_CHECK_DEPTH` cần đổi |
| 3.3 | Đối thủ + trend | `python main.py --competitors` | Bảng domain + khối THAY ĐỔI (T43); cần ≥ 2 lần check có top_urls | Rỗng → chạy thêm lần nữa |
| 3.4 | Chống spam | Chạy `--rank` lần 2 ngay | Bị chặn vì `RANK_CHECK_MIN_INTERVAL` (3600s mặc định) | Nếu KHÔNG bị chặn → lỗi rate limiter |

---

## Phần 4 — Telegram cảnh báo (theo docs/SETUP_ALERTS.md)

1. Tạo bot @BotFather → copy token; lấy chat id (bước 2 trong doc).
2. Điền `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` (khuyến nghị biến môi trường); set `ALERTS_ENABLE = True`.
3. `python main.py --daily-report` → tin 1 phần: XẾP HẠNG / SEARCH CONSOLE / **TREND** (T52 — PageSpeed + audit khi đủ 2 mốc) / VIỆC HÔM NAY; Telegram nhận tin.
4. `python main.py --weekly` → tin tuần (thêm AEO TREND + ĐỐI THỦ ĐANG LEO — T44), 1 lần/tuần.

**An toàn có sẵn**: token sai / Telegram sập → cảnh báo chỉ in console, flow chính KHÔNG chết.

---

## Phần 5 — Audit on-page + PageSpeed (F6)

| # | Lệnh | Kết quả mong đợi | Nếu lỗi |
|---|---|---|---|
| 5.1 | `python main.py --audit` | Báo cáo lỗi + severity + URL; lưu `audit_last.json` + **1 mốc `audit_history.json`** | Site lớn/trễ → `--audit-limit 20` cho lần đầu |
| 5.2 | `python main.py --audit-trend` | Từng loại lỗi qua các mốc — gảm là tốt (T41); chạy sau ≥ 2 lần audit | Rỗng → audit lần nữa |
| 5.3 | `python main.py --pagespeed` | LCP / CLS / INP + điểm mobile & desktop; lần đo ≥ 2 in dòng 📈 (T51) | **429** → tạo key miễn phí điền `PAGESPEED_API_KEY` (secret, đừng commit) |
| 5.4 | `python main.py --pagespeed-posts` | Bảng điểm từng bài đã push (job scheduler tự đo bài mới) | Rỗng → chạy `--run-job pagespeed` |

---

## Phần 6 — Backlink thật (F7) + Outreach (T32)

| # | Lệnh | Kết quả mong đợi | Nếu lỗi |
|---|---|---|---|
| 6.1 | Thêm link đã đặt | `python main.py --backlink-add "https://forum.vn/chude"` | URL không hợp lệ → exit 2 kèm thông báo rõ |
| 6.2 | `python main.py --backlink-check` | Mỗi link: còn sống / có link tới site / dofollow (+ anchor) | **403 / 429** → ghi "bị chặn", **KHÔNG retry/đổi UA** — lịch sự với host, không phải lỗi tool |
| 6.3 | Import GSC | tải CSV **External links** từ UI GSC (API không có endpoint này) → `--backlink-import path.csv` | CSV sai cột → thông báo chính xác dòng lỗi |
| 6.4 | Outreach | `--outreach-add URL --outreach-kw "anchor"` → `--outreach-list` (nhắc quá hạn) → `--export outreach` CSV cho VA | Tool CHỈ ghi sổ + nhắc — không tự liên hệ/email/crawl |

---

## Phần 7 — Ollama content (F8; cần máy đủ mạnh)

| # | Lệnh | Kết quả mong đợi | Nếu lỗi |
|---|---|---|---|
| 7.1 | Bật model | `ollama serve` + `ollama pull qwen3:30b-a3b` (~18 GB) | Máy 8 GB RAM không đủ 30b → đổi `CONTENT_MODEL` sang `qwen3:8b` / `llama3.1:8b` |
| 7.2 | Dry-run | `python main.py --generate "nối mi tự nhiên" --dry-run` | Chỉ in prompt, không tạo file |
| 7.3 | Chạy thật | `python main.py --generate "nối mi tự nhiên"` hoặc GUI tab 🤖 AI Engine → **SINH THEO NGÀY PLAN** (T48) | Draft lưu `content/drafts/` — bạn duyệt rồi `--wp-push` (CHI draft/pending, publish tay trên WordPress) |

---

## Phần 8 — Scheduler hằng ngày (F4/T20–T21, theo docs/SETUP_SCHEDULER.md)

1. `python main.py --scheduler-install` → copy lệnh `schtasks /Create` vào **Command Prompt (admin)** — tool chỉ IN, không tự đăng ký.
2. GUI tab 📈 Xếp Hạng → khung 🗓 LỊCH TỰ ĐỘNG → nút **🪟 TASK ĐÃ ĐĂNG KÝ?** (T49) → đợi `9/9` ✓.
3. `python main.py --scheduler-status` → job đến giờ + lịch sử 5 lần gần nhất.
4. `SCHEDULER_TRAFFIC_ENABLE` mặc định **TẮT** — bật là quyết định của bạn.

---

## Phần 9 — AEO hằng ngày (F9) + vòng duy trì

1. Hỏi ChatGPT/Gemini 1 câu theo từ khóa đang theo dõi → copy câu trả lời: GUI tab 📢 AI Nói Gì (dán vào khung, bấm PHÂN TÍCH & LƯU) hoặc `--aeo-check answer.txt --aeo-keyword "nối mi"`.
2. `python main.py --gsc-report` → cột AI cập nhật (✓1/1); `--aeo-report` chi tiết.
3. **5 phút/ngày**: nhìn TREND trong báo cáo sáng → làm VIỆC HÔM NAY → duyệt draft → `--wp-push`.

---

## Sau khi checklist xong

- Mọi lỗi gặp được ghi lại và gửi — chất lượng thật của tool được đánh giá ở đây, không ở unit test.
- Tính năng mới ngoài roadmap: đề xuất trước khi code (pattern hiện tại: mỗi tính năng 1 quick test riêng + 1 commit riêng + suite xanh + mojibake scan).
