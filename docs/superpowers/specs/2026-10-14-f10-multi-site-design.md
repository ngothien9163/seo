# Spec: F10 — Multi-site / multi-project (quản lý nhiều site trong một project)

- Ngày: 2026-10-14
- Trạng thái: ⏳ **CHỜ OWNER DUYỆT** — 4 quyết định (QĐ A/B/C mục 2 + scheduler lock mục 6, chốt ở cuối file) chưa chốt; chưa code vì migration đụng dữ liệu thật.
- Phân loại: Architectural — đổi nơi lưu state ở mọi module đọc/ghi và migrate file thật của owner (hard-to-reverse).
- Card gốc: `docs/superpowers/plans/2026-10-06-roadmap-10-tinh-nang.md` (mục F10).

## Vì sao spec này đứng lại chờ duyệt

F10 là task cuối trong roadmap và là task **duy nhất migrate dữ liệu thật** của owner
(`gsc_history.json`, `rank_history.json`, `session_state.json`, `config/keywords.json`…).
Roadmap gate nó sau *"spec đầy đủ + script migration. Đặt cuối vì đụng mọi nơi đọc/ghi state"*.
Đây là thao tác **hard-to-reverse** → phải chốt thiết kế trước, không refactor âm thầm.

---

## 1. Mục tiêu

Một project chạy được **nhiều site**, mỗi site có dữ liệu riêng không lẫn:

| Thuộc tính | hiện tại (1 site) | sau F10 (N site) |
|---|---|---|
| URL đích | `cfg.TARGET_URL` toàn cục | per-site |
| Từ khóa | `config/keywords.json` | `config/<site>/keywords.json` |
| Rank history | `rank_history.json` | `data/<site>/rank_history.json` |
| GSC history | `gsc_history.json` | `data/<site>/gsc_history.json` |
| Session/rate | `session_state.json` | `data/<site>/session_state.json` |
| Alerts state | `data/alerts_state.json` | `data/<site>/alerts_state.json` |
| Scheduler state/lock | `data/scheduler_state.json`, `scheduler.lock` | `data/<site>/scheduler_state.json`; lock vẫn dùng chung một ổ khóa process-wide |
| Backlink store/status | `config/backlinks.json`, `data/backlink_status.json` | per-site |
| Report CSV | `reports/<loai>_<ts>.csv` | `reports/<site>_<loai>_<ts>.csv` |
| Profile browser | `profiles/<profile_id>` | `profiles/<site>/<profile_id>` |

Cài đặt engine (Playwright, Ollama, Telegram token, PageSpeed key) vẫn **chung** —
chỉ dữ liệu + danh sách từ khóa là per-site.

---

## 2. Site model — 3 quyết định owner phải chốt

### Quyết định A — site được định danh bằng gì?

`site_domain()` (`utils/keywords.py:35`) và `target_domain()` (`utils/backlinks.py:59`)
đã quy về netloc bỏ `www.`. Ba lựa chọn cho **khóa thư mục**:

1. **(khuyến nghị) slug từ domain** — `nankybeauty.com` → `nankybeauty-com`.
   Đọc `cfg.TARGET_URL` ngay tại thời điểm gọi, không thêm key mới, khớp 100% helper hiện có.
2. **`SITE_ID` chuỗi tường minh** — owner khai `SITE_ID = "nanky"` trong settings;
   cho phép 2 site cùng domain (2 property staging/prod) nhưng thêm config burden.
3. **`cfg.GSC_SITE_URL`** — `sc-domain:nankybeauty.com`; chỉ meaningful khi đã bật GSC,
   rank/session không có GSC thì không có khóa. **Loại.**

→ Cần owner chọn 1 hay 2. Mặc định tôi làm theo **(1)**.

### Quyết định B — tương thích ngược (single-site không đổi hành vi)

Owner đang chạy 1 site. Phương án:

- **(khuyến nghị) fallback flat-file:** resolver per-site, nếu `data/<site>/...` chưa tồn tại
  mà file cũ ở gốc (`rank_history.json`) có → đọc file cũ. Owner bật multi-site thì migrate.
  → đơn site **không breaking**, chưa migrate vẫn chạy y như hôm nay.
- **cứng:** luôn dùng `data/<site>/...`, bắt buộc migrate trước khi chạy. Gọn code nhưng
  phá vỡ workflow hiện tại ngay commit đầu.

→ Cần owner chọn. Mặc định **(fallback)**.

### Quyết định C — browser profile có scope theo site không?

Profile giờ keyed theo `profile_id` (persona) trong `browser_manager.py:289-405`, **không** theo site.
- **Giữ persona-chung** (khuyến nghị): một "nhân vật" dùng cho mọi site = hành vi người thật hơn,
  không phá cookie đã gây dựng. Chỉ history/state là per-site.
- **Scope per-site:** cách ly tuyệt đối, nhưng phải login lại từng site và profile mỏng đi.

→ Mặc định **(giữ persona-chung)**; chỉ đổi nếu owner muốn cách ly.

---

## 3. Cơ chế implement (theo hedge đã có sẵn trong repo)

Repo **đã** có pattern một-điểm-sinh-path cho các module mới:

- `utils/alerts.py:34 _state_path()` — `getattr(cfg,"ALERTS_STATE_DIR","data")` lúc gọi.
- `utils/scheduler.py:32 _data_dir()` + `_state_path()` + `_lock_path()`.
- `utils/site_auditor.py:584 _state_path()`; backlinks có `_store_path`/state dir riêng.

F10 chỉ cần **thêm một resolver dùng chung** và áp cùng pattern cho 5 file còn hard-code:

**Thêm `utils/site_paths.py`:**
```
def current_site_slug() -> str        # slug từ cfg.TARGET_URL (QĐ A)
def site_file(name) -> str            # data/<site>/<name>, fallback flat-file (QĐ B)
def site_config(name) -> str          # config/<site>/<name>, fallback config/<name>
def site_profile_dir(profile_id)      # profiles/<site>/<id> hoặc profiles/<id> (QĐ C)
def report_name(kind, ts) -> str      # "<site>_<kind>_<ts>.csv" (1 site: bỏ prefix)
```

**Re-point 5 hard-code** (đổi hằng số module thành hàm gọi lúc runtime):
- `utils/gsc_client.py:31` `HISTORY_FILE`/`DATA_FILE` → `site_file("gsc_history.json")`
- `utils/rank_tracker.py:41` `HISTORY_FILE` → `site_file("rank_history.json")`
- `utils/rate_limiter.py:16` `STATE_FILE` → `site_file("session_state.json")`
- `utils/keywords.py:22` `KEYWORDS_FILE` → `site_config("keywords.json")`
- `utils/exporter.py:31` `REPORTS_DIR` giữ nguyên, nhưng `_unique_path` gọi `report_name`

**Vấn đề đóng băng lúc import:** alerts/scheduler/gsc/rank/keywords hiện freeze path vào
hằng số module-level tại import. Đổi sang gọi-hàm-lúc-truy-cập là bắt buộc cho QĐ B;
các test hiện gán `rt.HISTORY_FILE = TEST_FILE` → resolver phải cho phép override
(giữ tên biến module, chỉ đổi default từ literal sang hàm).

`main.py`/`ui.py`: thêm `--site <slug>` (override `cfg.TARGET_URL` cho cả run), GUI dropdown
chọn site. CLI không có `--site` → dùng `cfg.TARGET_URL` như cũ.

---

## 4. Migration script — bắt buộc non-destructive

Vì đụng dữ liệu thật, script `--migrate-multi-site` **không được xóa/move in-place**:

1. Đọc `cfg.TARGET_URL` hiện tại → slug (QĐ A).
2. Với mỗi flat-file cũ (`gsc_history.json`, `rank_history.json`, `session_state.json`,
   `config/keywords.json`, `config/backlinks.json`, `data/backlink_status.json`,
   `data/alerts_state.json`, `data/scheduler_state.json`): **copy** sang `data/<site>/` / `config/<site>/`.
   Không xóa bản gốc.
3. In bảng "đã copy X → Y" + SHA256 để owner đối chiếu.
4. Sau khi owner xác nhận GUI/CLI đọc đúng từ folder per-site → **owner tự** xóa file gốc
   (script chỉ gợi ý lệnh, không tự xóa).
5. `--dry-run` in kế hoạch copy mà không ghi gì.

Idempotent: chạy 2 lần không nhân bản dữ liệu (bỏ qua nếu đích đã tồn tại và giống hash).

---

## 5. Chia task gợi ý (4 task, mỗi task 1 commit, TDD như F6–F8)

- **T1:** `utils/site_paths.py` thuần (slug resolver + fallback) — test: slug đúng,
  fallback flat-file khi chưa migrate, override module-level vẫn hoạt động.
- **T2:** re-point 5 hard-code + giữ API cho test hiện có — test: đủ 4 suite con
  (`_quick_gsc/keyword/export/alert/scheduler`) vẫn xanh với monkeypatch path.
- **T3:** `--migrate-multi-site` (+`--dry-run`) non-destructive — test: copy đúng bảng,
  idempotent, dry-run không ghi.
- **T4:** `--site` CLI + dropdown GUI + prefix site trong report name — test offline,
  không network.

---

## 6. blast radius (đã survey, cần owner biết)

- Đọc/ghi state: 5 hard-code + 4 hedged helper (alerts, scheduler, site_auditor, backlinks).
- Scheduler lock (`data/scheduler.lock`): nên **giữ dùng chung** để 2 job per-site không
  chồng nhau, hay tách per-site? → mặc định giữ chung; ghi vào QD nếu owner muốn khác.
- `browser_manager` profile: xem QĐ C.
- README cây project + bảng cấu hình + mục Xử lý sự cố phải cập nhật ở T4.

---

## 7. Việc tôi KHÔNG làm trong F10 (boundary)

- Không đụng anti-detect / profile fingerprinting (chỉ path, không đổi cơ chế stealth).
- Không auto-push, không xóa dữ liệu gốc.
- Không đụng schema lịch sử rank/GSC (chỉ đổi **nơi lưu**, định dạng giữ nguyên → T2/T3 không đổi JSON shape).

---

## Cần owner trả lời trước khi code

1. **QĐ A:** slug từ domain (mặc định) hay `SITE_ID` tường minh?
2. **QĐ B:** fallback flat-file để đơn site không breaking (mặc định) hay bắt buộc migrate?
3. **QĐ C:** profile giữ persona-chung (mặc định) hay scope per-site?
4. Scheduler lock: dùng chung (mặc định) hay per-site?

Owner trả lời (hoặc nói "chốt theo mặc định, làm ngay") → tôi viết plan F10 chi tiết rồi thực thi T1→T4.
