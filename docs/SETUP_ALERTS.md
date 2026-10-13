# Hướng dẫn Setup cảnh báo tụt hạng (Telegram)

Tính năng F3: khi một từ khóa **rơi ≥ 5 hạng** so với lần check liền trước, hoặc **rớt khỏi Top 10** — bot gửi cho bạn 1 tin Telegram. Mỗi từ khóa tối đa **1 tin/ngày**, dù bạn check 3 lần.

Thời gian làm: **~5 phút**, làm 1 lần duy nhất.

---

## Bước 1: Tạo bot qua @BotFather

1. Mở Telegram → tìm **@BotFather** (có tích xanh chính chủ).
2. Gửi lệnh `/newbot`.
3. Đặt tên hiển thị (vd: `SEO Rank Alert`), rồi đặt **username** kết thúc bằng `bot` (vd: `nankybeauty_rank_bot`).
4. BotFather trả về một dòng dạng:

   ```
   http://api.telegram.org/bot123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/token
   ```

   Chuỗi `123456789:AAHxxxx...` chính là **TELEGRAM_BOT_TOKEN**.

> ⚠️ Token là mật khẩu. Đừng gửi vào nhóm chat, đừng paste vào screenshot, và **không commit** lên repo công khai.

## Bước 2: Lấy chat id của bạn

1. Mở bot vừa tạo (đồng ý `/start` nếu bot hỏi).
2. Gửi cho bot một tin bất kỳ, ví dụ `hello`.
3. Mở đường dẫn dưới bằng trình duyệt (thay `TOKEN` bằng token ở Bước 1):

   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```

4. Trong JSON trả về, tìm `"chat":{"id":987654321,...}` → số đó là **TELEGRAM_CHAT_ID** (số cá nhân thường dương; nhóm thường âm, vd `-1001234567890`).

## Bước 3: Điền cấu hình

Cách **an toàn nhất** (không đụng file được git theo dõi) — đặt biến môi trường:

```powershell
# PowerShell
setx TELEGRAM_BOT_TOKEN "123456789:AAHxxxx..."
setx TELEGRAM_CHAT_ID "987654321"
```

```bash
# Git Bash / Linux / macOS
export TELEGRAM_BOT_TOKEN="123456789:AAHxxxx..."
export TELEGRAM_CHAT_ID="987654321"
```

Hoặc sửa `config/settings.py` (PHẦN F) — chỉ nên làm nếu repo của bạn là **private**:

```python
ALERTS_ENABLE = True            # Bật = gửi thật; Tắt = chỉ in ra console
RANK_ALERT_DROP = 5             # Rơi >= N hạng thì báo
RANK_ALERT_TOP10_FALL = True    # Rớt khỏi Top 10 thì báo
TELEGRAM_BOT_TOKEN = "123456789:AAHxxxx..."
TELEGRAM_CHAT_ID = "987654321"
```

Biến môi trường luôn **thắng** giá trị trong `settings.py`.

## Bước 4: Kiểm tra

```bash
python main.py --alerts
```

- Dòng `Kênh giao hàng: telegram` = đã cấu hình đúng.
- Dòng `Kênh giao hàng: console` = chưa bật `ALERTS_ENABLE` hoặc thiếu token/chat id; tin sẽ chỉ in ra console.
- Nếu in `⚠️ Telegram từ chối (Bad Request: chat not found)` → chat id sai (chưa `/start` với bot, hoặc copy thiếu dấu `-` với nhóm).

Nút **🧪 GỬI THỬ BÁO ĐỘNG** trong tab **📈 Xếp Hạng** (GUI) gửi một tin test để bạn xác nhận tin đến điện thoại.

## Bước 5: Để cảnh báo chạy tự động

Cảnh báo được evaluate **tự động ngay sau mỗi lần rank check** (`python main.py --rank`) và sau mỗi lần fetch Search Console — bạn không phải chạy thêm lệnh nào. Muốn check định kỳ mà không ngồi bấm, xem tính năng **F4 — Scheduler** trong `docs/superpowers/plans/2026-10-06-roadmap-10-tinh-nang.md`.

---

## Gửi vào nhóm / kênh

- **Nhóm**: thêm bot vào nhóm, gửi 1 tin trong nhóm, rồi mở `/getUpdates` — lấy `chat.id` (bắt đầu bằng `-100...` với nhóm được boost).
- **Kênh (channel)**: tạo channel, thêm bot làm **Administrator**, `chat.id` là `-100...` của channel.
- Nếu `/getUpdates` trả `{"result":[]}`: ai đó đã set **webhook** cho bot → gọi `/deleteWebhook` một lần:
  `https://api.telegram.org/bot<TOKEN>/deleteWebhook`

## Cấu hình nâng cao

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `ALERTS_ENABLE` | `False` | Công tắc gửi thật. Tắt thì rules vẫn chạy và in console. |
| `RANK_ALERT_DROP` | `5` | Số hạng rơi (≥) để báo, so với **lần check liền trước**. |
| `RANK_ALERT_TOP10_FALL` | `True` | Bật/tắt riêng rule "rớt khỏi Top 10". |
| `ALERTS_STATE_DIR` | `data` | Nơi lưu `alerts_state.json` (state chống spam, giữ 14 ngày). |

Xóa file `data/alerts_state.json` nếu muốn nhận lại toàn bộ cảnh báo của hôm nay.

## Giới hạn đã biết

- Telegram lỗi / mất mạng → tin **không** bị đánh dấu "đã gửi", lần check sau sẽ thử lại; rank check và GSC fetch **không** chết theo.
- Chỉ báo từ dữ liệu rank SERP; chưa cảnh báo CTR/impressions bất thường (phase sau).
- Chưa có email / Slack / Discord.
