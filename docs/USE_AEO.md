# Hướng dẫn Use AEO tracking (F9) — AI có nhắc brand mình không?

Tính năng F9: mỗi ngày bạn **tự hỏi một AI engine** (ChatGPT / Gemini / Perplexity / Copilot / …)
một câu theo từng từ khóa đang theo dõi, **copy câu trả lời vào file** rồi chạy
`--aeo-check`. Tool phân tích xem câu trả lời **có nhắc brand** (`AEO_BRANDS` trong
`config/settings.py`) không, lưu kết quả và hiển thị cạnh dữ liệu SERP/GSC.

**Vì sao phải dán tay?** Tự động hỏi AI bằng browser rơi đúng lớp né phát hiện bot
mà project tuyên bố không động (giống lý do bỏ F5). Dán tay = không gửi request nào,
không key, không phí.

Thời gian mỗi lần: **~1 phút** (hỏi AI + copy + chạy lệnh).

---

## Bước 1: Hỏi AI và copy câu trả lời

Từ ChatGPT/Gemini/Perplexity… đặt câu kiểu:

```
Ở TP.HCM thì chỗ nào nối mi/Uốn mi uy tín?
```

hoặc hỏi trực tiếp về brand để đo nhận diện:

```
Bạn biết shop nối mi nào ở Thủ Đức không? (Ví dụ bạn biết Nanky Beauty không?)
```

Copy toàn bộ câu trả lời (Ctrl+A trong khung trả lời → Ctrl+C).

## Bước 2: Dán vào file và chạy

Lưu vào bất kỳ file text nào, ví dụ `answers/chatgpt-2026-10-18-nomi.txt`
(thư mục `answers/` không được git theo dõi nếu bạn muốn):

```bash
python main.py --aeo-check answers/chatgpt-2026-10-18-nomi.txt --aeo-engine ChatGPT --aeo-keyword "nối mi"
```

- `--aeo-keyword` — từ khóa đang theo dõi (để khớp cột trong báo cáo gộp). **Bắt buộc.**
- `--aeo-engine` — chỉ là **tên dán nhãn**, tự do đặt ("ChatGPT", "Gemini", "Perplexity", …).
- Kết quả: `[AEO] ✓ ChatGPT nhắc brand trong "nối mi" (1 vị trí, ngày 2026-10-18)` hoặc `✗ KHÔNG nhắc`.

Dán lại trong cùng ngày cùng engine cùng từ khóa → **thay** kết quả cũ (1 bản ghi/ngày/từ khóa/engine).

## Bước 3: Xem báo cáo

```bash
python main.py --aeo-report       # chỉ AEO
python main.py --gsc-report       # báo cáo gộp — có thêm cột AI khi đã có dữ liệu AEO
```

Báo cáo gộp hiện `✓1/1` = 1 trên 1 engine đã hỏi có nhắc. **Chưa dán lần nào → báo cáo
gộp y như trước** (không có cột AI, không đổi gì).

## Cấu hình biến thể brand

Mặc định `config/settings.py`:

```python
AEO_BRANDS = ["Nanky Beauty", "nankybeauty.com", "nanky beauty"]
```

So khớp **bỏ dấu tiếng Việt** (viết "nanky beauty" không dấu vẫn nhận ra) và theo
**từ trọn vẹn** — `nankybeautyva` không bị đếm là `nanky beauty`. Thêm biến thể mới
(cách viết chữ liền, tên viết tắt, domain khác) bằng cách thêm phần tử vào list này.

## Giới hạn đã biết

- Lưu tối đa `AEO_HISTORY_KEEP` (500) bản ghi — cũ nhất bị cắt.
- Chỉ nhận diện brand **nêu tên**, chưa đo "có được gợi ý đầu bảng không" (vị trí nhắc
  được lưu dạng index token — nếu cần xét vị trí tương đối, mở thêm sau).
- Method (b) API có key (OpenAI/Gemini API) chưa làm — muốn tự động hóa thêm thì
  phải có key và owner chốt trước; wiring text đã sẵn sàng.
