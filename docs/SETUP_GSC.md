# Hướng dẫn Setup Google Search Console cho SEO Bot

Tính năng này lấy dữ liệu SEO **thật** (clicks, impressions, vị trí trung bình, CTR) từ Google Search Console API — không scrape Google, không bao giờ gặp CAPTCHA, không phụ thuộc IP.

Thời gian làm: **~10 phút**, làm 1 lần duy nhất.

---

## Bước 1: Verify website trong Search Console (bỏ qua nếu đã làm)

1. Mở [search.google.com/search-console](https://search.google.com/search-console) bằng tài khoản Google của bạn.
2. Thêm property cho `nankybeauty.com`:
   - **Khuyên dùng: Domain property** (`nankybeauty.com`) — phủ cả subdomain và http/https.
   - Verify bằng bản ghi DNS TXT tại nơi quản lý tên miền (GoDaddy, Namecheap, Mật Nguyễn...).
3. Nếu dùng **URL prefix** (`https://nankybeauty.com/`) — verify bằng file HTML hoặc thẻ meta.

> ✅ Kiểm tra: mở Search Console, chọn property, thấy báo hiệu "Đã xác minh quyền sở hữu".

## Bước 2: Tạo project trên Google Cloud Console

1. Mở [console.cloud.google.com](https://console.cloud.google.com).
2. Góc trên trái → **Select a project** → **New Project**.
3. Đặt tên bất kỳ (ví dụ `seo-tools`) → **Create**.

## Bước 3: Bật Search Console API

1. Vào menu → **APIs & Services** → **Library**.
2. Tìm **Google Search Console API** → mở ra → **Enable**.

> Nếu bỏ bước này, khi chạy tool sẽ gặp lỗi **403 PERMISSION_DENIED**.

## Bước 4: Tạo Service Account + tải JSON key

1. Vào **APIs & Services** → **Credentials** → **Create Credentials** → **Service account**.
2. Đặt tên (ví dụ `seo-gsc-reader`) → **Create and Continue** (bước 2, 3 có thể bỏ qua — **Done**).
3. Nhấn vào service account vừa tạo → tab **Keys** → **Add Key** → **Create new key** → chọn **JSON** → **Create**.
4. File JSON tải về (dạng `seo-gsc-reader-xxxx.json`) — giữ an toàn, giống mật khẩu.

## Bước 5: Cấp quyền cho service account trong Search Console

1. Mở file JSON vừa tải, tìm dòng `"client_email"` — copy địa chỉ dạng:
   `seo-gsc-reader@seo-tools.iam.gserviceaccount.com`
2. Mở [Search Console](https://search.google.com/search-console) → chọn property → **Cài đặt (Settings)** → **Người dùng (Users and permissions)** → **Thêm người dùng (Add user)**.
3. Dán email service account vào, quyền chọn **Hạn chế (Restricted)** — đủ để xem dữ liệu → **Add**.

## Bước 6: Đặt file key vào đúng chỗ trong project

1. Đổi tên file JSON tải về thành `gsc_service_account.json`.
2. Copy vào thư mục `config/` của project:

```
seo-by-Tung/
└── config/
    └── gsc_service_account.json   ← file key ở đây
```

> 🔒 File này đã nằm trong `.gitignore` — không bao giờ bị commit lên git.

## Bước 7: Chạy thử

```bash
python main.py --gsc
```

Kết quả mong đợi: tool in số query nhận được rồi in **báo cáo gộp** — mỗi từ khóa hiển thị hạng SERP (từ Rank Tracker) cạnh clicks/impressions/vị trí TB/CTR (từ Google).

Xem lại báo cáo đã lưu mà không fetch lại:

```bash
python main.py --gsc-report
```

Trong GUI: tab **📈 Xếp Hạng** → nút **📊 LẤY DỮ LIỆU SEARCH CONSOLE**.

> ⏳ Property mới verify hoặc website ít traffic: Google cần vài ngày để tích lũy dữ liệu — báo cáo sẽ hiện "chưa có dữ liệu", không phải lỗi.

## Bước 8: Lỗi thường gặp

| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `Lỗi 403 PERMISSION_DENIED` | Chưa thêm email service account vào property, hoặc chưa bật API | Làm lại **bước 3** và **bước 5**, chờ ~5 phút cho quyền có hiệu lực |
| `Lỗi 400 BAD_REQUEST` | `GSC_SITE_URL` không khớp property | Mở `config/settings.py`, sửa `GSC_SITE_URL` đúng dạng property đã verify: Domain property → `sc-domain:nankybeauty.com`; URL prefix → `https://nankybeauty.com/` |
| `Lỗi 429` | Hết quota API | Chờ vài phút. Tool tự giới hạn 4 lần fetch/ngày nên rất khó đụng trần |
| `Chưa có credentials` khi chạy | Thiếu file key | Làm lại **bước 4** và **bước 6** |
| `File credentials ... lỗi` | File key sai/sai định dạng | Tải lại key mới ở **bước 4**, thay file cũ |
| Báo cáo "chưa có dữ liệu" | Property mới, Google chưa tổng hợp | Chờ 2–3 ngày rồi chạy lại |

---

### Cấu hình liên quan (`config/settings.py` — PHẦN E)

| Hằng số | Mặc định | Ý nghĩa |
|---|---|---|
| `GSC_SITE_URL` | `sc-domain:nankybeauty.com` | Property lấy dữ liệu |
| `GSC_CREDENTIALS_FILE` | `config/gsc_service_account.json` | Đường dẫn file key |
| `GSC_LOOKBACK_DAYS` | `28` | Lấy dữ liệu bao nhiêu ngày gần nhất |
| `GSC_MAX_FETCH_PER_DAY` | `4` | Giới hạn số lần fetch mỗi ngày (dữ liệu được lưu lại, xem lại bằng `--gsc-report`) |
