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
python main.py --indexnow            # URLs tốt (sitemap từ audit + rank history)
python main.py --indexnow --dry-run  # xem sẽ submit gì — không gọi mạng
python main.py --indexnow URL1 URL2  # chỉ định URL, URL nào cũng submit
```
→ HTTP 200 = engine nhận; **202** = đã nhận nhưng đang verify key file (bình
thường ở lần đầu nếu file chưa được treo đúng — check: truy cập
`https://<site-of-yours>/<tên file>.txt` bằng browser phải thấy đúng key).

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
