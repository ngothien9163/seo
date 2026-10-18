# -*- coding: utf-8 -*-
"""utils/audit_diff.py — G-3: audit diff — lỗi mới phát hiện vs đã sửa.

Đọc audit_history.json (2 mốc gần nhất, 0 request mới): lỗi xuất hiện mới
(xuất hiện lần này, lần trước không có) vs lỗi đã sửa (lần trước có, lần này
mất) — biết mình đang tiến bộ hay chểnh mảng.

Khớp lỗi theo (rule, url): detail có thể đổi chữ mà lỗi vẫn là lỗi đó.
Lần audit đầu tiên không diff được — tool nói rõ, không fake "0 thay đổi".
"""
from utils.site_auditor import load_audit_history

def _rule_key(finding: dict) -> str:
    return f"{finding.get('rule') or ''}|{finding.get('url') or ''}"


def build_diff(history: list) -> dict:
    """{added, fixed, current, prev, same} từ 2 mốc gần nhất.
    added/fixed: [finding] nguyên bản (rule, severity, url, detail).
    history trống/lỗi → {}, < 2 mốc → {'not_enough': True}."""
    records = [m for m in (history or [])
               if isinstance(m, dict) and isinstance(m.get("findings"), list)]
    if len(records) < 2:
        return {"not_enough": True} if records else {}
    prev, cur = records[-2], records[-1]
    prev_keys = {_rule_key(f) for f in prev["findings"] if isinstance(f, dict)}
    cur_keys = {_rule_key(f) for f in cur["findings"] if isinstance(f, dict)}
    added = [f for f in cur["findings"] if isinstance(f, dict)
             and _rule_key(f) not in prev_keys]
    fixed = [f for f in prev["findings"] if isinstance(f, dict)
             and _rule_key(f) not in cur_keys]
    return {"added": added, "fixed": fixed,
            "prev": prev, "cur": cur,
            "same": not added and not fixed}


def text(diff: dict) -> str:
    """Bảng diff human. Không đủ dữ liệu → hướng dẫn, không nói dối."""
    if not diff:
        return ("  Chưa có lịch sử audit nào — chạy `python main.py --audit`;"
                "\n  từ lần thứ hai, diff giữa hai lần audit gần nhất được tính"
                "\n  (lỗi mới phát hiện / đã sửa được).")
    if diff.get("not_enough"):
        return ("  Lịch sử audit mới có 1 mốc — chưa so được gì."
                "\n  Chạy `python main.py --audit` thêm một lần nữa rồi xem lại."
                "\n  (Lịch sử mốc bắt đầu từ lần có tính năng — mốc cũ không có.)")

    added, fixed = diff["added"], diff["fixed"]
    cur, prev = diff["cur"], diff["prev"]

    lines = ["  AUDIT GIỮA 2 LẦN GẦN NHẤT",
             f"   trước: {prev.get('saved_at', '?')} — {len(prev.get('findings') or [])} lỗi",
             f"    gần nhất: {cur.get('saved_at', '?')} — {len(cur.get('findings') or [])} lỗi",
             "  " + "-" * 68]
    if diff["same"]:
        lines.append("  ✅ Không thay đổi — cùng một bộ lỗi, chưa sửa gì và không phát mới.")
        return "\n".join(lines)
    if fixed:
        lines.append(f"  ĐÃ SỬA ({len(fixed)}) — có ở lần trước, lần này biến mất:")
        for f in fixed[:10]:
            lines.append(f'  ✅ [{f.get("severity")}] {f.get("rule")} — {f.get("url")}')
        if len(fixed) > 10:
            lines.append(f"  … và {len(fixed) - 10} lỗi nữa")
        lines.append("")
    if added:
        lines.append(f"  MỚI PHÁT HIỆN ({len(added)}) — lần này xuất hiện:")
        for f in added[:10]:
            lines.append(f'  ❌ [{f.get("severity")}] {f.get("rule")} — {f.get("url")}')
        if len(added) > 10:
            lines.append(f"  … và {len(added) - 10} lỗi nữa")
    return "\n".join(lines)


def run_audit_diff_cli() -> int:
    """`--audit-diff`: lỗi mới vs đã sửa giữa 2 lần audit gần nhất."""
    import config.settings as cfg
    diff = build_diff(load_audit_history())
    print("=" * 76)
    print(f"  AUDIT DIFF — {cfg.TARGET_URL or '(chưa cấu hình site)'}")
    print("=" * 76)
    print(text(diff))
    print("=" * 76)
    return 0
