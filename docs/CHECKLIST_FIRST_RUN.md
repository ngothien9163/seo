# Checklist "Bật nhà mới" — chạy thật từng tính năng lần đầu

> Mục đích: toàn bộ 10 tính năng đã code và xanh ~560 test **mock/offline**, nhưng chưa lần nào chạy trên dữ liệu thật. Checklist này bật từng tính năng theo thứ tự rẻ → đắt, mỗi bước có cách kiểm tra **kết quả mong đợi** và **nếu lỗi** rõ ràng. Làm theo thứ tự; đừng nhảy cóc.
>
> Lệnh nào in lỗi bạn không tự giải được → gửi nguyên đoạn log cho tôi (agent), đả sửa live.

**Quy ước chung**

- Thực hiện tại thư mục project (`D:\Projects\OpenSource\SEO\seo-by-Tung`), python là `venv\Scripts\python` (hoặc đã activate venv — mọi lệnh dưới viết `python` cho gọn).
- Phần đăng ký lịch (schtasks) dùng **Command Prompt**, không phải PowerShell.
- Phần cuối sẽ `git push` — nếu chưa sẵn sàng cho code ra origin, dừng trước phần đó.

---

## Phần 1 — Khởi động sạch (0 request, 0 key, ~2 phút)

| # | Việc | Lệnh | Kết quả mong đợi | Nếu lỗi |
|---|---|---|---|---|
| 1.1 | CLI in guide đầy đủ | `python main.py` | In bảng "Tính năng chính" + AUTOMATION, cuối có 2 dòng `--aeo-*` mới | Lỗi import → chạy `venv\Scripts\python main.py` thẳng |
| 1.2 | AEO lần đầu (chưa có dữ liệu) | `python main.py --aeo-report` | Bảng "Chưa có dữ liệu AEO" + hướng dẫn dán tay — KHÔNG crash | Gửi log |
| 1.3 | Backlink store rỗng | `python main.py --backlink-check` | Báo `config/backlinks.json` trống + hướng dẫn thêm link | Gửi log |
| 1.4 | GUI mở được | `python ui.py` | Cửa sổ CustomTkinter, tab mặc định, **không** tự chạy session nào | Thiếu customtkinter → dùng venv; lỗi khác → gửi log |

> Điểm này **chưa bật tự động gì** — chỉ xác nhận lối vào đúng.

---

## Phần 2 — GSC thật (F1/F2; cần service account, xem docs/SETUP_GSC.md)

Điều kiện: `config/gsc_service_account.json` tồn tại, email service account đã được cấp quyền trên property, Search Console API đã bật. Chưa có → làm hết 5 bước trong **docs/SETUP_GSC.md** trước.

| # | Lệnh | Kết quả mong đợi | Nếu lỗi |
|---|---|---|---|
| 2.1 | `python main.py --gsc` | Lưu snapshot `data/gsc_history.json`, in tổng clicks/impressions | **403** → email SA chưa vào property; **400** → `GSC_SITE_URL` sai format/trùng property |
| 2.2 | `python main.py --gsc-report` | Bảng từ khóa × clicks/impressions/vị trí/CTR thật | Rỗng → property mới, chờ 2–3 ngày dữ liệu |
| 2.3 | `python main.py --gsc-keywords` | Đề xuất query mới theo ngưỡng impressions | Không gợi ý gì → hạ `KEYWORD_SUGGEST_MIN_IMPRESSIONS` (VD 10) |
| 2.4 | `python main.py --export gsc` | CSV trong `reports/` mở bằng Excel tốt (UTF-8 BOM) | — |

---

## Phần 3 — Rank check thật (F2, ~10 phút)

| # | Lệnh | Kết quả mong đợi | Nếu lỗi |
|---|---|---|---|
| 3.1 | `python main.py --rank` | Check từng từ khóa, lưu `rank_history.json`; kw gặp CAPTCHA bị bỏ qua (log ghi rõ) | Nhiều CAPTCHA liền → chạy bằng GUI (có ô hỏi người giải) |
| 3.2 | `python main.py --rank-report` | Bảng từ khóa có hạng thật + sparkline | Tất cả ">100" → kw quá mới hoặc `RANK_CHECK_DEPTH` cần đổi |
| 3.3 | Chống spam | Chạy `--rank` lần 2 ngay → bị chặn vì `RANK_CHECK_MIN_INTERVAL` (3600s mặc định) | Nếu KHÔNG bị chặn → lỗi rate limiter, báo tôi |

---

## Phần 4 — Telegram cảnh báo (F3, ~5 phút, theo docs/SETUP_ALERTS.md)

1. Tạo bot @BotFather → copy token; lấy chat id (bước 2 trong doc).
2. Điền `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` (khuyến nghị biến môi trường — thấy trong doc); set `ALERTS_ENABLE = True`.
3. `python main.py --alerts` → in các cảnh báo lần check gần nhất; đồng thời Telegram nhận tin (nếu có dữ liệu tụt).
4. Chưa có cảnh báo nào → chỉ in console "không có cảnh báo" — đó là đúng.

**An toàn có sẵn**: token sai / Telegram sập → cảnh báo chỉ in ra console, flow chính (JSON state) KHÔNG chết — đã có unit test bảo đảm.

---

## Phần 5 — Audit on-page + PageSpeed (F6)

| # | Lệnh | Kết quả mong đợi | Nếu lỗi |
|---|---|---|---|
| 5.1 | `python main.py --audit` | Báo cáo lỗi + severity + URL; lưu `data/audit_last.json` | Site lớn/trễ → thêm `--audit-limit 20` cho lần đầu nhanh |
| 5.2 | `python main.py --export audit` | CSV`severity,rule,url,detail` mở bằng Excel tốt | — |
| 5.3 | `python main.py --pagespeed` | LCP / CLS / INP + điểm, mobile & desktop | **429 → hết quota ẩn danh PSI** — tạo key miễn phí rồi điền `PAGESPEED_API_KEY` (secret, đừng commit) |

---

## Phần 6 — Backlink thật (F7)

| # | Lệnh | Kết quả mong đợi | Nếu lỗi |
|---|---|---|---|
| 6.1 | Thêm link đã đặt | `python main.py --backlink-add "https://forum.vn/chude"` (hoặc thêm tay file) | URL không hợp lệ → exit 2 kèm thông báo rõ |
| 6.2 | `python main.py --backlink-check` | Mỗi link: còn sống / có link tới site / dofollow (+ anchor) | **403 / 429** → ghi "bị chặn", **KHÔNG retry/đổi UA** — lịch sự với host người khác, KHÔNG phải lỗi tool |
| 6.3 | Import GSC | tải CSV **External links** từ UI GSC (API không có endpoint này) → `--backlink-import path.csv` | CSV sai cột → thông báo chính xác dòng lỗi |

---

## Phần 7 — Ollama content (F8; cần máy đủ mạnh)

| # | Lệnh | Kết quả mong đợi | Nếu lỗi |
|---|---|---|---|
| 7.1 | Bật model | `ollama serve` + `ollama pull qwen3:30b-a3b` (~18 GB) | Máy 8 GB RAM không đủ 30b → đổi `CONTENT_MODEL` sang `qwen3:8b` / `llama3.1:8b` |
| 7.2 | Dry-run | `python main.py --generate "nối mi tự nhiên" --dry-run` | Chỉ in prompt, không tạo file; Ollama tắt vẫn được |
| 7.3 | Chạy thật | `python main.py --generate "nối mi tự nhiên"` | Draft lưu `content/drafts/<slug>-<ts>.md` — chạy 2 lần → 2 file khác nhau | Tool KHÔNG tự đăng (out-of-scope) — bạn duyệt rồi mới dùng |
| 7.4 | Ollama tắt | chạy 7.3 khi server chưa lên | Thông báo "chưa chạy Ollama tại <url>" + exit rõ ràng, không crash |

---

## Phần 8 — Multi-site thật (F10, rủi ro cao nhất — làm CUỐI)

An toàn: migration **CHỈ copy, không xoá** — vẫn nên backup `data/`, `rank_history.json`, `config/keywords.json` trước (một lệnh copy vào thư mục `_backup_pre_migrate/`).

| # | Lệnh | Kết quả mong đợi | Nếu lỗi |
|---|---|---|---|
| 8.1 | Dry-run | `python main.py --migrate-multi-site --dry-run` | In từng file sẽ copy + conflict; **không ghi gì** | Conflict → xem dòng, xử thủ công (file trùng nhưng khác nội dung) rồi chạy lại |
| 8.2 | Chạy thật | `python main.py --migrate-multi-site` | Copy xong + dấu `.migrated` → tool in "✅ Đã đóng dấu hoàn tất" | Lỗi khác → gửi log |
| 8.3 | Site khác chưa migrate | `python main.py --site tenmoi.com --rank-report` | Cảnh báo rõ "dữ liệu vẫn ở file phẳng" + chỉ dẫn migrate riêng | — |
| 8.4 | Tách site thứ 2 (chỉ khi có site thật) | `python main.py --site tenmoi.com --migrate-multi-site` (sau khi set `TARGET_URL` cho site đó hoặc dùng flag trên đúng) | `data/tenmoi-com/` có dữ liệu riêng, báo cáo gộp có prefix `tenmoi-com_` khi export CSV | — |

---

## Phần 9 — Scheduler hằng ngày (F4, theo docs/SETUP_SCHEDULER.md)

1. Đăng ký task Windows (`schtasks /Create`, 1 task/giờ theo doc).
2. `python main.py --scheduler-status` → hiển thị job mong muốn + lịch sử 5 lần gần nhất.
3. Chạy 1 lần thật: `python main.py --run-job rank` → logic rank chạy đúng + lock ra vào đúng đắn.
4. `SCHEDULER_TRAFFIC_ENABLE` mặc định **TẮT** — bật là quyết định của bạn (error âm thầm khi không ai nhìn).
5. `/scheduler-status` trả exit code 0 kèm trạng thái; muốn hủy task dùng `schtasks /Delete /TN <tên> /F`.

---

## Phần 10 — AEO hằng ngày (F9) + vòng duy trì

Có là 5 phút/ngày (hoặc tuần 3 lần tùy bảo):

1. Hỏi ChatGPT/Gemini 1 câu theo từ khóa đang theo dõi → copy toàn bộ câu trả lời vào file.
2. `python main.py --aeo-check answer.txt --aeo-keyword "nối mi" --aeo-engine ChatGPT`.
3. `python main.py --gsc-report` → cột AI cập nhật (✓1/1).

**Chưa dán lần nào** → cột AI vắng, báo cáo gộp không bị phá (không breaking).

---

## Sau khi checklist xong

- Tick từng dòng; mọi lỗi gặp được ghi lại và gửi — chất lượng thật của tool được đánh giá ở đây, không ở unit test.
- Việc kế tiếp: **push origin** (code đã commit đầy đủ nhưng chưa ra remote), rồi mới tính tính năng mới ngoài roadmap.
