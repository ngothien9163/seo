# Spec: GSC Client — Tích hợp Google Search Console API

- Ngày: 2026-10-04
- Trạng thái: Đã duyệt thiết kế (user chọn phương án A trong chat)
- Phân loại: Architectural (subsystem mới — nguồn dữ liệu Google API song song với Rank Tracker)

## 1. Mục tiêu & bối cảnh

Mục tiêu tổng của user: website **nankybeauty.com** lên top các từ khóa → tăng lượt truy cập → tăng bán hàng.

Rank Tracker (đã hoàn thành) lấy hạng từ SERP scraping, nhưng đang bị chặn thực tế vì IP máy user bị Google flag (`/sorry/` + reCAPTCHA). Google Search Console API là nguồn dữ liệu duy nhất **không scrape, không CAPTCHA, không phụ thuộc IP**, và là "sự thật" về hiệu quả SEO thực: clicks, impressions, vị trí trung bình, CTR theo từng query — dữ liệu mà scraping không bao giờ có.

**Tiêu chí thành công:**
1. Sau khi user làm xong hướng dẫn setup (`docs/SETUP_GSC.md`), chạy `python main.py --gsc` → nhận báo cáo gộp SERP + GSC.
2. GUI tab "📈 Xếp Hạng" lấy được dữ liệu GSC bằng 1 nút bấm.
3. Snapshot dữ liệu lưu `gsc_history.json`, giữ 90 ngày, mỗi ngày tối đa `GSC_MAX_FETCH_PER_DAY` lần fetch.
4. Thiếu credentials → thông báo tiếng Việt hướng dẫn rõ, không traceback khó hiểu.

## 2. Quyết định thiết kế đã duyệt

- **Phương án A — Service Account + `google-auth` + REST (`requests`)**: tạo service account trên Google Cloud Console, tải file JSON key, thêm email của service account làm user trong Search Console property (quyền Restricted là đủ). Token lấy bằng `google.oauth2.service_account.Credentials` với scope `webmasters.readonly`, tự refresh, không cần browser.
- Phương án B (OAuth Desktop) bị loại: refresh token chế độ "testing" hết hạn sau 7 ngày — không phù hợp tool chạy định kỳ.
- Phương án C (tự ký JWT bằng PyJWT) bị loại: thêm rủi ro crypto, không được lợi gì so với `google-auth`.
- **Giả định đã ghi nhận:** user có thể chưa verify property GSC → tính năng phải cung cấp hướng dẫn setup property từ đầu, và trạng thái "chưa setup" phải là lỗi thân thiện chứ không phải crash.

## 3. Kiến trúc & thành phần

### 3.1. `utils/gsc_client.py` (file mới — thành phần chính)

Một nhiệm vụ: nói chuyện với Search Console API + lưu dữ liệu + dựng báo cáo gộp. Đồng bộ (requests), không dùng Playwright.

Public API:

| Hàm | Chức năng |
|---|---|
| `load_credentials()` | Đọc `config/gsc_service_account.json` → `service_account.Credentials` với scope readonly. Thiếu file → raise `GSCSetupError` với thông điệp hướng dẫn. |
| `fetch_search_analytics(days=None)` | Lấy token, POST `searchAnalytics/query` với `startDate = today - (days-1)`, `endDate = today`. Trả `{query: {clicks, impressions, position, ctr}}`. |
| `parse_api_response(payload)` | Hàm thuần chuyển JSON response của API thành dict trên (tách riêng để unit test không cần network). |
| `can_run_fetch()` / `mark_fetch_run()` | Rate limit riêng cho GSC (state lưu trong `gsc_history.json`), cùng pattern với `rank_tracker.can_run_check`. |
| `save_snapshot(rows, start_date, end_date)` | Ghi snapshot ngày hôm nay vào `gsc_history.json`, prune quá 90 ngày. |
| `build_report()` | Báo cáo gộp (mục 4). |
| `print_report()` | In báo cáo. |
| `run_gsc_fetch_cli()` | Entry CLI: check rate limit → fetch → save → print report. |

Chi tiết API call:
- Endpoint: `POST https://searchconsole.googleapis.com/webmasters/v3/sites/{siteUrl}/searchAnalytics/query` với `siteUrl` URL-encode (ví dụ `sc-domain%3Anankybeauty.com`).
- Body: `{"startDate": "...", "endDate": "...", "dimensions": ["query"], "rowLimit": 250, "dataState": "all"}` — `dataState: "all"` để lấy cả dữ liệu mới chưa finalize (GSC thường trễ 2–3 ngày ở chế độ final).
- Scope: `https://www.googleapis.com/auth/webmasters.readonly`.
- Timeout 30s. Không retry tự động khi lỗi API (trừ 401 do token hết hạn → refresh 1 lần rồi thử lại).

### 3.2. Schema `gsc_history.json` (gitignored)

```json
{
  "site": "sc-domain:nankybeauty.com",
  "snapshots": {
    "2026-10-04": {
      "fetched_at": "2026-10-04T21:05:33",
      "start_date": "2026-09-07",
      "end_date": "2026-10-04",
      "rows": {
        "noi mi quan 2": {"clicks": 3, "impressions": 154, "position": 18.7, "ctr": 0.019}
      }
    }
  },
  "state": {"date": "", "count": 0, "last_fetch": 0}
}
```

Ghi đè snapshot cùng ngày (fetch nhiều lần/ngày chỉ giữ bản cuối). Giữ tối đa 90 ngày. Ghi đọc UTF-8, `ensure_ascii=False` (cùng chuẩn với `rank_history.json`).

### 3.3. `config/settings.py` — thêm PHẦN E

```python
# PHẦN E: GOOGLE SEARCH CONSOLE — dữ liệu SEO thật qua API (không scrape)
GSC_SITE_URL = "sc-domain:nankybeauty.com"   # property URL (sc-domain: hoặc https://...)
GSC_CREDENTIALS_FILE = "config/gsc_service_account.json"  # path JSON key, resolve từ thư mục gốc project
GSC_LOOKBACK_DAYS = 28        # Lấy dữ liệu 28 ngày gần nhất
GSC_MAX_FETCH_PER_DAY = 4     # Số lần fetch tối đa mỗi ngày (quota API là 1200/phút — giới hạn này chỉ để tránh gọi thừa)
```

### 3.4. Điểm vào

- `main.py`: `--gsc` (fetch + báo cáo), `--gsc-report` (chỉ xem báo cáo đã lưu) + 2 dòng help trong `show_strategy()`.
- `ui.py`: trong tab "📈 Xếp Hạng" thêm nút "📊 Lấy Dữ Liệu Search Console" + ghi kết quả vào `txt_rank`. Worker là `threading.Thread` thuần (requests chặn, không cần event loop); vô hiệu nút khi đang chạy hoặc traffic bot đang chạy; cập nhật UI qua `self.after(0, ...)`.
- `requirements.txt`: thêm `google-auth`.

### 3.5. `.gitignore`

Thêm `gsc_history.json` và `config/gsc_service_account.json`.

## 4. Báo cáo gộp (data flow)

`build_report()` nối dữ liệu **GSC 28 ngày gần nhất** (snapshot mới nhất) với **lần check SERP mới nhất** trong `rank_history.json`:

1. Chuẩn hóa query GSC và từ khóa cấu hình: lowercase, gộp khoảng trắng. Match exact trước; sau đó match "chứa": query chứa keyword hoặc keyword chứa query (GSC trả về query thật người dùng gõ — thường là biến thể của từ khóa cấu hình, ví dụ "nối mi quận 2 giá" khớp "nối mi quận 2"). Một query chỉ khớp đúng MỘT keyword (exact ưu tiên, sau đó chứa ngắn nhất).
2. Bảng chính (mỗi từ khóa trong `cfg.SEO_KEYWORDS`):

```
Từ khóa                  Hạng SERP  Δ   Xu hướng   Clicks  Hiện  Vị trí TB  CTR
nối mi quận 2                 12   ↑2   ▅▆▇█           5    210       14.3  2.4%
```
   — Cột Hạng SERP/Δ/xu hướng tái dùng logic của `rank_tracker`: đổi tên `_sparkline`/`_delta_str` thành public `sparkline`/`delta_str` trong `utils/rank_tracker.py` (giữ nguyên logic) và import sang; nếu chưa có rank history thì hiển thị "—".
3. Mục "Query mới phát hiện": query GSC có impressions mà không khớp từ khóa nào — top 15 theo impressions. Đây là dữ liệu đầu vào cho task keyword research tự động (roadmap #4).
4. Footer: tổng clicks/impressions toàn property trong khoảng thời gian, ngày bắt đầu/kết thúc dữ liệu thực tế (ghi rõ dữ liệu GSC có thể trễ 2–3 ngày).
5. Trường hợp thiếu một phía dữ liệu: chỉ có GSC → bảng GSC với cột SERP "—"; chỉ có rank history → báo cáo rank như hiện tại + dòng ghi chú "chưa có dữ liệu Search Console".

## 5. Xử lý lỗi (thông điệp tiếng Việt)

| Tình huống | Hành vi |
|---|---|
| Thiếu file `config/gsc_service_account.json` | In hướng dẫn ngắn + trỏ tới `docs/SETUP_GSC.md`. CLI exit code 1; GUI messagebox. |
| HTTP 403 PERMISSION_DENIED | "Email service account chưa được thêm vào Search Console property (quyền Restricted là đủ) — xem docs/SETUP_GSC.md bước 5." |
| HTTP 400 | Gợi ý kiểm tra `GSC_SITE_URL` (định dạng `sc-domain:...` hoặc `https://...` trùng với property đã verify). |
| HTTP 429 | Thông báo chờ quota, không retry tự động. |
| Lỗi mạng | Giữ snapshot cũ; báo cáo ghi rõ mốc thời gian dữ liệu đang hiển thị. |
| Property chưa có dữ liệu (mới verify) | Empty state thân thiện: "GSC chưa có dữ liệu — property mới cần chờ vài ngày để tích lũy." |

## 6. Bảo mật

- `config/gsc_service_account.json` và `gsc_history.json` nằm trong `.gitignore`, không bao giờ in nội dung key ra log.
- Scope chỉ-đọc (`webmasters.readonly`) — service account không thể sửa gì trong property.
- Token chỉ nằm trong bộ nhớ trong quá trình chạy; chỉ gọi `googleapis.com`.

## 7. Testing

1. `_quick_gsc_test.py` (gitignored, pattern `_quick_test.py` của Rank Tracker): tạo fake `gsc_history.json` + fake `rank_history.json` → assert bảng gộp, matching query↔keyword, các empty state, pruning 90 ngày, rate limit; xóa file test sau khi xong.
2. Unit test `parse_api_response` với payload giả (không cần network).
3. `py_compile` tất cả file touched.
4. Live smoke `--gsc`: chỉ chạy được sau khi user setup credentials (bước này nằm ngoài scope code — ghi trong SETUP_GSC.md là bước kiểm tra cuối).
5. GUI: `customtkinter` chưa cài trong môi trường dev → chỉ verify `py_compile` + logic, không launch UI được trong env này.

## 8. Tài liệu

- `docs/SETUP_GSC.md` (mới): hướng dẫn từng bước tiếng Việt — (1) verify property trong Search Console, (2) tạo project Google Cloud Console, (3) bật Search Console API, (4) tạo service account + tải JSON key, (5) thêm email service account vào property (quyền Restricted), (6) đặt file key vào `config/gsc_service_account.json`, (7) chạy `python main.py --gsc`, (8) bảng lỗi thường gặp.
- `README.md`: section tính năng mới, dòng CLI `--gsc`/`--gsc-report`, dòng config PHẦN E, cập nhật cây cấu trúc.

## 9. Rủi ro & giới hạn đã cân nhắc

- User chưa verify property → không chặn code/test; chỉ chặn bước chạy thật.
- Query dưới ngưỡng privacy của Google (site nhỏ, ít impressions) có thể bị ẩn trong dataState final — dùng `dataState: "all"` để giảm tối đa hiện tượng này.
- Không sửa lỗi mojibake có sẵn trong các file cũ (task tech debt riêng, roadmap #9); các phần code mới viết UTF-8 chuẩn.
- Không làm trong đợt này (YAGNI): OAuth, multi-property, keyword research tự động, SQLite, scheduler.
