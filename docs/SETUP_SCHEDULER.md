# Đặt lịch tự chạy trên Windows (F4)

Code **không tự thức dậy**. Đồng hồ thật là **Windows Task Scheduler**: nó gọi

```bat
python main.py --run-job rank
```

đúng giờ, còn `utils/scheduler.py` chỉ quyết định "giờ này có được chạy không" (dùng lại
giới hạn sẵn có của từng module), chặn hai job chồng nhau, và ghi dấu vết vào
`data/scheduler_state.json` để `python main.py --scheduler-status` hoặc khung
**🗓 LỊCH TỰ ĐỘNG** trong tab Xếp Hạng đọc lại.

---

## 1. Điều kiện để lịch chạy được

| Điều kiện | Nếu không |
|---|---|
| Máy **bật đúng giờ** và đang đăng nhập user của bạn | Task không chạy, **không chạy bù** (quyết định đã duyệt: gom nhiều lần check một lúc = pattern bất thường gửi lên Google). |
| `venv\Scripts\python.exe` tồn tại trong thư mục project | Job chết ngay, log chỉ có dòng "not recognized". |
| Playwright + Chromium đã cài (`playwright install chromium`) | Job `rank` báo lỗi trong log, exit 1. |
| Traffic: `SCHEDULER_TRAFFIC_ENABLE = True` trong `config/settings.py` | `--run-job traffic` in "đang TẮT theo quyết định của owner" rồi exit 0 — **mặc định là TẮT**, bật lên là quyết định của bạn. |

## 2. Đăng ký task (Command Prompt, không cần PowerShell)

**Lãi nhanh: `python main.py --scheduler-install`** in sẵn toàn bộ lệnh `schtasks /Create`
theo giờ trong `config/settings.py` (`SCHEDULER_*_HOURS`) — không tự đăng ký gì, copy dán là xong.
Các lệnh mẫu dưới đây resolve tay khi muốn hiểu cú pháp.

Thay `D:\Projects\OpenSource\SEO\seo-by-Tung` bằng đường dẫn thật nếu bạn đặt project ở chỗ khác.
Mỗi task một giờ, vì `schtasks /Create` chỉ nhận một `/ST` (định dạng `HH:mm` 24h).
Log ghi dồn vào `data\scheduler.log` để xem được lúc job chạy khi không có ai ngồi máy.

```bat
schtasks /Create /F /TN "SEO-Bot-Rank-0700" /SC DAILY /ST 07:00 /RL LIMITED ^
  /TR "cmd /c cd /d D:\Projects\OpenSource\SEO\seo-by-Tung && venv\Scripts\python.exe main.py --run-job rank >> data\scheduler.log 2>&1"

schtasks /Create /F /TN "SEO-Bot-Rank-1300" /SC DAILY /ST 13:00 /RL LIMITED ^
  /TR "cmd /c cd /d D:\Projects\OpenSource\SEO\seo-by-Tung && venv\Scripts\python.exe main.py --run-job rank >> data\scheduler.log 2>&1"

schtasks /Create /F /TN "SEO-Bot-Rank-1900" /SC DAILY /ST 19:00 /RL LIMITED ^
  /TR "cmd /c cd /d D:\Projects\OpenSource\SEO\seo-by-Tung && venv\Scripts\python.exe main.py --run-job rank >> data\scheduler.log 2>&1"

schtasks /Create /F /TN "SEO-Bot-GSC-0900" /SC DAILY /ST 09:00 /RL LIMITED ^
  /TR "cmd /c cd /d D:\Projects\OpenSource\SEO\seo-by-Tung && venv\Scripts\python.exe main.py --run-job gsc >> data\scheduler.log 2>&1"
```

`/F` = ghi đè task trùng tên, chạy lại lệnh này khi muốn đổi giờ là được.

### Job airobots (T26) — 1 lần/tuần, chỉ chạy thứ Hai

Job `airobots` đọc robots.txt site (1 request, **chỉ báo cáo** — không tự sửa gì),
kết quả lưu `ai_robots_last.json` → section Bot AI trong report.html luôn tươi.
`SCHEDULER_AIROBOTS_WEEKLY = True` (mặc định) → task đăng ký `/SC DAILY` nhưng
**chỉ chạy đúng thứ Hai**, ngày khác in dòng giải thích rồi thoát (không tốn request).
Muốn hằng ngày: đặt `False`. Giờ: `SCHEDULER_AIROBOTS_HOURS = [7]`.

```bat
schtasks /Create /F /TN "SEO-Bot-Airobots-0700" /SC DAILY /ST 07:00 /RL LIMITED ^
  /TR "cmd /c cd /d D:\Projects\OpenSource\SEO\seo-by-Tung && venv\Scripts\python.exe main.py --run-job airobots >> data\scheduler.log 2>&1"
```

**Tùy chọn — máy hay bật muộn:** thêm task bắt kịp khi đăng nhập. `RANK_CHECK_MIN_INTERVAL` chặn nếu vừa check xong, nên task này không gây check dồn:

```bat
schtasks /Create /F /TN "SEO-Bot-Logon" /SC ONLOGON /RL LIMITED ^
  /TR "cmd /c cd /d D:\Projects\OpenSource\SEO\seo-by-Tung && venv\Scripts\python.exe main.py --run-job rank >> data\scheduler.log 2>&1"
```

### Job pagespeed (T33) — PageSpeed cho bài vừa push

Job `pagespeed` đo **PageSpeed Insights** (so LAB mobile) cho bài nào trong
`wp_pushed.json` **chưa có điểm** — **1 request/URL trọn đời**: đo xong ghi key
`data/pagespeed_posts.json`, các lần chạy sau là 0 request. Mỗi đợt tối đa
`PAGESPEED_MAX_PER_RUN` (5) URL vì Lighthouse mất chục giây/URL; PSI 429 giữa
đợt thì job dừng nguyên đợt (URL chưa ghi — lần chạy kế tự thử lại). Bài điểm
< `PAGESPEED_WARN_SCORE` (60) được nhắc về sửa rồi đo lại, qua dòng trong báo
cáo ngày. Giờ: `SCHEDULER_PAGESPEED_HOURS = [6]`.

```bat
schtasks /Create /F /TN "SEO-Bot-Pagespeed-0600" /SC DAILY /ST 06:00 /RL LIMITED ^
  /TR "cmd /c cd /d D:\Projects\OpenSource\SEO\seo-by-Tung && venv\Scripts\python.exe main.py --run-job pagespeed >> data\scheduler.log 2>&1"
```

## 3. Đổi giờ thì đổi ở đâu?

**Trên Windows, không phải trong settings.** `SCHEDULER_RANK_HOURS = [7, 13, 19]` và
`SCHEDULER_GSC_HOURS = [9]` trong `config/settings.py` chỉ là **lịch mong muốn**: chúng
quyết định dòng in ra khi bạn chạy `--scheduler-status` / `--run-job saymax`, và là gợi ý
để gõ lệnh ở mục 2. Sửa hai list đó **không** làm Windows đổi giờ — phải tạo lại task
(`/Create /F` với `/ST` mới, và `/Delete` task cũ).

## 4. Kiểm tra

```bat
schtasks /Query /TN "SEO-Bot-Rank-0700" /V /FO LIST   (xem Next Run Time, Last Task Result)
schtasks /Run   /TN "SEO-Bot-Rank-0700"               (chạy ngay lập tức, không chờ đúng giờ)
schtasks /Delete /TN "SEO-Bot-Rank-0700" /F           (gỡ bỏ)
```

```bat
cd /d D:\Projects\OpenSource\SEO\seo-by-Tung
venv\Scripts\python.exe main.py --scheduler-status
type data\scheduler.log
```

`--scheduler-status` in từng job: giờ mong muốn, lần chạy cuối, `ok`/`error`, exit code,
dòng lỗi cuối và 5 lần chạy gần nhất. Chạy thử một job cụ thể thì dùng CLI
`--run-job rank` (GUI cố ý **không** có nút chạy job: chạy tay từ GUI thì log không nằm ở
Task Scheduler, và giờ đó chưa chắc đã tới lượt).

## 5. Lịch hay gặp

- **`ERROR: Access is denied.`** — mở Command Prompt kiểu *Run as administrator* rồi chạy lại `/Create`.
- **Task hiện `Last Task Result = 0x1`** — job chạy nhưng fail; mở `data\scheduler.log` xem dòng `[GSC]`/`[Rank]`/`[Scheduler]` in ra gì (thiếu credentials là lỗi hay gặp nhất — xem `docs/SETUP_GSC.md`).
- **Task không bao giờ chạy** — máy ngủ: Control Panel → Power Options, hoặc trong Task Scheduler tick *Wake the computer to run this task* ở tab Conditions.
- **Muốn chạy khi chưa đăng nhập** — các lệnh trên tạo task kiểu "chạy khi user đăng nhập". Muốn chạy nền thật sự thì mở Task Scheduler GUI, chọn *Run whether user is logged on or not* (cần nhập mật khẩu) — CLI `/RU`/`/RP` làm được nhưng dễ sai, nên cứ dùng GUI.
- **Đường dẫn có dấu cách** — nhớ bọc nháy kép cho cả cụm `cd /d ...`, và toàn bộ giá trị `/TR` nằm trong một cặp nháy kép.

## 6. Giới hạn

- Các lệnh ở trên được viết theo `schtasks /Create /?` của Windows (đã kiểm tra cờ hợp lệ), nhưng **chưa đăng ký thật** trên máy này — việc tạo task thuộc về owner; làm hộ sẽ sửa đổi lịch của máy bạn.
- Lock chống chồng job chỉ hoạt động trong **một máy / một bản checkout** (file `data/scheduler.lock`), hai bản song song không thấy nhau.
- `data/scheduler_state.json` giữ tối đa 50 lần chạy; `data/scheduler.log` chỉ được nối thêm (qua `>>`) nên tự lớn dần — xóa thủ công khi cần.
