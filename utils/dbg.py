"""
utils/dbg.py — log có chọn lọc cho tầng giả lập hành vi.

Mặc định im lặng. Đặt INTERACTION_DEBUG=True trong config/settings.py để thấy những
lỗi trước đây bị `except: pass` nuốt vô hình (selector không match, trang đổi layout,
timing race...). Đây chỉ là ống nhìn vào lỗi đã xảy ra, không đổi hành vi fallback.
"""
import config.settings as cfg


def warn(where: str, exc: BaseException) -> None:
    """In một dòng debug khi bật cờ; không bao giờ raise (đang ở trong except)."""
    if getattr(cfg, "INTERACTION_DEBUG", False):
        print(f"   [dbg] {where}: {type(exc).__name__}: {str(exc)[:100]}")
