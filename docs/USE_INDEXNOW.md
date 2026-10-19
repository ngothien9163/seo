# IndexNow — đẩy URL mới vào Bing/Yandex/Seznam/Naver (T18)

> Mục tiêu: khi đăng bài / sửa bài → nói cho các engine tìm kiếm ngoài Google biết
> liền, đừng đợi crawler tự lướt tới. IndexNow là tiêu chuẩn mở (Bing, Yandex,
> Seznam, Naver đều nhận — engine nào nhận thì tự share cho các engine còn lại).

## Vì sao chọn IndexNow mà không dùng Bing API key?

- IndexNow **không cần OAuth, không cần key của bên thứ ba**: key 32 ký tự mình
  tự sinh, chỉ cần treo 1 file text lên site để engine verify quyền sở hữu.
- Không thêm dependency — chỉ `requests` vốn có.
- Là tiêu chuẩn mở được indexnow.org cấp API endpoint `https://api.indexnow.org/indexnow`.

## Bật lần đầu — 3 bước (~10 phút)

### 1. Sinh key
```
python main.py --indexnow-key
```
→ Lệnh in key + lưu vào `data/indexnow_key.txt` (per-site khi multi-site).

### 2. Treo file lên site (một lần duy nhất)
Cách 1 — SFTP/cPanel: tải file `indexnow_key.txt` lên **gốc site**
(`public_html/`), đổi tên thành `indexnow-key.txt`, nội dung giữ nguyên là key.
Cách 2 — WordPress Admin: Media → Add New → upload file → key nằm dưới
`/wp-content/uploads/` (tốt, đúng chuẩn — file nào trên cùng host cũng được,
chỉ cần ngay dưới đó có chứa key).

### 3. Submit
```
python main.py --indexnow            # T24: tự đọc sitemap của site, chỉ submit URL MỚI
python main.py --indexnow --dry-run  # xem sẽ submit gì — không gọi mạng
python main.py --indexnow --indexnow-full   # đẩy lại toàn bộ sitemap (không lọc URL mới)
python main.py --indexnow URL1 URL2  # chỉ định URL, URL nào cũng submit
```
→ HTTP 200 = engine nhận; **202** = đã nhận nhưng đang verify key file (bình
thường ở lần đầu nếu file chưa được treo đúng — check: truy cập
`https://<site-of-yours>/<tên file>.txt` bằng browser phải thấy đúng key).

## URL mới từ sitemap (T24)

`--indexnow` **không chỉ định URL** giờ tự GET `robots.txt` (1 request):
- robots khai `Sitemap:` → đọc đúng file đó; khai nhiều → tối đa 3 file đầu.
- Không khai → thử `/sitemap.xml`.
- File là `<sitemapindex>` → đọc tối đa 10 file con (1 request mỗi file).
- Chỉ nhận `<loc>` cùng host + robots cho phép (cùng luật với audit).

Sau đó đóng với tập URL **đã biết**: lần submit trước (state `known` trong
`indexnow_state.json`) + audit gần nhất + rank history + trang chủ → chỉ URL
MỚI được submit; submit thành công tự nhớ vào `known`. Không có URL mới →
in dòng rõ ràng, không submit gì (đừng ngại chạy lại trong ngày).

Sitemap lỗi / rỗng → tự rơi về nguồn cũ của T18 (audit crawl + rank history +
trang chủ). Chỉ định URL tay → hành vi T18 nguyên vẹn, không đụng sitemap.

## Chống spam

- **1 lần/ngày** mặc định, state `data/indexnow_state.json`. Chạy lại trong
  ngày → chỉ in nhắc. Muốn submit lại ngay: `--force`.
- **Đánh dấu CHỈ KHI submit thành công** — mạng chết → lần chạy kế tự thử lại.
- Chỉ submit **URL cùng host của site** — URL lạ bị loại trước.

## Những gì indexnow KHÔNG làm

- Không tự up file key lên site của bạn (config WP/FTP là việc của bạn).
- Không đăng kí Bing WMT (vẫn nên tạo tài khoản Bing Webmaster để xem index
  coverage — chỉ là không dùng chung API key đó).
- HTTP 200/202 chỉ có nghĩa engine đã NHẬN, không có nghĩa đã index —
  việc index do engine quyết (xem coverage ở Bing WMT dashboard).

## Malfunction / lỗi thường gặp

| HTTP | Ý nghĩa | Sửa |
|------|---------|-----|
| 400  | Sai định dạng | kiểm tra key hex + URL hợp lệ |
| 403  | Key chưa hợp lệ | file key chưa lên site, hoặc nội dung file sai |
| 422  | URL không thuộc host | URL phải cùng domain với key file |
| 429  | Too Many Requests | spam guard — hôm mai thử lại |
