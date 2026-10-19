# Sổ outreach — xin đặt link (T32)

> Mục tiêu: bạn gửi lời "cho mình một chỗ đặt link" cho site người khác bằng tay
> (mail, mạng X, tin nhắn) — tool **ghi sổ** + **nhắc follow-up trong báo cáo
> ngày**, để không bỏ rơi lời đề xuất nào đã gửi ra ngoài. Sổ sống ở
> `data/outreach.json` (per-site khi đã migrate).

## Tool làm gì / không làm gì

- Làm: ghi trạng thái 4 bước của mỗi lời đề xuất — **proposed** (đã gửi) →
  **agreed** (người ta đồng ý) → **placed** (link đã sống; từ đây hệ
  `--backlink-check` lo phần còn sống/dofollow) — hoặc **dead** (mai một: chờ
  lâu / từ chối). Nhắc trong báo cáo ngày: đề xuất ≥ 7 ngày chưa phản hồi,
  đồng ý ≥ 5 ngày chưa đặt link (đổi ngưỡng: `OUTREACH_REMIND_PROPOSED` /
  `OUTREACH_REMIND_AGREED` trong `config/settings.py`).
- KHÔNG làm: tự liên hệ ai, tự gửi mail, tự crawl/người site người ta, tự thêm
  vào `backlinks.json` (khi set placed, lệnh chỉ IN khuyên chạy `--backlink-add`
  — bạn bấm thì hệ verify mới tính).

## Ghi sổ

```bash
# thêm lời đề xuất — trang đích nên là 1 BÀI CỤ THỂ, không phải trang chủ
python main.py --outreach-add "https://spa-review.vn/top-spa-mi-hcm" \
    --outreach-kw "nối mi quận 2" \
    --outreach-title "Spa review HCM" \
    --outreach-contact "email | telegram @ten" \
    --outreach-note "đã gửi mail ngày 19/10"

# xem sổ
python main.py --outreach-list

# cập nhật trạng thái (đi lui được: agreed → proposed)
python main.py --outreach-set "spa-review.vn" --outreach-state agreed
python main.py --outreach-set "spa-review.vn" --outreach-state placed \
    --outreach-note "link live ngày 25/10"
# → lệnh sẽ in khuyên: python main.py --backlink-add "URL" để hệ verify theo dõi

# mai một (ấm im, từ chối)
python main.py --outreach-set "spa-review.vn" --outreach-state dead --outreach-note "họ im lặng"

# xóa hẳn khỏi sổ (dead thì không nhắc nữa rồi — remove chỉ khi thật sự cần dọn)
python main.py --outreach-remove "spa-review.vn"
```

Trùng URL tự chặn: một trang = một mục (dựa chuẩn bỏ tham số tracking như
backlink store — `?utm_*`, trailing slash là cùng một trang). Thêm lại URL đã
**dead** là mở vòng mới (mốc đề xuất mới); URL đang **placed** thì không thêm
nữa — vào danh sách backlink rồi.

## Nhật ký trạng thái

Mỗi mục ghi 4 mốc riêng: `proposed_at` / `agreed_at` / `placed_at` /
`dead_at` + `updated`. Chuyển trạng thái KHÔNG xóa mốc cũ — mở vòng thật sự
chỉ có qua add lại sau dead. Ghi atomic (tmp + os.replace) — sổ không cụt file
khi crash.

## Nhắc trong báo cáo ngày

`--daily-report` (và scheduler job `daily`) tự thêm dưới phần "── VIỆC HÔM NAY ──"
dòng cho bài quá hạn, tối đa 2 dòng/lần:

```
- 'Spa review HCM' (spa-review.vn) đã 12 ngày chờ phản hồi — nhắc 1 nhịp hoặc đánh dead.
- '…' (…) đồng ý 6 ngày chưa đặt link — gửi anchor / nhắc lại, quá hạn đánh dead.
```

Bài còn tươi, placed, dead thì KHÔNG xuất hiện — không spam. صف trong html
report (`--html-report` section "Sổ outreach — xin đặt link") cũng có trạng thái
+ số ngày chờ + ghi chú.

## Lỗi thường gặp

- **"URL trang đích không hợp lệ"** — thiếu `https://` hoặc rỗng; url cần scheme.
- **"'x' khớp 2 mục"** — set/remove khớp nhiều mục khi gõ substring; gõ thêm
  ký tự hoặc dùng URL đầy đủ.
- **"Trạng thái phải là 1 trong: proposed|agreed|placed|dead"** — chính tả.
- Sổ hiển thị trống dù đã thêm: kiểm tra `--outreach-list` ở cùng site
  (per-site `data/<slug>/outreach.json` khi đã `--migrate-multi-site`).
