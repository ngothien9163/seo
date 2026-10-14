# F8 — Content generation bằng Ollama — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development / executing-plans. Bước theo checkbox.

**Goal:** `python main.py --generate "nối mi tự nhiên"` lấy một mục trong `content/planner.DEFAULT_30D_PLAN` (theo `--day`) hoặc đúng từ khóa đang track → gọi Ollama **2 bước** (outline → draft) → viết markdown có frontmatter vào `content/drafts/<slug>-< timestamp >.md`, kèm **tự kiểm tra SEO thô** (từ khóa xuất hiện trong H1? trong 2 lần đầu body?) in ra console. GUI: nút **✍️ SINH BÀI (Ollama)** ở tab 🤖 AI Engine. Tool **chỉ sinh, không tự đăng**.

**Architecture:** 3 module, lớp thuần test được không cần Ollama:
`utils/content_prompts.py` (prompt builder + slugify + frontmatter + `seo_check` — **không IO, không network, không import requests**) →
`utils/ollama_client.py` (client Ollama **dùng chung** đầu tiên của repo: `base_from_url` / `check_connection` / `generate`, nhận `post` tiêm vào để test) →
`content/generator.py` (pipeline outline→draft→file + `run_generate_cli`) → CLI/GUI. `generator` gọi `ollama_client`, `ollama_client` không biết gì về `generator`.

**Tech Stack:** Python 3.11 stdlib (`json`, `os`, `re`, `unicodedata`, `datetime`) + `requests` (đã có trong requirements.txt), model `qwen3:30b-a3b` (`cfg.CONTENT_MODEL`). **Không** thêm dependency (không SDK `ollama` — gọi thẳng `/api/generate`), **không** Playwright.

**Spec:** card F8 (roadmap dòng 143–153). Trạng thái máy dev: **Ollama đang TẮT** (đo 2026-10-14: `localhost:11434` từ chối kết nối) → mọi test offline tiêm `post`/`client`; verify bài thật là việc của owner sau khi `ollama serve`.

## Global Constraints

- **Không có client Ollama tái dùng được trong repo.** `utils/interactions.py:117-153` hard-code `http://localhost:11434/api/generate` + `qwen2.5-coder:7b`, không đọc `cfg`, không retry; GUI tự parse URL bằng chuỗi ở **2 chỗ** (`ui.py:866`, `ui.py:890`). F8 tạo `utils/ollama_client.py` **một lần**, GUI dùng chung (Task 4 gộp 2 chỗ parse về `base_from_url`), **không** sửa `interactions.py` (ngoài phạm vi).
- **Không tự đăng, không sinh hàng loạt.** Theo card: ngoài phạm vi WordPress API, sinh ảnh, và "sinh cả tháng trong 1 lần chạy". `--generate` sinh **một** bài mỗi lệnh.
- **`stream: False`, timeout `CONTENT_GEN_TIMEOUT = 300` s** (model 30b chậm), **retry đúng `CONTENT_GEN_RETRIES = 1` lần và chỉ khi timeout** — lỗi khác (Ollama tắt, 500, JSON hỏng) trả thông điệp tiếng Việt ngay, không vòng lặp vô hạn.
- **Không raise, không `sys.exit` trong module** — `generate` trả `(text|None, error)`; `run_generate_cli` trả mã exit (0 ok · 1 Ollama/gọi lỗi · 2 input sai). Console in an toàn vì `main.py` đã reconfigure UTF-8 (F4).
- **Ollama là localhost, không có credential.** Không in prompt payload chứa dữ liệu nhạy cảm ra log; URL lấy từ `cfg.OLLAMA_URL` (GUI ghi `entry_ollama_url` vào `cfg` lúc chạy, `ui.py:974-976`) — **không** hard-code host ở module mới.
- Draft ghi **UTF-8 không BOM** (khác CSV của F1 vốn cần BOM cho Excel), tên file có timestamp để **không bao giờ ghi đè** (2 lần cùng từ khóa = 2 file), atomic qua `.tmp` + `os.replace` (pattern `utils/keywords.py:83-96`).
- Path drafts qua **một hàm duy nhất** `drafts_dir()` đọc `cfg.CONTENT_DRAFTS_DIR` lúc gọi — hedge F10.
- **`content/drafts/` phải gitignore** (bản nháp máy sinh, owner duyệt rồi mới dùng; vào repo là rác). Task 4 test pin điều này.
- Kiểm tra SEO là **thô, chủ ý**: fold-không-dấu (tái dùng `utils/keywords._fold` → `gsc_client._fold`) đếm sự hiện diện trong H1 + 2 lần đầu, **không** đếm density, **không** cam kết "bài đạt chuẩn SEO".
- `content/planner.py` **tái khai báo** `CONTENT_MODEL`/`CONTENT_TIMEOUT=120` (dòng 14-15) và keyword trong `DEFAULT_30D_PLAN` **mất dấu tiếng Việt** (mojibake, dòng 20-24). F8 **không** sửa planner, **không** tin keyword của planner làm từ khóa chính — từ khóa chính đến từ `--generate` hoặc `utils.keywords.load_keywords()`; planner chỉ cho `topic/type/target`.
- Test `_quick_content_test.py` ở root (gitignored), assert thuần, **không pytest, không network** (tiêm `post`/`client`), chạy `PYTHONIOENCODING=utf-8`. Mỗi task một commit.

## Review Focus

1. `slugify("Nối Mi Tự Nhiên Là Gì?")` → `"noi-mi-tu-nhien-la-gi"` (bỏ dấu, bỏ `?`, nối `-`, không dấu `-` đầu/cuối); chuỗi chỉ có ký tự đặc biệt → rỗng → fallback an toàn.
2. `check_connection` khi Ollama **tắt** (ConnectionError) → `{ok: False, message}` chứa đúng URL base, **không raise**; khi `/api/tags` trả `{"models":[{"name":...}]}` → đếm đúng số model.
3. `generate` retry **đúng 1 lần khi timeout**: `post` raise `Timeout` lần 1 rồi trả OK lần 2 → `post` được gọi **2** lần, kết quả OK. `post` raise `ConnectionError` → gọi **1** lần, trả error (không retry lỗi không-phải-timeout). 4 attempts là bug.
4. `generate` parse `{"response": "..."}`; response thiếu key / không phải JSON / HTTP != 200 → trả `(None, message)` có ngữ cảnh, **không** `None` trần gây crash dây chuyền.
5. Pipeline: outline rỗng/None → không gọi bước draft, báo lỗi rõ; draft OK nhưng `post` trả text có fence ```json``` bọc ngoài (model hay làm vậy) → strip fence trước khi ghi file.
6. Frontmatter: `---` mở & đóng đúng một cặp, `date` dạng ISO, `keyword`/`topic`/`type`/`model` có mặt; `slug` từ keyword chứ **không** từ topic.
7. Không ghi đè: `_draft_path` với timestamp va nhau → thêm suffix `-2`; file `.tmp` không được sót lại sau khi ghi.
8. `run_generate_cli("")` khi `load_keywords()` rỗng → exit 2 + hướng dẫn thêm từ khóa (`--gsc-add-keyword` / tab ⚙️). `--dry-run` **không** gọi `post` và **không** ghi file (in prompt + đường dẫn dự kiến).
9. GUI: guard `_generate_running` chặn双击, nút disable khi chạy, thread nền nhả cờ ở `finally`, log `✍️ Đã lưu <path>`.
10. Purity (AST): `content_prompts.py` không import `requests`/`ollama_client`/`os`; `ollama_client` chỉ import `requests` **trong hàm**; `generator` không tự gọi `sys.exit`/`os.system`.

## Quyết định đã chốt

| Câu hỏi | Chốt | Lý do |
|---|---|---|
| Model | `cfg.CONTENT_MODEL` (`qwen3:30b-a3b`) | card chốt; README đã hướng dẫn `ollama pull qwen3:30b-a3b`. |
| Endpoint | `{base}/api/generate`, `stream:false` | theo card; không dùng `/api/chat` (một lượt prompt là đủ cho outline/draft). |
| Client ở đâu | `utils/ollama_client.py` **mới**, GUI dùng chung | repo chưa có client dùng chung; GUI đang duplicate parse URL 2 lần. |
| Prompt builder ở đâu | `utils/content_prompts.py` thuần | test assert các mảnh bắt buộc có mặt mà không cần network. |
| Nguồn topic | `content/planner.DEFAULT_30D_PLAN` theo `--day N` | card: "chọn một mục trong content plan 30 ngày". |
| Nguồn từ khóa | `--generate "<kw>"`, fallback `load_keywords()[0]` | keyword planner mất dấu → không dùng làm từ khóa chính. |
| Draft format | `.md` + frontmatter YAML-ish, UTF-8 không BOM | owner duyệt/sửa tay rồi mới đăng. |
| Draft có commit? | **Không** — gitignore `content/drafts/` | bản nháp máy sinh, mỗi lần chạy một file, vào repo là rác. |
| SEO check | fold dấu, H1 + 2 lần đầu, chỉ in console | card: "kiểm tra SEO tự động thô". |
| Ngoài phạm vi | tự đăng, sinh ảnh, batch cả tháng, sửa `interactions.py` | theo card + giữ blast radius. |

---

### Task 1: `utils/content_prompts.py` — prompt builder + SEO check thuần

**Files:** Create `utils/content_prompts.py`, Create `_quick_content_test.py`.

**Interfaces (Produces):** `slugify(text) -> str`, `outline_prompt(topic, keyword, content_type="blog", target="") -> str`, `draft_prompt(outline, keyword, topic="", content_type="blog", target="") -> str`, `build_frontmatter(meta: dict) -> str`, `assemble(frontmatter, body) -> str`, `extract_h1(markdown) -> str`, `seo_check(markdown, keyword) -> dict` (`{"keyword","in_h1","first_two_ok","occurrences"}`).

- [x] Step 1 — Test fail trước: `slugify` (có dấu → không dấu, khoảng trắng → `-`, bỏ ký tự đặc biệt, collapse `--`, trim `-`, rỗng → `"bai-viet"`); `outline_prompt` chứa cả `topic` + `keyword` + từ "dàn ý"/"outline" + giới hạn số mục; `draft_prompt` chứa `outline` đã sinh + keyword + `content_type`; prompt **không** chứa từ "WordPress"/"tự đăng"; `build_frontmatter` đúng một cặp `---`, có đủ key, escape được giá trị chứa `:`; `extract_h1` lấy dòng `# ` đầu, bỏ code fence; `seo_check` fold-không-dấu ("Nối Mi" khớp "nối mi tự nhiên"), `in_h1` chỉ nhìn H1 không nhìn title HTML, `occurrences` đếm thân bài; AST purity (mục 10).
- [x] Step 2 — Chạy → FAIL (`ModuleNotFoundError: utils.content_prompts`).
- [x] Step 3 — Implement (stdlib `re`/`unicodedata`; **không** import requests/os ở đầu file).
- [x] Step 4 — Test → ALL PASS + CJK scan 0 + mutation battery (đảo `in_h1`, bỏ fold, `slugify` không trim, retry-là-hàm-pure → bỏ).
- [x] Step 5 — Commit: `feat: F8 prompt builder + seo check thuan (khong network)`

**Kết quả Task 1 (2026-10-14):** 18 test ALL PASS (16 ban đầu + 2 test biên thêm sau mutation), CJK scan 0, mutation **10/10 CAUGHT** (battery UTF-8, restore-bytes + sha256 verify). Battery bắt được 2 vụ survivor ban đầu → đã thêm test: `seo_check(md, "")` phải `in_h1 False` (từ khóa rỗng không khớp vô điều kiện), `extract_h1` bỏ qua `#` trong code fence khi fence đứng trước + không nhận `##` làm H1.
**Deviation:** signature chốt là `outline_prompt(keyword, focus="", content_type="", angle="")` và `draft_prompt(outline, keyword, topic="", content_type="", notes="")` — khác tên tham số ở plan (`topic, keyword, ...`). Test chỉ assert các needle xuất hiện nên không đổi hành vi; Task 3 (generator) là chỗ gọi duy nhất, giữ nhất quán với signature này.

### Task 2: `utils/ollama_client.py` — client Ollama dùng chung

**Files:** Create `utils/ollama_client.py`, Modify `_quick_content_test.py`.

**Interfaces:** `base_from_url(url=None) -> str`, `generate_url(base=None) -> str`, `check_connection(post=None, url=None) -> dict` (`{"ok","models","message"}`), `generate(prompt, model=None, timeout=None, retries=None, post=None, url=None) -> tuple[str|None, str]` (text, lỗi), `_post` mặc định (lazy `requests`).

- [x] Step 1 — Test fail trước (tiêm `post`): `base_from_url("http://h:11434/api/generate")` → `"http://h:11434"`, giữ path gốc nếu URL lạ; `check_connection` ConnectionError → `ok False` + message chứa host, **không raise**; OK → `models` đếm từ `{"models":[{"name":...}]}`; `generate` timeout 1 lần rồi OK → `post` gọi **2** lần + text đúng; ConnectionError → gọi **1** lần; HTTP != 200 / JSON rác / thiếu `response` → `(None, message)`; text có fence ```json bọc → strip; `model` mặc định đọc `cfg.CONTENT_MODEL` **lúc gọi** (đổi cfg giữa 2 test có tác dụng); payload `stream` **phải** `False`.
- [x] Step 2 — Chạy → FAIL.
- [x] Step 3 — Implement (retry chỉ cho `requests.exceptions.Timeout`, giữ import `requests` trong hàm).
- [x] Step 4 — Test ALL PASS + mutation (retry cho mọi exception, `stream:True`, nuốt message lỗi → trả `""`, quên strip fence).
- [x] Step 5 — Commit: `feat: F8 ollama client dung chung (timeout 300s, retry chi khi timeout)`

**Kết quả Task 2 (2026-10-14):** 29 test ALL PASS (thêm 11 test Task 2), mutation **9/9 CAUGHT** (retry-all-exceptions, stream-true, swallow-error→"", no-strip-fence, retry-connection-error, no-retry-timeout, base-keeps-generate-suffix, tags-url-is-generate, non200-ignored). Battery bắt được survivor `non200-ignored` (body 500 không JSON bị fallback JSON-parse che mất) → thêm `test_generate_non_200_with_valid_body_still_fails` (503 kèm `{"response":...}` vẫn phải fail).
**Deviation:** (a) seam của `check_connection` là `get=None` (GET `/api/tags`), không phải `post` — generate dùng `post=None`; (b) `CONTENT_GEN_TIMEOUT/RETRIES/DRAFTS_DIR` (PHẦN J) thêm **ngay Task 2** vì client là nơi dùng đầu tiên (plan để ở Task 4); Task 4 không cần thêm lại; (c) `import requests` ở đầu ollama_client là OK (đây là tầng network — chỉ `content_prompts` mới phải thuần).

### Task 3: `content/generator.py` — pipeline outline→draft→file + CLI

**Files:** Create `content/generator.py`, Modify `_quick_content_test.py`.

**Interfaces:** `drafts_dir() -> str`, `plan_item(day=None, keyword="") -> dict|None`, `render_article(keyword, outline_and_draft, item) -> (path, text)` (ghi file, trả nội dung), `generate_article(keyword="", day=None, client=None, out_dir=None) -> (path|None, message)`, `run_generate_cli(keyword="", day=None, dry_run=False) -> int`.

- [x] Step 1 — Test fail trước (`client` tiêm trả canned text): ghi file UTF-8 **không BOM**, tên `<slug>-<YYYYMMDD-HHMMSS>.md`, 2 lần chạy → **2 file** (không ghi đè), `.tmp` không sót; frontmatter + thân bài có mặt; outline fail → không gọi draft + message rõ; `plan_item(day=3)` đúng mục ngày 3, `day` ngoàirange → None, `day` trùng keyword → match fold; `run_generate_cli(dry_run=True)` **không** gọi `client` và **không** tạo file; Ollama down (client giả trả lỗi) → exit 1; input trống + `load_keywords()` rỗng → exit 2; exit 0 in đường dẫn + `seo_check`.
- [x] Step 2 — Chạy → FAIL.
- [x] Step 3 — Implement pipeline + atomic write.
- [x] Step 4 — Test ALL PASS + mutation.
- [x] Step 5 — Commit: `feat: F8 pipeline outline->draft + ghi content/drafts (atomic, khong de)`

**Kết quả Task 3 (2026-10-14):** 37 test ALL PASS (thêm 8 test Task 3, dùng `FakeClient` tiêm — không network), CJK 0, mutation **8/8 CAUGHT** (overwrite-không-bump, BOM-sig, non-atomic-không-replace, draft-gọi-dù-outline-fail, dry_run-gọi-client, plan-day-ngoai-range-tra-ve-last, keyword-match-exact-thay-fold, draft-dung-outline-lam-prompt). BOM mutant ban đầu SKIP do anchor `\\n` escape sai trong harness → chạy lại đơn lập với anchor `encoding="utf-8", newline=` → **CAUGHT** (test `..._two_distinct_files` assert `not raw.startswith(b"\xef\xbb\xbf")`).
**Deviation:** (a) `dry_run` đặt ở `generate_article(..., dry_run=True)` (tra (None, msg) chứa 2 prompt, KHÔNG gọi client, KHÔNG tạo file) để CLI chỉ forward — plan chỉ ghi dry_run ở CLI; (b) `render_article(..., out_dir=None)` thêm tham số out_dir cho test ghi vào folder tạm; (c) chuỗi in ra generator.py dùng **full Unicode có dấu** (nhất quán ollama_client), sửa lại bản ASCII-stripped ban đầu.

### Task 4: CLI + GUI + README + gitignore

**Files:** Modify `main.py`, `ui.py`, `config/settings.py` (PHẦN J), `.gitignore`, `README.md`, Modify `_quick_content_test.py`.

**Interfaces:** settings mới `CONTENT_GEN_TIMEOUT = 300`, `CONTENT_GEN_RETRIES = 1`, `CONTENT_DRAFTS_DIR = "content/drafts"`; `main.py` branch `--generate` (+ `--day`, `--dry-run`); GUI `btn_generate` + `run_generate_content` + `_generate_running`.

- [ ] Step 1 — Test fail trước: AST `main.py` có `"--generate"`, `"--day"`, `"--dry-run"` + gọi `run_generate_cli` với `keyword=`/`day=`/`dry_run=`; help `show_strategy` có dòng `--generate`; GUI có `btn_generate`/`def run_generate_content`/`_generate_running`/`SINH BÀI`, worker gọi `generate_article` + reset cờ ở `finally` + guard `is_running`; settings PHẦN J khai mỗi key **đúng một lần** và PHẦN I/H còn nguyên; `.gitignore` có `content/drafts`; README needle `### 14.`, `--generate`, `content/drafts`, `CONTENT_GEN_TIMEOUT`, `qwen3:30b-a3b`, "chỉ sinh, không tự đăng", cây project có `content_prompts.py`/`ollama_client.py`/`generator.py`, bảng cấu hình có 3 key mới.
- [ ] Step 2 — Chạy → FAIL.
- [ ] Step 3 — Implement wiring (dùng `_flag_value` cho `--generate`; `--day` parse int, sai → `run_generate_cli` tự báo exit 2).
- [ ] Step 4 — GUI: nút **✍️ SINH BÀI (Ollama)** trong hàng nút `bf` tab 🤖 AI Engine (cùng pattern `_audit_running`); **gộp** 2 chỗ parse URL ở `ui.py:866`/`890` về `ollama_client.base_from_url` (một sự thật về base URL).
- [ ] Step 5 — README mục **"### 14. Content generation bằng Ollama (F8)"** + bảng PHẦN J + cây project + bullet "Ollama chưa chạy" trong Xử lý sự cố + paragraph F8-không-thêm-dependency.
- [ ] Step 6 — **Verify offline** (Ollama TẮT trên máy dev, đo 2026-10-14): `--generate "nối mi" --dry-run` → exit 0, in prompt outline + draft, **không** tạo file; `--generate "nối mi"` (Ollama tắt) → exit 1 + "chưa chạy Ollama tại http://localhost:11434", không traceback; pipeline + ghi file đã được chứng minh bằng test tiêm `client`, **chưa** chứng minh bằng bài thật từ `qwen3:30b-a3b` — owner phải `ollama serve` rồi chạy lại để xác nhận chất lượng bài.
- [ ] Step 7 — GUI probe (mainloop thật + tiêm `client` trả canned draft, **không** network): đếm lời gọi, guard, nút disable→normal, `✍️ Đã lưu` xuống log box, và **xóa file draft probe** tạo ra.
- [ ] Step 8 — Commit: `feat: F8 cli --generate + nut GUI sinh bai + README`

## Tiêu chí hoàn thành (card F8)

- Ollama tắt → thông báo "chưa chạy Ollama tại <url>", exit 1, **không crash** (verify offline đạt trên máy dev).
- Bài sinh ra có đủ frontmatter + lưu đúng `content/drafts/`.
- Chạy 2 lần cùng từ khóa → 2 file khác nhau (không ghi đè).
- Tự kiểm tra SEO thô in ra console (kw trong H1? trong 2 lần đầu?).
- Nút GUI chạy thread nền, có guard, log xuống khung.
- **Không** tự đăng, **không** batch cả tháng, **không** thêm dependency.

## Known limitations (ghi nhận, không sửa trong plan này)

- **Không verify được chất lượng bài thật trên máy dev** (Ollama tắt 2026-10-14). Pipeline + file I/O được chứng minh bằng unit test tiêm `client`; văn phong/độ chính xác của `qwen3:30b-a3b` là việc owner kiểm khi `ollama serve`.
- `content/prompts` chỉ là tiếng Việt hướng dẫn model — **không** phải RAG, không nhúng dữ liệu site, không guarantee số liệu đúng; owner phải duyệt fact trước khi đăng (đúng tinh thần "tool chỉ sinh").
- Keyword trong `DEFAULT_30D_PLAN` mất dấu (mojibake cũ) → `plan_item(keyword=...)` match theo fold vẫn chạy nhưng `topic/target` planner in ra vẫn có thể thiếu dấu; sửa planner ngoài phạm vi F8.
- Không tạo ảnh, không meta description riêng, không schema — đó là việc khác (card ghi rõ ngoài phạm vi).
- Ollama localhost, không auth: client **không** gửi gì ra ngoài máy — nếu owner trỏ `OLLAMA_URL` sang host từ xa thì payload prompt (chứa từ khóa + content plan) rời máy, cân nhắc trước.
