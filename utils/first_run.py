# -*- coding: utf-8 -*-
"""utils/first_run.py — T15: `--first-run` chạy thử lần đầu, tuần tự như checklist.

Owner mới mở tool, wizard nói bước nào thiếu — nhưng wizard CHỈ ĐỌC. Lệnh này
là phần "thử xem lệnh chạy được thật": chạy TUẦN TỰ 4 bước rẻ nhất của
CHECKLIST_FIRST_RUN.md, mỗi bước tự nuốt lỗi riêng (lỗi bước trước không
đẩy người đi qua bước sau chết), cuối bảng là danh sách VIỆC KẾ TIẾP.

Bước:
  1. wizard   — in trạng thái 6 bước (T14), không mạng
  2. doctor   — kiểm tra môi trường (combo #1), không mạng
  3. audit    — crawl chính site (F6), chỉ site mình — CHẠY THẬT
  4. export CSV các nguồn đã có (không chết khi rỗng)
  5. đề xuất việc kế tiếp dựa trên wizard steps (rank/GSC/Ollama...)

Nguyên tắc:
- KHÔNG đụng mã secret, KHÔNG check GSC thật (403/400 sẽ làm lệnh thất bại
  ở lần đầu — việc đó thuộc docs/SETUP_GSC.md), KHÔNG mở browser.
- KHÔNG tự sửa config: đây là chạy thử + hướng dẫn, không phải autocorrect.
- Không raise: tổng kết cuối luôn in được, exit 0 luôn — lệnh đọc/chạy thử,
  không phải cổng chặn.
"""
import io
import contextlib

from utils import site_paths

OK_MARK = "✓"
FAIL_MARK = "✗"
SKIP_MARK = "—"  # bước trước chết thì bước sau skip


def _run_into_buf(fn, *args, **kwargs) -> tuple[int, str]:
    """Chạy fn với stdout chặn vào buffer — mỗi bước in riêng trong bảng."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            code = fn(*args, **kwargs)
    except Exception as e:
        return 999, f"Lỗi không xử lý được: {type(e).__name__}: {e}"
    return (code if isinstance(code, int) else 0), buf.getvalue()


def first_run_steps() -> list[dict]:
    """Chạy tuần tự và trả [(key, title, code, note, output)]. KHÔNG raise."""
    # Bước 1: wizard T14
    import utils.setup_wizard as sw
    from utils.doctor import run_doctor_cli

    steps = []
    code_w, out_w = _run_into_buf(sw.run_wizard_cli)
    steps.append({"key": "wizard", "title": "Wizard 6 bước (T14)",
                  "code": code_w, "note": "trạng thái cài đặt — không mạng",
                  "output": out_w})

    # Bước 2: doctor — check file/config, không mạng (ping Ollama là --net, để owner tự chọn)
    code_d, out_d = _run_into_buf(run_doctor_cli, net=False)
    steps.append({"key": "doctor", "title": "Doctor môi trường",
                  "code": code_d, "note": "không mạng — check file/config",
                  "output": out_d})

    if code_w != 0 or code_d != 0:
        # wizard/doctor exit 0 luôn - nhưng nếu chết hẳn (ex 999) thì skip audit
        steps.append({"key": "audit", "title": "Audit site (F6)",
                      "code": 3, "note": "bỏ qua — wizard/doctor trục trặc lớn",
                      "output": ""})
        steps.append({"key": "export", "title": "Xuất CSV",
                      "code": 3, "note": "bỏ qua — wizard/doctor trục trặc lớn",
                      "output": ""})
        return steps

    # Bước 3: audit — crawl thật, chỉ site mình
    from utils.site_auditor import run_audit_cli
    code_a, out_a = _run_into_buf(run_audit_cli)
    steps.append({"key": "audit", "title": "Audit site (F6)",
                  "code": code_a, "note": "crawl HTML tĩnh site mình",
                  "output": out_a})

    # Bước 4: export CSV — nguồn rỗng thì báo file chỉ có tiêu đề,
    # không chết cả vòng
    code_e, out_e = _run_into_buf(_export_csvs)
    steps.append({"key": "export", "title": "Xuất CSV các nguồn có",
                  "code": code_e, "note": "rank/GSC/audit — rỗng vẫn chạy",
                  "output": out_e})
    return steps


def _export_csvs() -> int:
    """4 lần xuất CSV — nguồn rỗng chỉ nhắc, không raise."""
    from utils.exporter import export_audit, export_gsc, export_rank
    ok = bad = 0
    for label, fn in (("xếp hạng", export_rank), ("audit", export_audit),
                      ("Search Console", export_gsc)):
        try:
            path, n = fn()
            ok += 1
            tone = "" if n else " (chưa có dữ liệu — file chỉ có tiêu đề)"
            print(f"[Export] {label}: {path} ({n} dòng){tone}")
        except Exception as e:
            bad += 1
            print(f"[Export] ❌ {label}: {type(e).__name__}: {e}")
    return 0 if bad == 0 else 1


def next_actions() -> list[str]:
    """Việc kế tiếp dựa trên wizard steps — mỗi dòng 1 hành động cụ thể."""
    import utils.setup_wizard as sw
    acts = []
    for s in sw.wizard_steps():
        if s["done"] or not s["hint"]:
            continue
        if not s["optional"]:
            acts.append(f"{sw.STEP_LABELS[s['key']]}  →  {s['hint']}")
        else:
            acts.append(f"(tùy chọn) {sw.STEP_LABELS[s['key']]}  →  {s['hint']}")
    return acts


def reel_markers(steps: list[dict]) -> list[str]:
    """Dòng riêng mỗi bước trong bảng tổng — [✓]/[✗]/[—]."""
    marks = []
    for s in steps:
        c = int(s["code"])
        m = OK_MARK if c == 0 else SKIP_MARK if c == 3 else FAIL_MARK
        title = f"{s['title']} ({s['note']})"
        marks.append(f"  [{m}] {title}  — exit {c}")
    return marks


def run_first_run_cli() -> int:
    """Entry `--first-run`: chạy thử tuần tự lần đầu — in từng bước + tổng kết + gợi ý việc kế tiếp."""
    print("=" * 96)
    print("  FIRST RUN — chạy thử tuần tự lần đầu (theo docs/CHECKLIST_FIRST_RUN.md, giá rẻ trước)")
    print("=" * 96)
    print(f"  Site: {site_paths.site_domain() or '(chưa cấu hình)'}"
          f"  |  per-site={'BẬT' if site_paths.is_multi_site() else 'TẮT (chưa migrate)'}")
    print("-" * 96)

    steps = first_run_steps()
    for s in steps:
        out = (s["output"] or "").rstrip()
        print(f"\n[{OK_MARK if not int(s['code']) else FAIL_MARK}] "
              f"{'─' * 78} {s['title']}")
        if out:
            for line in out.split("\n")[:14]:
                print(f"  {line}")
            if len(out.split("\n")) > 14:
                print("  … (bị cắt — chạy lệnh riêng để xem đầy đủ)")
        else:
            print("  (không in được output)")

    print("-" * 96)
    print("  TỔNG KẾT:")
    for line in reel_markers(steps):
        print(line)
    print("-" * 96)
    print("  VIỆC KẾ TIẾP (xu hướng trước):")
    acts = next_actions()
    for a in acts:
        print(f"   • {a}")
    if not acts:
        print("   • Chưa còn bước bắt buộc nào thiếu — mở docs/CHECKLIST_FIRST_RUN.md làm tick riêng.")
    print("  Chi tiết từng bước: docs/CHECKLIST_FIRST_RUN.md")
    print("=" * 96)

    # exit 0 luôn — lệnh này là chạy thử + hướng dẫn, không phải cổng chặn
    return 0
