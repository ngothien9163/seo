import customtkinter as ctk
import threading
import asyncio
import sys
import random
import time
import uuid
import itertools
import traceback
import requests
from datetime import date, timedelta
from tkinter import END

from core.browser_manager import BrowserManager
from tests.test_direct_access import run_deep_session
from utils.keywords import load_keywords, save_keywords
from utils import site_paths
import config.settings as cfg

_real_stderr = sys.stderr  # preserve before any redirect

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class RedirectText:
    def __init__(self, text_ctrl, app):
        self.output = text_ctrl
        self.app = app

    def write(self, string):
        if string:
            try:
                self.app.after(0, self._insert_text, string)
            except Exception:
                _real_stderr.write(string)

    def _insert_text(self, string):
        try:
            self.output.insert(END, string)
            self.output.see(END)
        except Exception:
            _real_stderr.write(string)

    def flush(self): pass


class TrafficBotUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SEO Traffic Bot — AI Powered")
        self.geometry("1300x820")
        self.is_running = False
        self.stop_event = threading.Event()
        self._session_ok = 0
        self._session_err = 0
        self._rank_running = False
        self._gsc_running = False
        self._audit_running = False
        self._backlinks_running = False
        self._generate_running = False
        self._alert_running = False
        self._htmlreport_running = False
        self._intlinks_running = False
        self._actions_running = False
        self._doctor_running = False
        self._clustgsc_running = False
        self._gsctrend_running = False
        self._ctrops_running = False
        self._planprog_running = False
        self._gscalerts_running = False
        self._tools_running = {tag: False for tag in
                               ("doctor-net", "page-impact", "content-gap",
                                "refresh-diff", "content-brief", "daily-report")}
        self._chart_running = False
        self._chart_visible = False
        self._wizard_running = False
        self._firstrun_running = False
        self._aeo_running = False

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main_area()

        sys.stdout = RedirectText(self.txt_log, self)
        sys.stderr = RedirectText(self.txt_log, self)

    # ═══════════════════════════════════════════════════════════════
    # SIDEBAR
    # ═══════════════════════════════════════════════════════════════

    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=290, corner_radius=0)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False)
        sb.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            sb, text="CONTROL CENTER",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(28, 16))

        self.btn_start = ctk.CTkButton(
            sb, text="▶  BẮT ĐẦU TREO MÁY",
            fg_color="#1a7a1a", hover_color="#24a824",
            height=50, font=ctk.CTkFont(size=14, weight="bold"),
            command=self.start_thread,
        )
        self.btn_start.grid(row=1, column=0, padx=20, pady=(0, 8))

        self.btn_stop = ctk.CTkButton(
            sb, text="⏹  DỪNG KHẨN CẤP",
            fg_color="#7a1a1a", hover_color="#a82424",
            state="disabled", height=40,
            command=self.stop_process,
        )
        self.btn_stop.grid(row=2, column=0, padx=20, pady=(0, 16))

        ctk.CTkFrame(sb, height=1, fg_color="#333").grid(row=3, column=0, sticky="ew", padx=20, pady=4)

        self.lbl_status = ctk.CTkLabel(sb, text="● Sẵn sàng", text_color="gray")
        self.lbl_status.grid(row=4, column=0, padx=20, pady=(8, 4))

        self.lbl_timer = ctk.CTkLabel(
            sb, text="",
            font=ctk.CTkFont(family="Consolas", size=18, weight="bold"),
            text_color="yellow",
        )
        self.lbl_timer.grid(row=5, column=0, padx=20, pady=4)

        # Session counter
        ctk.CTkFrame(sb, height=1, fg_color="#333").grid(row=6, column=0, sticky="ew", padx=20, pady=(12, 4))
        ctk.CTkLabel(sb, text="Sessions", font=ctk.CTkFont(size=11), text_color="gray").grid(row=7, column=0)

        sf = ctk.CTkFrame(sb, fg_color="transparent")
        sf.grid(row=8, column=0, padx=20, pady=4)
        ctk.CTkLabel(sf, text="✅").grid(row=0, column=0, padx=(0, 4))
        self.lbl_ok = ctk.CTkLabel(sf, text="0", font=ctk.CTkFont(size=14, weight="bold"), text_color="#00cc44")
        self.lbl_ok.grid(row=0, column=1, padx=(0, 16))
        ctk.CTkLabel(sf, text="❌").grid(row=0, column=2, padx=(0, 4))
        self.lbl_err = ctk.CTkLabel(sf, text="0", font=ctk.CTkFont(size=14, weight="bold"), text_color="#cc2222")
        self.lbl_err.grid(row=0, column=3)

        # Ollama status
        ctk.CTkFrame(sb, height=1, fg_color="#333").grid(row=9, column=0, sticky="ew", padx=20, pady=(12, 4))
        ctk.CTkLabel(sb, text="AI Engine", font=ctk.CTkFont(size=11), text_color="gray").grid(row=10, column=0)
        self.lbl_ollama_sidebar = ctk.CTkLabel(
            sb, text="● Chưa kiểm tra", text_color="gray", font=ctk.CTkFont(size=11))
        self.lbl_ollama_sidebar.grid(row=11, column=0, padx=20, pady=(2, 20))

    # ═══════════════════════════════════════════════════════════════
    # MAIN AREA
    # ═══════════════════════════════════════════════════════════════

    def _build_main_area(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        main.grid_rowconfigure(1, weight=1)
        main.grid_columnconfigure(0, weight=1)

        self.tabs = ctk.CTkTabview(main)
        self.tabs.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        self.tab_general  = self.tabs.add("⚙️ Cài Đặt Chung")
        self.tab_loop     = self.tabs.add("🔁 Treo Máy")
        self.tab_browser  = self.tabs.add("🖥️ Thiết Bị")
        self.tab_behavior = self.tabs.add("🎯 Hành Vi SEO")
        self.tab_ai       = self.tabs.add("🤖 AI Engine")
        self.tab_warmup   = self.tabs.add("🔥 Nuôi Nick")
        self.tab_rank     = self.tabs.add("📈 Xếp Hạng")
        self.tab_tools    = self.tabs.add("🧰 Phân Tích")
        self.tab_aeo      = self.tabs.add("📢 AI Nói Gì")
        self.tab_wizard   = self.tabs.add("🧙 Cài Đặt Lần Đầu")

        self._setup_tab_general()
        self._setup_tab_loop()
        self._setup_tab_browser()
        self._setup_tab_behavior()
        self._setup_tab_ai()
        self._setup_tab_warmup()
        self._setup_tab_rank()
        self._setup_tab_tools()
        self._setup_tab_aeo()
        self._setup_tab_wizard()

        # Log
        log_frame = ctk.CTkFrame(main)
        log_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=(8, 0))
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(1, weight=1)

        hdr = ctk.CTkFrame(log_frame, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=8, pady=(6, 0))
        ctk.CTkLabel(hdr, text="System Logs", font=ctk.CTkFont(size=12, weight="bold"), anchor="w").pack(side="left")
        ctk.CTkButton(hdr, text="Xóa Log", width=70, height=24, font=ctk.CTkFont(size=11),
                      command=lambda: self.txt_log.delete("0.0", END)).pack(side="right")

        self.txt_log = ctk.CTkTextbox(
            log_frame,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#0d0d0d", text_color="#00ff00",
        )
        self.txt_log.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

    # ═══════════════════════════════════════════════════════════════
    # TAB: CÀI ĐẶT CHUNG
    # ═══════════════════════════════════════════════════════════════

    def _setup_tab_general(self):
        t = self.tab_general
        t.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(t, text="Target URL:").grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        self.entry_url = ctk.CTkEntry(t, width=360, placeholder_text="https://example.com")
        self.entry_url.insert(0, cfg.TARGET_URL)
        self.entry_url.grid(row=1, column=0, sticky="w", padx=12)

        ctk.CTkLabel(t, text="Chế độ Traffic:").grid(row=2, column=0, sticky="w", padx=12, pady=(16, 4))
        self.radio_var = ctk.StringVar(value=cfg.TRAFFIC_MODE)
        rf = ctk.CTkFrame(t, fg_color="transparent")
        rf.grid(row=3, column=0, sticky="w", padx=12)
        ctk.CTkRadioButton(rf, text="Vao thang Link (Direct)", variable=self.radio_var, value="direct").pack(side="left", padx=(0, 8))
        ctk.CTkRadioButton(rf, text="Google Search SEO", variable=self.radio_var, value="search").pack(side="left", padx=(0, 8))
        ctk.CTkRadioButton(rf, text="AIO Chat (ChatGPT/Gemini)", variable=self.radio_var, value="aio").pack(side="left", padx=(0, 8))
        ctk.CTkRadioButton(rf, text="Mix (all)", variable=self.radio_var, value="mix").pack(side="left")

        ctk.CTkLabel(t, text="Số luồng đồng thời:").grid(row=4, column=0, sticky="w", padx=12, pady=(16, 4))
        sf = ctk.CTkFrame(t, fg_color="transparent")
        sf.grid(row=5, column=0, sticky="w", padx=12)
        self.slider_threads = ctk.CTkSlider(
            sf, from_=1, to=20, number_of_steps=19, width=280,
            command=lambda v: self.lbl_threads.configure(text=f"{int(v)} luồng"),
        )
        self.slider_threads.set(5)
        self.slider_threads.pack(side="left")
        self.lbl_threads = ctk.CTkLabel(sf, text="5 luồng", width=70)
        self.lbl_threads.pack(side="left", padx=8)

        ctk.CTkLabel(t, text="Danh sách Proxy (1 proxy/dòng):").grid(row=6, column=0, sticky="w", padx=12, pady=(16, 4))
        self.txt_proxy = ctk.CTkTextbox(t, width=360, height=100)
        self.txt_proxy.grid(row=7, column=0, sticky="w", padx=12, pady=(0, 12))
        if cfg.PROXY_LIST:
            self.txt_proxy.insert("0.0", "\n".join(cfg.PROXY_LIST))

        ctk.CTkLabel(t, text="Từ khóa Google SEO (mỗi dòng 1 từ):").grid(row=0, column=1, sticky="w", padx=20, pady=(12, 4))
        self.txt_keywords = ctk.CTkTextbox(t, width=280, height=230)
        self.txt_keywords.grid(row=1, column=1, rowspan=7, sticky="nsew", padx=20, pady=(0, 12))
        _kws = load_keywords()
        if _kws:
            self.txt_keywords.insert("0.0", "\n".join(_kws))

        # ── Multi-site (F10/F10b) — dropdown sổ site + nút áp theo Target URL ──
        sf_frame = ctk.CTkFrame(t, fg_color="transparent")
        sf_frame.grid(row=8, column=0, sticky="w", padx=12, pady=(12, 2))
        self.combo_sites = ctk.CTkComboBox(sf_frame, width=220, height=28,
                                           values=self._registry_values(),
                                           fg_color="#38383f", button_color="#5a5a6a")
        self.combo_sites.pack(side="left")
        ctk.CTkButton(sf_frame, text="📂 Site sổ", height=28, width=96,
                      font=ctk.CTkFont(size=11),
                      command=self.select_registry_site).pack(side="left", padx=(8, 0))
        ctk.CTkButton(sf_frame, text="➕ Thêm site", height=28, width=96,
                      font=ctk.CTkFont(size=11),
                      command=self.add_site_to_registry).pack(side="left", padx=(8, 0))
        ctk.CTkButton(sf_frame, text="⚡ Chạy cả sổ", height=28, width=110,
                      font=ctk.CTkFont(size=11), fg_color="#7a1a5a", hover_color="#982470",
                      command=self.run_sites_batch).pack(side="left", padx=(8, 0))
        self.combo_batch = ctk.CTkComboBox(sf_frame, width=120, height=28,
                                           values=["Check rank", "GSC fetch", "Audit", "Report HTML"],
                                           fg_color="#38383f", button_color="#5a5a6a")
        self.combo_batch.pack(side="left", padx=(8, 0))
        self.btn_apply_site = ctk.CTkButton(sf_frame, text="🔀 Áp dụng site (theo Target URL ở trên)", height=28,
                      font=ctk.CTkFont(size=11), command=self.apply_site).pack(side="left", padx=(8, 0))
        self.lbl_known_sites = ctk.CTkLabel(
            t, text="", font=ctk.CTkFont(size=10), text_color="gray",
            anchor="w", justify="left", wraplength=360)
        self.lbl_known_sites.grid(row=9, column=0, sticky="w", padx=12, pady=(0, 12))
        self._refresh_known_sites()

    def _known_sites_text(self) -> str:
        slugs = site_paths.known_site_slugs()
        return "Site đã migrate: " + (", ".join(slugs) if slugs else "(chưa có — chạy --migrate-multi-site)")

    def _refresh_known_sites(self):
        try:
            self.lbl_known_sites.configure(text=self._known_sites_text())
        except Exception:
            pass

    # ── F10b/F10c — sổ site trong UI ─────────────────────────────────────────

    def _registry_rows(self) -> list:
        from utils.site_registry import load
        try:
            return load()
        except Exception as e:
            print(f"[Sites] Không đọc được sổ site: {e}")
            return []

    def _registry_values(self) -> list:
        return [r["url"] for r in self._registry_rows()] or ["(sổ trống — chạy --sites)"]

    def select_registry_site(self):
        """📂: chọn site trong dropdown → điền Target URL (= nút 🔀 kết tiếp chỉ bấm cho chắc)."""
        url = (self.combo_sites.get() or "").strip()
        if not url or url.startswith("("):
            print("[Sites] Sổ site trống — thêm site bằng ➕ (site phải migrate trước).")
            return
        self.entry_url.delete(0, END)
        self.entry_url.insert(0, url)
        self.apply_site()

    def add_site_to_registry(self):
        """➕: thêm site đang nhập ở Target URL vào sổ (F10b) — có messagebox xác nhận migrate."""
        url = self.entry_url.get().strip()
        if not url:
            print("[Sites] Target URL trống — nhập domain rồi bấm ➕.")
            return
        try:
            from utils.site_registry import add, run_site_add_cli
            run_site_add_cli(url)
            self.combo_sites.configure(values=self._registry_values())
            self._refresh_known_sites()
        except Exception as e:
            print(f"[Sites] Thêm site lỗi: {type(e).__name__}: {e}")

    def run_sites_batch(self):
        """⚡: chạy 1 lệnh (rank/gsc/audit/report) qua TỪNG site sổ — process con mỗi site."""
        if self.is_running or getattr(self, "_rank_running", False) \
                or getattr(self, "_gsc_running", False) or getattr(self, "_audit_running", False):
            print("[Sites] ⏳ Có job đang chạy — dừng hẳn rồi mới chạy cả sổ.")
            return
        choice = (self.combo_batch.get() or "").strip()
        cli_map = {"Check rank": "--rank", "GSC fetch": "--gsc", "Audit": "--audit",
                   "Report HTML": "--html-report"}
        cli = cli_map.get(choice)
        if not cli:
            print("[Sites] Chọn lệnh trong dropdown ⚡ (Check rank / GSC fetch / Audit / Report HTML).")
            return
        rows = self._registry_rows()
        if not rows:
            print("[Sites] Sổ trống — không chạy lô gì cả.")
            return
        threading.Thread(target=self._sites_batch_worker, args=(cli,), daemon=True).start()

    def _sites_batch_worker(self, cli: str):
        try:
            from utils.sites_run import run_sites_run_cli
            run_sites_run_cli([cli])
        except Exception as e:
            print(f"[Sites] Chạy lô lỗi: {type(e).__name__}: {e}")


    def apply_site(self):
        """Đổi site đang làm việc: đặt cfg.TARGET_URL theo Target URL, module tự re-resolve lúc gọi."""
        # getattr chứ không self._x: test F10 gọi hàm này unbound trên stub SimpleNamespace.
        # Đổi cfg giữa lúc worker đang chạy thì nửa việc ghi vào data site cũ, nửa vào site mới.
        if self.is_running or getattr(self, "_rank_running", False) \
                or getattr(self, "_gsc_running", False) or getattr(self, "_audit_running", False) \
                or getattr(self, "_alert_running", False):
            print("[Site] ⏳ Có job đang chạy — dừng hẳn rồi mới đổi site.")
            return
        url = self.entry_url.get().strip()
        if not url:
            print("[Site] Target URL trống — nhập domain (vd shoplanhdep.com) rồi bấm Áp dụng.")
            return
        cfg.TARGET_URL = url if "://" in url else f"https://{url}"
        dom = site_paths.site_domain()
        if dom:
            cfg.GSC_SITE_URL = f"sc-domain:{dom}"
        mode = "BẬT (dùng data/<slug>/)" if site_paths.is_multi_site() else \
               "TẮT (dùng file flat gốc — site này chưa migrate)"
        print(f"[Site] Đã chuyển sang: {dom or cfg.TARGET_URL}  | per-site={mode}")
        self._refresh_known_sites()
        try:
            self.txt_keywords.delete("0.0", END)
            _k = load_keywords()
            if _k:
                self.txt_keywords.insert("0.0", "\n".join(_k))
        except Exception as e:
            print(f"[Site] Không nạp lại từ khóa: {e}")
        try:
            self.entry_url.delete(0, END)
            self.entry_url.insert(0, cfg.TARGET_URL)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════
    # TAB: TREO MÁY
    # ═══════════════════════════════════════════════════════════════

    def _setup_tab_loop(self):
        t = self.tab_loop

        self.chk_loop = ctk.CTkCheckBox(
            t, text="KÍCH HOẠT CHẾ ĐỘ TREO MÁY (AUTO LOOP)",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.chk_loop.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 8))

        ctk.CTkLabel(t, text="Tổng thời gian treo máy (Phút):").grid(row=1, column=0, sticky="w", padx=40)
        self.entry_loop_time = ctk.CTkEntry(t, width=140, placeholder_text="VD: 120")
        self.entry_loop_time.insert(0, str(getattr(cfg, "LOOP_DURATION_MINUTES", 120)))
        self.entry_loop_time.grid(row=2, column=0, sticky="w", padx=40, pady=6)

        self.chk_new_user = ctk.CTkCheckBox(t, text="Luôn dùng User mới (xóa cookie sau mỗi phiên)")
        self.chk_new_user.select()
        self.chk_new_user.grid(row=3, column=0, sticky="w", padx=20, pady=(20, 8))

        ctk.CTkLabel(
            t, text="ℹ️  Mỗi luồng chạy độc lập — luồng nào xong trước tự bốc phiên mới.",
            text_color="gray", font=ctk.CTkFont(size=11),
        ).grid(row=4, column=0, sticky="w", padx=20, pady=8)

    # ═══════════════════════════════════════════════════════════════
    # TAB: THIẾT BỊ
    # ═══════════════════════════════════════════════════════════════

    def _setup_tab_browser(self):
        t = self.tab_browser

        ctk.CTkLabel(t, text="Thiết bị giả lập:").grid(row=0, column=0, sticky="w", padx=20, pady=(20, 4))
        self.combo_device = ctk.CTkComboBox(t, values=cfg.SUPPORTED_DEVICES, width=260)
        # Dùng giá trị từ cfg.DEVICE_NAME, fallback về item đầu tiên trong list
        default_device = cfg.DEVICE_NAME if cfg.DEVICE_NAME in cfg.SUPPORTED_DEVICES else cfg.SUPPORTED_DEVICES[0]
        self.combo_device.set(default_device)
        self.combo_device.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 20))

        self.sw_headless = ctk.CTkSwitch(t, text="Chạy Ngầm (Headless Mode)")
        self.sw_headless.grid(row=2, column=0, sticky="w", padx=20, pady=10)

        self.sw_images = ctk.CTkSwitch(t, text="Tải Hình Ảnh (tắt để nhanh hơn)")
        self.sw_images.select()
        self.sw_images.grid(row=3, column=0, sticky="w", padx=20, pady=10)

    # ═══════════════════════════════════════════════════════════════
    # TAB: HÀNH VI SEO
    # ═══════════════════════════════════════════════════════════════

    def _setup_tab_behavior(self):
        t = self.tab_behavior

        # Thời gian trên site
        ctk.CTkLabel(t, text="⏱  Thời gian xem trang (giây):",
                     font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=4, sticky="w", padx=14, pady=(14, 6))
        dur_f = ctk.CTkFrame(t, fg_color="transparent")
        dur_f.grid(row=1, column=0, columnspan=4, sticky="w", padx=20)
        ctk.CTkLabel(dur_f, text="Min:").pack(side="left")
        self.entry_min_time = ctk.CTkEntry(dur_f, width=70)
        self.entry_min_time.insert(0, str(cfg.DURATION_MIN))
        self.entry_min_time.pack(side="left", padx=(4, 14))
        ctk.CTkLabel(dur_f, text="Max:").pack(side="left")
        self.entry_max_time = ctk.CTkEntry(dur_f, width=70)
        self.entry_max_time.insert(0, str(cfg.DURATION_MAX))
        self.entry_max_time.pack(side="left", padx=4)

        ctk.CTkFrame(t, height=1, fg_color="#333").grid(row=2, column=0, columnspan=4, sticky="ew", padx=14, pady=12)

        # Hành vi SERP
        ctk.CTkLabel(t, text="🔍  Hành vi tìm kiếm Google:",
                     font=ctk.CTkFont(weight="bold")).grid(row=3, column=0, columnspan=4, sticky="w", padx=14, pady=(0, 8))

        self.chk_pogo = ctk.CTkCheckBox(
            t, text="Pogo-stick đối thủ  (click đối thủ → back → mới vào site mình)")
        self.chk_pogo.select()
        self.chk_pogo.grid(row=4, column=0, columnspan=4, sticky="w", padx=28, pady=4)

        pf = ctk.CTkFrame(t, fg_color="transparent")
        pf.grid(row=5, column=0, columnspan=4, sticky="w", padx=48, pady=(0, 6))
        ctk.CTkLabel(pf, text="Số lần tối đa:").pack(side="left")
        self.slider_pogo = ctk.CTkSlider(
            pf, from_=0, to=2, number_of_steps=2, width=110,
            command=lambda v: self.lbl_pogo_val.configure(text=f"{int(v)}"),
        )
        self.slider_pogo.set(2)
        self.slider_pogo.pack(side="left", padx=8)
        self.lbl_pogo_val = ctk.CTkLabel(pf, text="2", width=16)
        self.lbl_pogo_val.pack(side="left")
        ctk.CTkLabel(pf, text="lần", text_color="gray").pack(side="left", padx=4)

        self.chk_warmup_search = ctk.CTkCheckBox(
            t, text="Warm-up trước Google  (ghé trang VN phù hợp persona vài chục giây)")
        self.chk_warmup_search.select()
        self.chk_warmup_search.grid(row=6, column=0, columnspan=4, sticky="w", padx=28, pady=4)

        self.chk_kw_variation = ctk.CTkCheckBox(
            t, text="Thử từ khóa biến thể trước  (25% — mô phỏng gõ sai rồi sửa lại)")
        self.chk_kw_variation.select()
        self.chk_kw_variation.grid(row=7, column=0, columnspan=4, sticky="w", padx=28, pady=4)

        ctk.CTkFrame(t, height=1, fg_color="#333").grid(row=8, column=0, columnspan=4, sticky="ew", padx=14, pady=12)

        # Hành vi trên site
        ctk.CTkLabel(t, text="🌐  Hành vi trên site đích:",
                     font=ctk.CTkFont(weight="bold")).grid(row=9, column=0, columnspan=4, sticky="w", padx=14, pady=(0, 8))

        self.chk_third_page = ctk.CTkCheckBox(t, text="Ghé thêm trang thứ 3  (tăng pages/session)")
        self.chk_third_page.select()
        self.chk_third_page.grid(row=10, column=0, columnspan=4, sticky="w", padx=28, pady=4)

        tf = ctk.CTkFrame(t, fg_color="transparent")
        tf.grid(row=11, column=0, columnspan=4, sticky="w", padx=48, pady=(0, 8))
        ctk.CTkLabel(tf, text="Xác suất:").pack(side="left")
        self.slider_third_page = ctk.CTkSlider(
            tf, from_=10, to=70, number_of_steps=12, width=140,
            command=lambda v: self.lbl_third_val.configure(text=f"{int(v)}%"),
        )
        self.slider_third_page.set(35)
        self.slider_third_page.pack(side="left", padx=8)
        self.lbl_third_val = ctk.CTkLabel(tf, text="35%", width=38)
        self.lbl_third_val.pack(side="left")

    # ═══════════════════════════════════════════════════════════════
    # TAB: AI ENGINE
    # ═══════════════════════════════════════════════════════════════

    def _setup_tab_ai(self):
        t = self.tab_ai

        ctk.CTkLabel(t, text="Cấu hình Ollama Local",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(16, 12))

        ctk.CTkLabel(t, text="Ollama URL:").grid(row=1, column=0, sticky="w", padx=14, pady=(0, 4))
        self.entry_ollama_url = ctk.CTkEntry(t, width=380)
        self.entry_ollama_url.insert(0, cfg.OLLAMA_URL)
        self.entry_ollama_url.grid(row=2, column=0, sticky="w", padx=14)

        ctk.CTkLabel(t, text="Model:").grid(row=3, column=0, sticky="w", padx=14, pady=(14, 4))
        self.combo_model = ctk.CTkComboBox(t, values=[
            "qwen3:30b-a3b",
            "qwen3:8b",
            "gemma3:12b",
            "qwen2.5:7b",
            "qwen2.5-coder:7b",
            "qwen2.5-coder:14b",
            "llama3.1:8b",
            "mistral:7b",
        ], width=260)
        self.combo_model.set(cfg.OLLAMA_MODEL)
        self.combo_model.grid(row=4, column=0, sticky="w", padx=14)

        bf = ctk.CTkFrame(t, fg_color="transparent")
        bf.grid(row=5, column=0, sticky="w", padx=14, pady=16)
        self.btn_test_ollama = ctk.CTkButton(
            bf, text="🔌  Kiểm tra kết nối Ollama", width=220,
            command=self.test_ollama_connection,
        )
        self.btn_test_ollama.pack(side="left")
        self.btn_refresh_models = ctk.CTkButton(
            bf, text="Refresh model list", width=130,
            command=self.refresh_ollama_models,
        )
        self.btn_refresh_models.pack(side="left", padx=6)
        self.lbl_ollama_status = ctk.CTkLabel(bf, text="● Chưa kiểm tra", text_color="gray")
        self.lbl_ollama_status.pack(side="left", padx=14)

        self.entry_gen_kw = ctk.CTkEntry(bf, width=240, placeholder_text="từ khóa (trống = từ khóa đang track)")
        self.entry_gen_kw.pack(side="left", padx=(14, 0))
        self.btn_generate = ctk.CTkButton(
            bf, text="✍️  SINH BÀI",
            fg_color="#2a5a8a", hover_color="#3a7ab0",
            height=38, font=ctk.CTkFont(size=13, weight="bold"),
            command=self.run_generate_content,
        )
        self.btn_generate.pack(side="left", padx=(10, 0))

        ctk.CTkFrame(t, height=1, fg_color="#333").grid(row=6, column=0, columnspan=2, sticky="ew", padx=14, pady=8)

        info = (
            "AI Engine (Ollama) được dùng để:\n"
            "  •  Tạo Nhân cách người dùng  — tuổi, mood, tốc độ gõ, typo rate\n"
            "  •  Quyết định hành vi tìm kiếm  — pogo mấy lần, đọc snippet bao lâu\n"
            "  •  Sinh từ khóa biến thể  — mô phỏng user gõ sai trước khi sửa\n"
            "  •  Viết bình luận tự động  — phong cách khớp với tuổi + tâm trạng\n\n"
            "  ⚠️  Cần Ollama đang chạy local và đã pull model trước khi bắt đầu."
        )
        ctk.CTkLabel(t, text=info, justify="left", text_color="gray",
                     font=ctk.CTkFont(size=11)).grid(row=7, column=0, sticky="w", padx=14, pady=4)

    # ═══════════════════════════════════════════════════════════════
    # TAB: NUÔI NICK
    # ═══════════════════════════════════════════════════════════════

    def _setup_tab_warmup(self):
        t = self.tab_warmup

        self.chk_warmup = ctk.CTkCheckBox(
            t, text="BẬT NUÔI NICK  (warm-up lịch sử trình duyệt trước khi vào task SEO)",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.chk_warmup.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 12))

        ctk.CTkLabel(t, text="Loại trang warm-up:", text_color="gray").grid(row=1, column=0, sticky="w", padx=20, pady=(0, 8))

        self.chk_ytb = ctk.CTkCheckBox(t, text="YouTube  (xem video ngắn)")
        self.chk_ytb.select()
        self.chk_ytb.grid(row=2, column=0, sticky="w", padx=44, pady=4)

        self.chk_news = ctk.CTkCheckBox(t, text="Đọc Báo  (vnexpress, dantri...)")
        self.chk_news.select()
        self.chk_news.grid(row=3, column=0, sticky="w", padx=44, pady=4)

        self.chk_wiki = ctk.CTkCheckBox(t, text="Wikipedia")
        self.chk_wiki.select()
        self.chk_wiki.grid(row=4, column=0, sticky="w", padx=44, pady=4)

        self.chk_shop = ctk.CTkCheckBox(t, text="Shopping  (shopee, lazada...)")
        self.chk_shop.select()
        self.chk_shop.grid(row=5, column=0, sticky="w", padx=44, pady=4)

        self.chk_fb = ctk.CTkCheckBox(t, text="Facebook")
        self.chk_fb.select()
        self.chk_fb.grid(row=6, column=0, sticky="w", padx=44, pady=4)

        self.chk_ig = ctk.CTkCheckBox(t, text="Instagram")
        self.chk_ig.select()
        self.chk_ig.grid(row=7, column=0, sticky="w", padx=44, pady=4)

        ctk.CTkLabel(
            t,
            text=(
                "ℹ️  Nuôi Nick khác với Warm-up trước Google (tab Hành Vi SEO).\n"
                "    Nuôi Nick chạy trước toàn bộ task — xây dựng lịch sử duyệt web dài hạn.\n"
                "    Warm-up trước Google chỉ ghé 1 trang VN ngắn ngay trước khi search."
            ),
            text_color="gray", font=ctk.CTkFont(size=11), justify="left",
        ).grid(row=8, column=0, sticky="w", padx=20, pady=20)

    # ═══════════════════════════════════════════════════════════════
    # TAB: XẾP HẠNG (RANK TRACKER)
    # ═══════════════════════════════════════════════════════════════

    def _setup_tab_rank(self):
        t = self.tab_rank
        ctk.CTkLabel(
            t, text="Kiểm tra vị trí từ khóa trên Google (kết quả organic, top 100).",
            font=ctk.CTkFont(size=12), text_color="gray",
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 4))

        rf = ctk.CTkFrame(t, fg_color="transparent")
        rf.grid(row=1, column=0, sticky="w", padx=20, pady=6)
        self.btn_rank_check = ctk.CTkButton(
            rf, text="🔄  KIỂM TRA XẾP HẠNG NGAY",
            fg_color="#1a5a7a", hover_color="#2478a8",
            height=38, width=250, font=ctk.CTkFont(size=13, weight="bold"),
            command=self.run_rank_check_now,
        )
        self.btn_rank_check.pack(side="left")
        self.btn_gsc = ctk.CTkButton(
            rf, text="📊  LẤY DỮ LIỆU SEARCH CONSOLE",
            fg_color="#1a5a7a", hover_color="#2478a8",
            height=38, font=ctk.CTkFont(size=13, weight="bold"),
            command=self.run_gsc_fetch_now,
        )
        self.btn_gsc.pack(side="left", padx=(16, 0))
        self.btn_export = ctk.CTkButton(
            rf, text="📤  XUẤT CSV",
            fg_color="#3a6b35", hover_color="#4a8544",
            height=38, font=ctk.CTkFont(size=13, weight="bold"),
            command=self.export_csv_now,
        )
        self.btn_export.pack(side="left", padx=(16, 0))
        self.btn_alert_test = ctk.CTkButton(
            rf, text="🧪  GỬI THỬ BÁO ĐỘNG",
            fg_color="#6a4a8a", hover_color="#7d5aa3",
            height=38, font=ctk.CTkFont(size=13, weight="bold"),
            command=self.run_alert_preview,
        )
        self.btn_alert_test.pack(side="left", padx=(16, 0))
        self.btn_audit = ctk.CTkButton(
            rf, text="🔍  AUDIT SITE",
            fg_color="#8a5a1a", hover_color="#a8721f",
            height=38, font=ctk.CTkFont(size=13, weight="bold"),
            command=self.run_site_audit,
        )
        self.btn_audit.pack(side="left", padx=(16, 0))
        self.btn_backlinks = ctk.CTkButton(
            rf, text="🔗  CHECK BACKLINK",
            fg_color="#1a6b5a", hover_color="#248a74",
            height=38, font=ctk.CTkFont(size=13, weight="bold"),
            command=self.run_backlink_check,
        )
        self.btn_backlinks.pack(side="left", padx=(16, 0))
        rf2 = ctk.CTkFrame(t, fg_color="transparent")
        rf2.grid(row=1, column=0, sticky="w", padx=20, pady=(2, 0))
        self.btn_htmlreport = ctk.CTkButton(
            rf2, text="🌐  XUẤT REPORT HTML",
            fg_color="#1a5a7a", hover_color="#2478a8",
            height=32, font=ctk.CTkFont(size=12, weight="bold"),
            command=self.run_html_report_now,
        )
        self.btn_htmlreport.pack(side="left")
        self.btn_intlinks = ctk.CTkButton(
            rf2, text="🧩  GỢI Ý LINK NỘI BỘ",
            fg_color="#1a5a7a", hover_color="#2478a8",
            height=32, font=ctk.CTkFont(size=12, weight="bold"),
            command=self.run_internal_links_now,
        )
        self.btn_intlinks.pack(side="left", padx=(16, 0))
        self.btn_actions = ctk.CTkButton(
            rf2, text="📝  VIỆC ƯU TIÊN TỪ AUDIT",
            fg_color="#8a5a1a", hover_color="#a8721f",
            height=32, font=ctk.CTkFont(size=12, weight="bold"),
            command=self.run_audit_actions_now,
        )
        self.btn_actions.pack(side="left", padx=(16, 0))
        self.btn_doctor = ctk.CTkButton(
            rf2, text="🩺  DOCTOR",
            fg_color="#5a5a6a", hover_color="#6d6d80",
            height=32, font=ctk.CTkFont(size=12, weight="bold"),
            command=self.run_doctor_now,
        )
        self.btn_doctor.pack(side="left", padx=(16, 0))
        self.btn_planprog = ctk.CTkButton(
            rf2, text="📋  PLAN PROGRESS",
            fg_color="#1a5a7a", hover_color="#2478a8",
            height=32, font=ctk.CTkFont(size=12, weight="bold"),
            command=self.run_plan_progress_now,
        )
        self.btn_planprog.pack(side="left", padx=(16, 0))
        self.btn_gscalerts = ctk.CTkButton(
            rf2, text="📉  GSC ALERTS",
            fg_color="#8a3a35", hover_color="#a8483f",
            height=32, font=ctk.CTkFont(size=12, weight="bold"),
            command=self.run_gsc_alerts_now,
        )
        self.btn_gscalerts.pack(side="left", padx=(16, 0))
        self.btn_clustgsc = ctk.CTkButton(
            rf2, text="⚖️  CỤM × GSC",
            fg_color="#1a5a7a", hover_color="#2478a8",
            height=32, font=ctk.CTkFont(size=12, weight="bold"),
            command=self.run_cluster_gsc_now,
        )
        self.btn_clustgsc.pack(side="left", padx=(16, 0))
        self.btn_gsctrend = ctk.CTkButton(
            rf2, text="📊  GSC TREND",
            fg_color="#1a5a7a", hover_color="#2478a8",
            height=32, font=ctk.CTkFont(size=12, weight="bold"),
            command=self.run_gsc_trend_now,
        )
        self.btn_gsctrend.pack(side="left", padx=(16, 0))
        self.btn_ctrops = ctk.CTkButton(
            rf2, text="🎯  CTR OPS",
            fg_color="#1a5a7a", hover_color="#2478a8",
            height=32, font=ctk.CTkFont(size=12, weight="bold"),
            command=self.run_ctr_ops_now,
        )
        self.btn_ctrops.pack(side="left", padx=(16, 0))
        self.btn_chart = ctk.CTkButton(
            rf2, text="📈  CHART",
            fg_color="#1a5a7a", hover_color="#2478a8",
            height=32, font=ctk.CTkFont(size=12, weight="bold"),
            command=self.run_chart_now,
        )
        self.btn_chart.pack(side="left", padx=(16, 0))
        self.lbl_rank_last = ctk.CTkLabel(rf, text="", text_color="gray")
        self.lbl_rank_last.pack(side="left", padx=16)
        self.lbl_alert_mode = ctk.CTkLabel(rf, text="", text_color="gray")
        self.lbl_alert_mode.pack(side="left", padx=(0, 16))

        self.txt_rank = ctk.CTkTextbox(t, font=ctk.CTkFont(family="Consolas", size=12))
        self.txt_rank.grid(row=2, column=0, sticky="nsew", padx=20, pady=(4, 4))
        t.grid_rowconfigure(2, weight=1)
        t.grid_columnconfigure(0, weight=1)

        # F10k — CHART: canvas vẽ đường hạng thật (ẩn/dấu theo nút)
        import tkinter as tk
        self.canvas_chart = tk.Canvas(t, height=220, bg="#181820",
                                      highlightthickness=0)
        self.canvas_chart.grid(row=2, column=0, sticky="nsew", padx=20, pady=(4, 4))
        self.canvas_chart.grid_remove()  # mặc định ẩn — texttrước

        sf = ctk.CTkFrame(t)
        sf.grid(row=3, column=0, sticky="nsew", padx=20, pady=(4, 4))
        head = ctk.CTkFrame(sf, fg_color="transparent")
        head.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(head, text="Từ khóa đề xuất từ Search Console (chưa theo dõi)",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.btn_kw_suggest = ctk.CTkButton(
            head, text="💡  TỪ KHÓA ĐỀ XUẤT", width=180, height=28,
            fg_color="#1a5a7a", hover_color="#2478a8",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.refresh_keyword_suggestions,
        )
        self.btn_kw_suggest.pack(side="right")
        self.kw_suggest_frame = ctk.CTkScrollableFrame(sf, height=160, fg_color="transparent")
        self.kw_suggest_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._kw_suggest_note("Chưa có danh sách — bấm '💡 TỪ KHÓA ĐỀ XUẤT' (cần dữ liệu Search Console).")

        sch = ctk.CTkFrame(t)
        sch.grid(row=4, column=0, sticky="nsew", padx=20, pady=(4, 16))
        sch_head = ctk.CTkFrame(sch, fg_color="transparent")
        sch_head.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(sch_head, text="🗓  LỊCH TỰ ĐỘNG — do Windows Task Scheduler điều khiển",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.btn_scheduler_refresh = ctk.CTkButton(
            sch_head, text="🧾  LOAD TRẠNG THÁI", width=180, height=28,
            fg_color="#1a5a7a", hover_color="#2478a8",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.refresh_scheduler_status,
        )
        self.btn_scheduler_refresh.pack(side="right")
        self.txt_scheduler = ctk.CTkTextbox(
            sch, height=140, font=ctk.CTkFont(family="Consolas", size=11))
        self.txt_scheduler.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._refresh_alert_mode_label()
        self._refresh_rank_report()
        self.refresh_scheduler_status()

    def refresh_scheduler_status(self):
        """Đọc data/scheduler_state.json — GUI là process khác nên không thấy gì in-process.
        Chỉ xem, không bấm: job chạy từ GUI sẽ không có log của Task Scheduler."""
        from utils.scheduler import format_status
        try:
            lines = format_status()
        except Exception as e:
            lines = [f"[Scheduler] Không đọc được trạng thái: {type(e).__name__}: {e}"]
        self.txt_scheduler.delete("0.0", "end")
        self.txt_scheduler.insert("0.0", "\n".join(lines))

    # ── F10 — tab 🧰 Phân Tích: mỗi nút chạy 1 lệnh CLI báo cáo đọc-only ──
    TOOLS_LABELS = {
        "doctor-net": ("🩺  DOCTOR --net", "run_extra_cli"),
        "page-impact": ("⚖️  PAGE IMPACT", "--page-impact"),
        "content-gap": ("🕳️  CONTENT GAP", "--content-gap"),
        "refresh-diff": ("🔁  REFRESH DIFF", "--refresh-diff"),
        "content-brief": ("📰  CONTENT BRIEF", "--content-brief"),
        "daily-report": ("🌅  DAILY REPORT", "--daily-report"),
    }
    TOOLS_DESC = {
        "doctor-net": "Kiểm tra môi trường kèm ping Ollama (--doctor --net)",
        "page-impact": "Sức nặng theo trang: trang VIP, phơi không ai click (--page-impact)",
        "content-gap": "Query Google phơi mà site chưa có trang riêng (--content-gap)",
        "refresh-diff": "Bài nên refresh đã đến bước nào (--refresh-diff)",
        "content-brief": "Brief trộn dữ liệu cho 1 từ khóa dưới ô nhập (--content-brief)",
        "daily-report": "Báo cáo buổi sáng gộp 1 tin (--daily-report)",
    }

    def _setup_tab_tools(self):
        t = self.tab_tools
        ctk.CTkLabel(
            t, text="Phân tích đọc-only — chạy lệnh CLI và in kết quả vào System Logs bên dưới.",
            font=ctk.CTkFont(size=12), text_color="gray",
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 4))

        self.entry_brief_kw = ctk.CTkEntry(t, width=340, height=32,
                                           placeholder_text="Từ khóa cho CONTENT BRIEF (vd: nối mi quận 2)")
        self.entry_brief_kw.grid(row=1, column=0, sticky="w", padx=20, pady=(4, 8))

        tf = ctk.CTkFrame(t, fg_color="transparent")
        tf.grid(row=2, column=0, sticky="w", padx=20, pady=6)
        for i, tag in enumerate(("doctor-net", "page-impact", "content-gap",
                                 "refresh-diff", "content-brief", "daily-report")):
            label = self.TOOLS_LABELS[tag][0]
            btn = ctk.CTkButton(tf, text=label, height=32, width=150,
                                fg_color="#1a5a7a", hover_color="#2478a8",
                                font=ctk.CTkFont(size=12, weight="bold"),
                                command=lambda tag=tag: self.run_tool_now(tag))
            btn.grid(row=i // 3, column=i % 3, padx=(0 if i % 3 == 0 else 12, 0),
                     pady=(0, 8), sticky="w")
            setattr(self, f"btn_tool_{tag}", btn)
            note = ctk.CTkLabel(tf, text=self.TOOLS_DESC[tag],
                                font=ctk.CTkFont(size=10), text_color="gray", anchor="w")
            note.grid(row=(i // 3) * 10 + 1, column=i % 3, sticky="w", padx=2, pady=(0, 6))

    def run_tool_now(self, tag: str):
        """Nút tab 🧰 — mô hình của các nút khác: guard → disable → thread → enable."""
        if self._tools_running.get(tag):
            return
        if tag == "content-brief" and not (self.entry_brief_kw.get() or "").strip():
            print("[Tools] Nhập từ khóa ở ô trên rồi mới bấm CONTENT BRIEF.")
            return
        self._tools_running[tag] = True
        btn = getattr(self, f"btn_tool_{tag}", None)
        if btn is not None:
            btn.configure(state="disabled", text="⏳ Đang chạy...")
        threading.Thread(target=self._tool_worker, args=(tag,), daemon=True).start()

    def _tool_worker(self, tag: str):
        try:
            if tag == "doctor-net":
                from utils.doctor import run_doctor_cli
                run_doctor_cli(net=True)
            elif tag == "content-brief":
                from utils.content_brief import run_content_brief_cli
                run_content_brief_cli(keyword=self.entry_brief_kw.get().strip(),
                                      save_to_disk=True)
            else:
                from utils.dispatch_tools import dispatch_tools
                dispatch_tools(tag)
        except Exception as e:
            print(f"[Tools] Lỗi {tag}: {type(e).__name__}: {e}")
        finally:
            self._tools_running[tag] = False
            btn = getattr(self, f"btn_tool_{tag}", None)
            label = self.TOOLS_LABELS[tag][0]
            if btn is not None:
                self.after(0, lambda: btn.configure(state="normal", text=label))

    # ── T14 — tab 🧙 Cài Đặt Lần Đầu: trạng thái các bước bật nhà (chỉ đọc) ──
    def _setup_tab_wizard(self):
        t = self.tab_wizard
        ctk.CTkLabel(
            t, text="Wizard bật nhà cho owner mới — hiển thị bước nào đã xong, còn thiếu gì. "
                    "Chỉ ĐỌC file/config: wizard không cấu hình gì thay bạn, không gửi request nào.",
            font=ctk.CTkFont(size=12), text_color="gray", justify="left",
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 6))

        wf = ctk.CTkFrame(t, fg_color="transparent")
        wf.grid(row=1, column=0, sticky="w", padx=20, pady=6)
        self.btn_wizard = ctk.CTkButton(
            wf, text="🧙  KIỂM TRA LẠI TỪNG BƯỚC",
            fg_color="#1a5a7a", hover_color="#2478a8",
            height=36, font=ctk.CTkFont(size=12, weight="bold"),
            command=self.run_wizard_now,
        )
        self.btn_wizard.pack(side="left")
        self.btn_wizard_docs = ctk.CTkButton(
            wf, text="📖  MỞ CHECKLIST DOCS", fg_color="#5a5a6a", hover_color="#6d6d80",
            height=36, font=ctk.CTkFont(size=12, weight="bold"),
            command=self.open_wizard_docs,
        )
        self.btn_wizard_docs.pack(side="left", padx=(12, 0))
        self.btn_firstrun = ctk.CTkButton(
            wf, text="🌱  FIRST RUN (chạy thử từng bước)",
            fg_color="#2a6b35", hover_color="#3a8544",
            height=36, font=ctk.CTkFont(size=12, weight="bold"),
            command=self.run_first_run_now,
        )
        self.btn_firstrun.pack(side="left", padx=(12, 0))

        self.lbl_wizard_summary = ctk.CTkLabel(
            t, text="", font=ctk.CTkFont(size=13, weight="bold"), anchor="w")
        self.lbl_wizard_summary.grid(row=2, column=0, sticky="w", padx=20, pady=(10, 4))

        self.txt_wizard = ctk.CTkTextbox(
            t, font=ctk.CTkFont(family="Consolas", size=12), height=300)
        self.txt_wizard.grid(row=3, column=0, sticky="nsew", padx=20, pady=(4, 12))
        t.grid_rowconfigure(3, weight=1)

        self._wizard_refresh(silent=True)

    def _wizard_refresh(self, silent: bool = False):
        """Chạy wizard_steps() trên main thread và vẽ lại bảng. silent=True: không đếm lỗi."""
        try:
            from utils.setup_wizard import STEP_LABELS, ready_summary, wizard_steps
            steps = wizard_steps()
            ok, miss, warn, skip = "✓", "✗", "!", "—"
            lines = [f"  {'BƯỚC':<34}{'TRẠNG THÁI':<8}HIỆN TRẠNG", "  " + "─" * 94]
            for s in steps:
                mark = ok if s["done"] else (skip if s["optional"] and not s["detail"].startswith(("ALERTS", "WP đ")) else warn)
                if s["optional"] and s["done"]:
                    mark = ok
                lines.append(f"  {STEP_LABELS[s['key']]:<34}{mark:<8}{s['detail'][:64]}")
                if not s["done"] and s["hint"]:
                    lines.append(f"       ↳ {s['hint']}")
            lines.append("  " + "─" * 94)
            lines.append(f"  {ready_summary(steps)}")
            lines.append('  Chi tiết từng bước: docs/CHECKLIST_FIRST_RUN.md — tab 🧰 Phân Tích chạy được mỗi lệnh qua nút.')
            self.txt_wizard.delete("0.0", END)
            self.txt_wizard.insert("0.0", "\n".join(lines))
            self.lbl_wizard_summary.configure(text=ready_summary(steps))
        except Exception as e:
            if not silent:
                print(f"[Wizard] Lỗi vẽ lại: {type(e).__name__}: {e}")

    def run_wizard_now(self):
        """🧙: nạp wizard_steps từ thread rồi vẽ lại trên main thread — nút disable khi chạy."""
        if self._wizard_running:
            return
        self._wizard_running = True
        self.btn_wizard.configure(state="disabled", text="⏳ Đang kiểm tra...")
        threading.Thread(target=self._wizard_worker, daemon=True).start()

    def _wizard_worker(self):
        try:
            # wizard_steps đọc file/config — đọc trong thread để không chặn UI,
            # vẽ trên main thread qua after như mọi worker khác.
            from utils.setup_wizard import wizard_steps
            steps = wizard_steps()
            self.after(0, lambda: self._wizard_draw(steps))
        except Exception as e:
            print(f"[Wizard] Lỗi: {type(e).__name__}: {e}")
        finally:
            self._wizard_running = False
            self.after(0, lambda: self.btn_wizard.configure(
                state="normal", text="🧙  KIỂM TRA LẠI TỪNG BƯỚC"))

    def _wizard_draw(self, steps):
        """Vẽ bảng wizard từ `steps` đã nạp ở worker (main thread)."""
        from utils.setup_wizard import STEP_LABELS, ready_summary
        ok, miss, opt = "✓", "✗", "—"
        lines = [f"  {'BƯỚC':<34}{'XONG':<6}HIỆN TRẠNG", "  " + "─" * 94]
        for s in steps:
            mark = ok if s["done"] else (opt if s["optional"] else miss)
            lines.append(f"  {STEP_LABELS[s['key']]:<34}{mark:<6}{s['detail'][:70]}")
            if not s["done"] and s["hint"]:
                lines.append(f"       ↳ {s['hint']}")
        lines.append("  " + "─" * 94)
        lines.append(f"  {ready_summary(steps)}")
        lines.append("  Chi tiết từng bước: docs/CHECKLIST_FIRST_RUN.md — tab 🧰 Phân Tích có nút chạy sẵn.")
        self.txt_wizard.delete("0.0", END)
        self.txt_wizard.insert("0.0", "\n".join(lines))
        self.lbl_wizard_summary.configure(text=ready_summary(steps))

    def open_wizard_docs(self):
        """📖: mở docs/CHECKLIST_FIRST_RUN.md bằng chương trình mặc định của Windows."""
        import os as _os
        path = _os.path.join(site_paths.ROOT, "docs", "CHECKLIST_FIRST_RUN.md")
        if not _os.path.isfile(path):
            print("[Wizard] Không tìm thấy docs/CHECKLIST_FIRST_RUN.md trong project.")
            return
        try:
            _os.startfile(path)  # Windows: open bằng app mặc định
        except Exception as e:
            print(f"[Wizard] Không mở được file docs: {e}")

    def run_first_run_now(self):
        """🌱: chạy thử tuần tự wizard→doctor→audit→export (T15) — audit crawl thật nên thread."""
        if self._firstrun_running:
            return
        if self.is_running or getattr(self, "_audit_running", False):
            print("[FirstRun] ⚠️ Bot/audit đang chạy — đừng chồng crawl lên nhau.")
            return
        self._firstrun_running = True
        self.btn_firstrun.configure(state="disabled", text="⏳ Đang chạy thử...")
        threading.Thread(target=self._firstrun_worker, daemon=True).start()

    def _firstrun_worker(self):
        try:
            from utils.first_run import run_first_run_cli
            run_first_run_cli()  # in thẳng vào System Logs (stdout được redirect)
        except Exception as e:
            print(f"[FirstRun] Lỗi: {type(e).__name__}: {e}")
        finally:
            self._firstrun_running = False
            self.after(0, lambda: self.btn_firstrun.configure(
                state="normal", text="🌱  FIRST RUN (chạy thử từng bước)"))

    # ── T17 — tab 📢 AI Nói Gì: AEO paste tay + bảng keyword × engine (chỉ đọc) ──
    def _setup_tab_aeo(self):
        t = self.tab_aeo
        ctk.CTkLabel(
            t, text="AI trả lời có nhắc brand mình không? Hỏi ChatGPT/Gemini/Perplexity bằng 1 từ khóa, "
                    "copy câu trả lời dán vào khung dưới rồi bấm PHÂN TÍCH — tool chỉ đọc text, gửi 0 request.",
            font=ctk.CTkFont(size=12), text_color="gray", justify="left", wraplength=900,
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 6))

        af = ctk.CTkFrame(t, fg_color="transparent")
        af.grid(row=1, column=0, sticky="w", padx=20, pady=6)
        self.btn_aeo_refresh = ctk.CTkButton(
            af, text="📢  KIỂM TRA LẠI BẢNG ĐỀU (REFRESH)",
            fg_color="#1a5a7a", hover_color="#2478a8",
            height=36, font=ctk.CTkFont(size=12, weight="bold"),
            command=self.run_aeo_now,
        )
        self.btn_aeo_refresh.pack(side="left")
        self.btn_aeo_report = ctk.CTkButton(
            af, text="📄  IN BÁO CÁO AEO (CHI TIẾT)",
            fg_color="#5a5a6a", hover_color="#6d6d80",
            height=36, font=ctk.CTkFont(size=12, weight="bold"),
            command=self.run_aeo_report,
        )
        self.btn_aeo_report.pack(side="left", padx=(12, 0))

        self.lbl_aeo_kw = ctk.CTkLabel(af, text="Từ khóa:",
                                       font=ctk.CTkFont(size=12), anchor="w")
        self.lbl_aeo_kw.pack(side="left", padx=(24, 4))
        self.entry_aeo_kw = ctk.CTkEntry(af, width=260, height=36,
                                         placeholder_text="vd: nối mi quận 2")
        self.entry_aeo_kw.pack(side="left")
        self.lbl_aeo_engine = ctk.CTkLabel(af, text="Engine:",
                                           font=ctk.CTkFont(size=12), anchor="w")
        self.lbl_aeo_engine.pack(side="left", padx=(24, 4))
        self.entry_aeo_engine = ctk.CTkEntry(af, width=120, height=36,
                                             placeholder_text="ChatGPT")
        self.entry_aeo_engine.pack(side="left")

        self.txt_aeo_answer = ctk.CTkTextbox(
            t, font=ctk.CTkFont(family="Segoe UI", size=12), height=150)
        self.txt_aeo_answer.grid(row=2, column=0, sticky="nsew", padx=20, pady=(4, 6))
        ctk.CTkLabel(
            t, text="↓ dán nội dung câu trả lời AI vào khung trên + điền từ khóa + engine → bấm PHÂN TÍCH",
            font=ctk.CTkFont(size=10), text_color="gray",
        ).grid(row=3, column=0, sticky="w", padx=20)

        self.btn_aeo_analyze = ctk.CTkButton(
            t, text="🔍  PHÂN TÍCH & LƯU", fg_color="#2a6b35", hover_color="#3a8544",
            height=36, font=ctk.CTkFont(size=12, weight="bold"),
            command=self.run_aeo_analyze_now,
        )
        self.btn_aeo_analyze.grid(row=4, column=0, sticky="w", padx=20, pady=8)

        self.txt_aeo_matrix = ctk.CTkTextbox(
            t, font=ctk.CTkFont(family="Consolas", size=12), height=280)
        self.txt_aeo_matrix.grid(row=5, column=0, sticky="nsew", padx=20, pady=(4, 12))
        t.grid_rowconfigure(5, weight=1)

        self._aeo_refresh(silent=True)

    def _aeo_refresh(self, silent: bool = False):
        """Nạp ai_matrix() trên main thread + vẽ bảng. silent=True: không đếm lỗi."""
        try:
            lines = self._aeo_matrix_lines()
            self.txt_aeo_matrix.delete("0.0", END)
            self.txt_aeo_matrix.insert("0.0", "\n".join(lines))
        except Exception as e:
            if not silent:
                print(f"[AEO] Lỗi vẽ lại: {type(e).__name__}: {e}")

    def _aeo_matrix_lines(self) -> list:
        """Bảng keyword × engine từ ai_matrix() — pure: không chạm widgets."""
        from utils.aeo import ai_matrix
        matrix = ai_matrix()
        header = [f"  {'Từ khóa':<38}{'Engine':<14}{'Nhắc brand':<12}{'Ngày đo'}",
                  "  " + "─" * 94]
        if not matrix:
            return header + [
                "  Chưa có dữ liệu AEO.",
                "  Mỗi ngày: hỏi 1 AI engine 1 câu theo từng từ khóa → copy câu trả lời",
                "  dán vào khung trên → điền từ khóa + engine → bấm PHÂN TÍCH & LƯU.",
            ]
        # engine nào đang thiếu (chưa hỏi) cũng ra hàng '—' — nhìn phát biết chỗ chưa đo,
        # lấy hợp các engine trông thấy + 3 engine phổ thường hay hỏi
        engines = sorted({e for per_kw in matrix.values() for e in per_kw}
                         | {"ChatGPT", "Gemini", "Perplexity"})
        lines = header
        for kw in sorted(matrix):
            for engine in engines:
                info = matrix[kw].get(engine)
                if info is None:
                    lines.append(f"  {kw[:38]:<38}{engine[:13]:<14}{'—':<12}{'—'}")
                    continue
                mark = "✓" if info["mentioned"] else "✗"
                n = f"{info['mentions']} lần" if info["mentions"] > 1 else "có"
                lines.append(f"  {kw[:38]:<38}{engine[:13]:<14}{mark + ' ' + n:<12}"
                             f"{info.get('date', '')}")
        return lines

    def run_aeo_now(self):
        """📢 REFRESH BẢNG: nạp matrix ở thread (đọc file) rồi vẽ trên main thread."""
        if self._aeo_running:
            return
        self._aeo_running = True
        self.btn_aeo_refresh.configure(state="disabled", text="⏳ Đang nạp...")
        threading.Thread(target=self._aeo_worker, daemon=True).start()

    def _aeo_worker(self):
        try:
            lines = self._aeo_matrix_lines()
            self.after(0, lambda: self._aeo_draw(lines))
        except Exception as e:
            print(f"[AEO] Lỗi: {type(e).__name__}: {e}")
        finally:
            self._aeo_running = False
            self.after(0, lambda: self.btn_aeo_refresh.configure(
                state="normal", text="📢  KIỂM TRA LẠI BẢNG ĐỀU (REFRESH)"))

    def _aeo_draw(self, lines):
        self.txt_aeo_matrix.delete("0.0", END)
        self.txt_aeo_matrix.insert("0.0", "\n".join(lines))

    def run_aeo_report(self):
        """📄 IN BÁO CÁO: build_report() trả string — in vào System Logs qua worker."""
        if self._aeo_running:
            return
        self._aeo_running = True
        self.btn_aeo_report.configure(state="disabled", text="⏳ Đang đọc...")
        threading.Thread(target=self._aeo_report_worker, daemon=True).start()

    def _aeo_report_worker(self):
        try:
            from utils.aeo import build_report
            print(build_report())
        except Exception as e:
            print(f"[AEO] Lỗi báo cáo: {type(e).__name__}: {e}")
        finally:
            self._aeo_running = False
            self.after(0, lambda: self.btn_aeo_report.configure(
                state="normal", text="📄  IN BÁO CÁO AEO (CHI TIẾT)"))

    def run_aeo_analyze_now(self):
        """🔍 PHÂN TÍCH & LƯU: validate input trước, sau đó thread (ghi file history)."""
        if self._aeo_running:
            return
        kw = (self.entry_aeo_kw.get() or "").strip()
        if not kw:
            print("[AEO] Điền từ khóa đang theo dõi rồi mới phân tích.")
            return
        answer = self.txt_aeo_answer.get("0.0", END).strip()
        if not answer:
            print("[AEO] Dán câu trả lời AI vào khung trên rồi mới phân tích.")
            return
        self._aeo_running = True
        self.btn_aeo_analyze.configure(state="disabled", text="⏳ Đang phân tích...")
        threading.Thread(target=self._aeo_analyze_worker,
                         args=(answer, kw, self.entry_aeo_engine.get()), daemon=True).start()

    def _aeo_analyze_worker(self, answer: str, kw: str, engine: str):
        try:
            from utils.aeo import add_result
            brands = getattr(cfg, "AEO_BRANDS", [])
            record = add_result(answer, brands=brands,
                                engine=(engine or "ChatGPT").strip() or "ChatGPT",
                                keyword=kw)
            mark = "✓ nhắc" if record["mentioned"] else "✗ không nhắc"
            print(f"[AEO] {mark} brand trong \"{record['keyword']}\" "
                  f"({record['engine']}, ngày {record['date']}) — đã lưu history.")
            lines = self._aeo_matrix_lines()
            self.after(0, lambda: self._aeo_draw(lines))
            self.after(0, lambda: self.txt_aeo_answer.delete("0.0", END))
        except Exception as e:
            print(f"[AEO] Lỗi phân tích: {type(e).__name__}: {e}")
        finally:
            self._aeo_running = False
            self.after(0, lambda: self.btn_aeo_analyze.configure(
                state="normal", text="🔍  PHÂN TÍCH & LƯU"))

    # ── F10k — CHART: đường hạng thật bằng canvas (hạng nhỏ = ở trên) ──
    def run_chart_now(self):
        """📈: vẽ hạng 8 mốc gần nhất vào canvas — toggle hiện/ẩn."""
        if self._chart_running:
            return
        if self._chart_visible:
            self._chart_visible = False
            self.canvas_chart.grid_remove()
            self.txt_rank.grid()
            self.btn_chart.configure(text="📈  CHART")
            return
        self._chart_running = True
        self.btn_chart.configure(state="disabled", text="⏳ Đang vẽ...")
        threading.Thread(target=self._chart_worker, daemon=True).start()

    def _chart_worker(self):
        try:
            from utils.rank_tracker import _load_history
            from utils.gui_charts import rank_series_from_history
            series = rank_series_from_history(_load_history())
            self.after(0, lambda: self._chart_render(series))
        except Exception as e:
            print(f"[Chart] Lỗi: {type(e).__name__}: {e}")
        finally:
            self._chart_running = False
            self.after(0, lambda: self.btn_chart.configure(
                state="normal", text="📈  CHART"))

    def _chart_render(self, series: dict):
        """Chạy trong main thread — dịch items → create_* trên canvas."""
        self._chart_visible = True
        try:
            self.txt_rank.grid_remove()
            self.canvas_chart.grid()
        except Exception:
            pass
        cvs = self.canvas_chart
        cvs.delete("all")
        w = max(cvs.winfo_width() or 700, 400)
        h = max(cvs.winfo_height() or 220, 160)
        if not series:
            cvs.create_text(w // 2, h // 2, text="Chưa có hạng để vẽ — chạy KIỂM TRA XẾP HẠNG trước",
                            fill="#8a8a96", font=("Consolas", 11))
            return
        from utils.gui_charts import chart_items
        items = chart_items(series, w, h)
        seen_grid = set()
        for it in items:
            kind = it[0]
            if kind == "grid":
                _, y, txt = it
                if y not in seen_grid:
                    seen_grid.add(y)
                    cvs.create_line(20, y, w - 12, y, fill="#3a3a44")
                    cvs.create_text(8, y, text=txt, fill="#cfcfd8", anchor="e",
                                    font=("Consolas", 9))
            elif kind == "line":
                cvs.create_line(it[2], it[3], it[4], it[5],
                                fill=it[1], width=2, smooth=True)
            elif kind == "dot":
                x, y, r = it[1], it[2], 3
                cvs.create_oval(x - r, y - r, x + r, y + r, fill=it[1], outline="")
            elif kind == "label":
                if len(it) >= 5:
                    x, y, txt, anchor = it[1], it[2], it[3], "start"
                    cvs.create_text(x, y, text=txt, fill="#cfcfd8", anchor=anchor,
                                    font=("Consolas", 9))

    def _refresh_alert_mode_label(self):
        from utils.alerts import delivery_mode
        try:
            mode = delivery_mode()
        except Exception as e:
            mode = f"console (lỗi đọc cấu hình: {e})"
        self.lbl_alert_mode.configure(
            text="Cảnh báo: Telegram" if mode == "telegram" else "Cảnh báo: console")

    def run_alert_preview(self):
        """Nút 🧪: gửi một tin thử qua kênh đang cấu hình, không đụng state cảnh báo thật."""
        if getattr(self, "_alert_running", False):
            return
        self._alert_running = True
        try:
            self.btn_alert_test.configure(state="disabled", text="⏳ Đang gửi...")
        except Exception:
            pass
        threading.Thread(target=self._alert_preview_worker, daemon=True).start()

    def _alert_preview_worker(self):
        try:
            from utils.alerts import delivery_mode, is_configured, send
            mode = delivery_mode()
            if mode != "telegram":
                print(f"[Alert] Kênh hiện tại: console — {is_configured()[1]}")
            try:
                ok = send("🧪 Tin thử từ SEO Bot: kênh cảnh báo tụt hạng đang hoạt động.")
            except Exception as e:
                print(f"[Alert] ❌ Sender raise ngoài dự kiến: {type(e).__name__}: {e}")
                ok = False
            print("[Alert] ✅ Tin thử đã được thông báo." if ok
                  else "[Alert] ❌ Tin thử thất bại — xem mô tả ở trên.")
        except Exception as e:
            # Thiếu vòng này thì một lỗi bất ngờ để _alert_running kẹt ở True vĩnh viễn:
            # nút thử cảnh báo chết im lặng cho tới khi khởi động lại GUI.
            print(f"[Alert] ❌ Không chạy được tin thử: {type(e).__name__}: {e}")
        finally:
            self._alert_running = False
            self.after(0, self._finish_alert_preview)

    def _finish_alert_preview(self):
        """Trả nút về trạng thái bấm được — chạy trên main thread qua after()."""
        try:
            self.btn_alert_test.configure(state="normal", text="🧪  GỬI THỬ BÁO ĐỘNG")
        except Exception:
            pass
        self._refresh_alert_mode_label()

    def _refresh_rank_report(self):
        from utils.gsc_client import build_report as build_merged_report
        from utils.rank_tracker import _load_history, fmt_stamp
        try:
            # Báo cáo gộp SERP + GSC (tự fallback báo cáo rank khi chưa có dữ liệu GSC)
            report = build_merged_report()
        except Exception as e:
            report = f"Lỗi đọc lịch sử xếp hạng: {e}"
        self.txt_rank.delete("0.0", "end")
        self.txt_rank.insert("0.0", report)
        try:
            checks = _load_history().get("checks", {})
            if checks:
                self.lbl_rank_last.configure(
                    text=f"Lần check gần nhất: {fmt_stamp(sorted(checks.keys())[-1])}")
            else:
                self.lbl_rank_last.configure(text="Chưa check lần nào")
        except Exception:
            pass

    def run_rank_check_now(self):
        if self.is_running:
            print("[Rank] ⚠️ Bot đang chạy — không check xếp hạng song song (tránh CAPTCHA).")
            return
        if self._rank_running:
            return
        self._rank_running = True
        self.btn_rank_check.configure(state="disabled", text="⏳ Đang kiểm tra...")
        threading.Thread(target=self._rank_check_worker, daemon=True).start()

    def _rank_check_worker(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._rank_check_async())
            loop.close()
        except Exception as e:
            print(f"[Rank] Lỗi: {e}")
        finally:
            self._rank_running = False
            self.after(0, lambda: self.btn_rank_check.configure(
                state="normal", text="🔄  KIỂM TRA XẾP HẠNG NGAY"))
            self.after(0, self._refresh_rank_report)

    async def _rank_check_async(self):
        from utils.rank_tracker import can_run_check, mark_check_run, run_rank_check
        ok, reason = can_run_check()
        if not ok:
            print(f"[Rank] {reason}")
            return
        from core.browser_manager import BrowserManager
        manager = BrowserManager()
        try:
            # Dùng proxy đầu tiên trong ô Proxy (nếu có) — IP sạch giúp tránh CAPTCHA
            proxies = [p.strip() for p in self.txt_proxy.get("0.0", "end").strip().split("\n") if p.strip()]
            proxy = proxies[0] if proxies else None
            if proxy:
                print(f"[Rank] Dùng proxy: {proxy}")
            browser = await manager.launch_browser()
            page = await manager.create_context(browser, proxy_info=proxy, profile_id="rank_tracker")
            await run_rank_check(page, on_captcha=self._rank_solve_captcha)
            mark_check_run()
        finally:
            await manager.close()

    def _rank_solve_captcha(self, page) -> bool:
        """Dialog chờ người dùng giải CAPTCHA trong cửa sổ browser đang mở."""
        done = threading.Event()
        result = {"ok": False}

        def ask():
            import tkinter.messagebox as mb
            result["ok"] = mb.askretrycancel(
                "CAPTCHA phát hiện",
                "Google hiện CAPTCHA trong cửa sổ trình duyệt.\n\n"
                "Giải CAPTCHA xong → bấm 'Retry' để tiếp tục check.\n"
                "Bấm 'Cancel' để dừng và lưu kết quả một phần.")
            done.set()

        self.after(0, ask)
        done.wait()
        return result["ok"]

    # ─── SEARCH CONSOLE (thuần HTTP — không browser, không CAPTCHA) ──────

    def run_gsc_fetch_now(self):
        if self.is_running:
            print("[GSC] ⚠️ Bot đang chạy — không lấy dữ liệu Search Console song song.")
            return
        if self._gsc_running:
            return
        self._gsc_running = True
        self.btn_gsc.configure(state="disabled", text="⏳ Đang lấy...")
        threading.Thread(target=self._gsc_fetch_worker, daemon=True).start()

    def _gsc_fetch_sync(self):
        from utils.gsc_client import (
            can_run_fetch, mark_fetch_run, fetch_search_analytics, save_snapshot,
        )
        ok, reason = can_run_fetch()
        if not ok:
            print(f"[GSC] {reason}")
            return
        days = getattr(cfg, "GSC_LOOKBACK_DAYS", 28)
        rows = fetch_search_analytics(days)
        today = date.today()
        save_snapshot(rows, (today - timedelta(days=days - 1)).isoformat(), today.isoformat())
        mark_fetch_run()
        print(f"[GSC] ✅ Đã lưu {len(rows)} query — báo cáo gộp đã cập nhật.")
        from utils.alerts import hint_pending
        hint_pending()   # GUI không đi qua run_gsc_fetch_cli → nhắc ở đây

    def _gsc_fetch_worker(self):
        try:
            self._gsc_fetch_sync()
        except Exception as e:
            print(f"[GSC] Lỗi: {e}")
        finally:
            self._gsc_running = False
            self.after(0, lambda: self.btn_gsc.configure(
                state="normal", text="📊  LẤY DỮ LIỆU SEARCH CONSOLE"))
            self.after(0, self._refresh_rank_report)
            self.after(0, self.refresh_keyword_suggestions)

    # ─── EXPORT CSV (chỉ đọc file state — không browser, không network) ──────

    def export_csv_now(self):
        """Xuất lịch sử xếp hạng + snapshot Search Console ra CSV trong reports/."""
        from utils.exporter import export_gsc, export_rank
        for label, fn in (("xếp hạng", export_rank), ("Search Console", export_gsc)):
            try:
                path, n = fn()
            except Exception as e:
                print(f"[Export] ❌ Lỗi xuất dữ liệu {label}: {e}")
                continue
            print(f"[Export] ✅ Đã lưu {path} ({n} dòng {label})")
            if n == 0:
                print(f"[Export]    Chưa có dữ liệu {label} — file chỉ có tiêu đề.")

    # ═══════════════════════════════════════════════════════════════
    # AUDIT ON-PAGE (F6)
    # ═══════════════════════════════════════════════════════════════

    def run_site_audit(self):
        """Nút 🔍: crawl chính site bằng requests (HTML tĩnh) — không mở trình duyệt."""
        if self.is_running:
            print("[Audit] ⚠️ Bot đang treo máy — đợi phiên traffic xong rồi audit.")
            return
        if self._audit_running:
            return
        self._audit_running = True
        self.btn_audit.configure(state="disabled", text="⏳ Đang audit...")
        threading.Thread(target=self._site_audit_worker, daemon=True).start()

    def _site_audit_worker(self):
        try:
            from utils.site_auditor import run_audit_cli
            from utils.exporter import export_audit
            if run_audit_cli() == 0:
                path, n = export_audit()
                print(f"[Audit] 📤 Báo cáo CSV: {path} ({n} dòng)")
        except Exception as e:
            print(f"[Audit] Lỗi: {e}")
        finally:
            self._audit_running = False
            self.after(0, lambda: self.btn_audit.configure(
                state="normal", text="🔍  AUDIT SITE"))

    # ═══════════════════════════════════════════════════════════════
    # BACKLINK AUTO-CHECK (F7)
    # ═══════════════════════════════════════════════════════════════

    def run_backlink_check(self):
        """Nút 🔗: verify danh sách link đã đặt — requests tĩnh ≤5 luồng, không mở browser."""
        if self.is_running:
            print("[Backlink] ⚠️ Bot đang treo máy — đợi phiên traffic xong rồi check backlink.")
            return
        if self._backlinks_running:
            return
        self._backlinks_running = True
        self.btn_backlinks.configure(state="disabled", text="⏳ Đang check backlink...")
        threading.Thread(target=self._backlink_worker, daemon=True).start()

    def _backlink_worker(self):
        try:
            from utils.backlink_checker import run_backlink_check_cli
            from utils.exporter import export_backlinks
            if run_backlink_check_cli() == 0:
                path, n = export_backlinks()
                print(f"[Backlink] 📤 Báo cáo CSV: {path} ({n} dòng)")
        except Exception as e:
            print(f"[Backlink] Lỗi: {e}")
        finally:
            self._backlinks_running = False
            self.after(0, lambda: self.btn_backlinks.configure(
                state="normal", text="🔗  CHECK BACKLINK"))

    # ═══════════════════════════════════════════════════════════════
    # CÔNG CỤ BÁO CÁO / GỢI Ý — CLI làm phần nặng, GUI chỉ bấm và in ra
    # ═══════════════════════════════════════════════════════════════

    def run_html_report_now(self):
        """Nút 🌐: xuất data/report.html (SERP+GSC+Audit+Backlink) — thread nền."""
        if self._htmlreport_running:
            return
        self._htmlreport_running = True
        self.btn_htmlreport.configure(state="disabled", text="⏳ Đang xuất...")
        threading.Thread(target=self._htmlreport_worker, daemon=True).start()

    def _htmlreport_worker(self):
        try:
            from utils.html_report import run_html_report_cli, _report_path
            run_html_report_cli()
            print(f"[HTML] 💡 Mở bằng double-click file hoặc: start {_report_path()}")
        except Exception as e:
            print(f"[HTML] Lỗi: {type(e).__name__}: {e}")
        finally:
            self._htmlreport_running = False
            self.after(0, lambda: self.btn_htmlreport.configure(
                state="normal", text="🌐  XUẤT REPORT HTML"))

    def run_internal_links_now(self):
        """Nút 🧩: gợi ý link nội bộ từ audit + rank history — chỉ đọc, không tự sửa."""
        if self._intlinks_running:
            return
        self._intlinks_running = True
        self.btn_intlinks.configure(state="disabled", text="⏳ Đang phân tích...")
        threading.Thread(target=self._intlinks_worker, daemon=True).start()

    def _intlinks_worker(self):
        try:
            from utils.internal_links import run_internal_links_cli
            run_internal_links_cli()
        except Exception as e:
            print(f"[InternalLinks] Lỗi: {type(e).__name__}: {e}")
        finally:
            self._intlinks_running = False
            self.after(0, lambda: self.btn_intlinks.configure(
                state="normal", text="🧩  GỢI Ý LINK NỘI BỘ"))

    def run_audit_actions_now(self):
        """Nút 📝: findings audit → việc ưu tiên theo từ khóa (CAO trước)."""
        if self._actions_running:
            return
        self._actions_running = True
        self.btn_actions.configure(state="disabled", text="⏳ Đang xếp việc...")
        threading.Thread(target=self._actions_worker, daemon=True).start()

    def _actions_worker(self):
        try:
            from utils.audit_actions import run_audit_actions_cli
            run_audit_actions_cli()
        except Exception as e:
            print(f"[Actions] Lỗi: {type(e).__name__}: {e}")
        finally:
            self._actions_running = False
            self.after(0, lambda: self.btn_actions.configure(
                state="normal", text="📝  VIỆC ƯU TIÊN TỪ AUDIT"))

    def run_doctor_now(self):
        """Nút 🩺: kiểm tra môi trường — mỗi mục tự nuốt lỗi, không crash."""
        if self._doctor_running:
            return
        self._doctor_running = True
        self.btn_doctor.configure(state="disabled", text="⏳ Đang kiểm tra...")
        threading.Thread(target=self._doctor_worker, daemon=True).start()

    def _doctor_worker(self):
        try:
            from utils.doctor import run_doctor_cli
            run_doctor_cli(net=False)
        except Exception as e:
            print(f"[Doctor] Lỗi: {type(e).__name__}: {e}")
        finally:
            self._doctor_running = False
            self.after(0, lambda: self.btn_doctor.configure(
                state="normal", text="🩺  DOCTOR"))

    def run_plan_progress_now(self):
        """Nút 📋: 30 mục content plan — mục nào đã có draft / đã push WP (chỉ đọc)."""
        if self._planprog_running:
            return
        self._planprog_running = True
        self.btn_planprog.configure(state="disabled", text="⏳ Đang quét...")
        threading.Thread(target=self._planprog_worker, daemon=True).start()

    def _planprog_worker(self):
        try:
            from utils.plan_progress import run_plan_progress_cli
            run_plan_progress_cli()
        except Exception as e:
            print(f"[PlanProgress] Lỗi: {type(e).__name__}: {e}")
        finally:
            self._planprog_running = False
            self.after(0, lambda: self.btn_planprog.configure(
                state="normal", text="📋  PLAN PROGRESS"))

    def run_gsc_alerts_now(self):
        """Nút 📉: query nào mất phơi mạnh giữa 2 snapshot GSC (gửi qua kênh alerts)."""
        if self._gscalerts_running:
            return
        self._gscalerts_running = True
        self.btn_gscalerts.configure(state="disabled", text="⏳ Đang so...")
        threading.Thread(target=self._gscalerts_worker, daemon=True).start()

    def _gscalerts_worker(self):
        try:
            from utils.gsc_alerts import run_gsc_alerts_cli
            run_gsc_alerts_cli()
        except Exception as e:
            print(f"[GSCAlerts] Lỗi: {type(e).__name__}: {e}")
        finally:
            self._gscalerts_running = False
            self.after(0, lambda: self.btn_gscalerts.configure(
                state="normal", text="📉  GSC ALERTS"))

    def run_cluster_gsc_now(self):
        """Nút ⚖️: cụm từ khóa × dữ liệu Google thật (imps/clicks + cụm mù GSC)."""
        if self._clustgsc_running:
            return
        self._clustgsc_running = True
        self.btn_clustgsc.configure(state="disabled", text="⏳ Đang ghép...")
        threading.Thread(target=self._clustgsc_worker, daemon=True).start()

    def _clustgsc_worker(self):
        try:
            from utils.cluster_gsc import run_cluster_gsc_cli
            run_cluster_gsc_cli()
        except Exception as e:
            print(f"[ClusterGSC] Lỗi: {type(e).__name__}: {e}")
        finally:
            self._clustgsc_running = False
            self.after(0, lambda: self.btn_clustgsc.configure(
                state="normal", text="⚖️  CỤM × GSC"))

    def run_gsc_trend_now(self):
        """Nút 📊: xu hướng imps/clicks/CTR theo query, 8 mốc GSC gần nhất."""
        if self._gsctrend_running:
            return
        self._gsctrend_running = True
        self.btn_gsctrend.configure(state="disabled", text="⏳ Đang vẽ...")
        threading.Thread(target=self._gsctrend_worker, daemon=True).start()

    def _gsctrend_worker(self):
        try:
            from utils.gsc_trend import run_gsc_trend_cli
            run_gsc_trend_cli()
        except Exception as e:
            print(f"[GSCTrend] Lỗi: {type(e).__name__}: {e}")
        finally:
            self._gsctrend_running = False
            self.after(0, lambda: self.btn_gsctrend.configure(
                state="normal", text="📊  GSC TREND"))

    def run_ctr_ops_now(self):
        """Nút 🎯: query được thấy mà ít người click → gợi ý sửa title/meta."""
        if self._ctrops_running:
            return
        self._ctrops_running = True
        self.btn_ctrops.configure(state="disabled", text="⏳ Đang so...")
        threading.Thread(target=self._ctrops_worker, daemon=True).start()

    def _ctrops_worker(self):
        try:
            from utils.ctr_opportunities import run_ctr_cli
            run_ctr_cli()
        except Exception as e:
            print(f"[CTROps] Lỗi: {type(e).__name__}: {e}")
        finally:
            self._ctrops_running = False
            self.after(0, lambda: self.btn_ctrops.configure(
                state="normal", text="🎯  CTR OPS"))

    # ═══════════════════════════════════════════════════════════════
    # CONTENT GENERATION (F8) — chỉ sinh bản nháp bằng Ollama, không tự đăng
    # ═══════════════════════════════════════════════════════════════

    def run_generate_content(self):
        """Nút ✍️: sinh dàn ý → bản nháp markdown vào content/drafts/ (thread nền)."""
        if self.is_running:
            print("[Content] ⚠️ Bot đang treo máy — đợi phiên traffic xong rồi sinh bài.")
            return
        if self._generate_running:
            return
        # Đọc widget Tk ở luồng chính — worker nền KHÔNG được chạm entry (Tk không thread-safe)
        kw = self.entry_gen_kw.get().strip()
        url = self.entry_ollama_url.get().strip()
        self._generate_running = True
        self.btn_generate.configure(state="disabled", text="⏳ Đang sinh bài...")
        threading.Thread(target=self._generate_worker, args=(kw, url), daemon=True).start()

    def _generate_worker(self, kw, url):
        try:
            from content.generator import generate_article
            if url:
                cfg.OLLAMA_URL = url
            path, msg = generate_article(keyword=kw)
            if path:
                print(f"[Content] ✍️ Đã lưu bản nháp: {path}")
            else:
                print(f"[Content] {msg}")
        except Exception as e:
            print(f"[Content] Lỗi: {e}")
        finally:
            self._generate_running = False
            self.after(0, lambda: self.btn_generate.configure(
                state="normal", text="✍️  SINH BÀI"))

    # ═══════════════════════════════════════════════════════════════
    # TỪ KHÓA ĐỀ XUẤT TỪ SEARCH CONSOLE (F2)
    # ═══════════════════════════════════════════════════════════════

    def _kw_suggest_note(self, text: str):
        for w in self.kw_suggest_frame.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.kw_suggest_frame, text=text, text_color="gray",
                     font=ctk.CTkFont(size=12), anchor="w", justify="left",
                     ).pack(anchor="w", padx=4, pady=6)

    def refresh_keyword_suggestions(self):
        """Liệt kê query Search Console chưa theo dõi, mỗi dòng có nút + Thêm."""
        from utils.gsc_client import latest_gsc_rows, suggest_keywords
        from utils.keywords import load_keywords
        try:
            rows = latest_gsc_rows()
        except Exception as e:
            print(f"[Keyword] Lỗi đọc dữ liệu Search Console: {e}")
            self._kw_suggest_note("Không đọc được dữ liệu Search Console.")
            return
        if not rows:
            self._kw_suggest_note("Chưa có dữ liệu Search Console — bấm '📊 LẤY DỮ LIỆU SEARCH CONSOLE' trước.")
            return

        items = suggest_keywords(rows, load_keywords(),
                                 limit=getattr(cfg, "KEYWORD_SUGGEST_LIMIT", 20))
        if not items:
            self._kw_suggest_note(
                f"Không còn query nào chưa theo dõi có impressions ≥ "
                f"{getattr(cfg, 'KEYWORD_SUGGEST_MIN_IMPRESSIONS', 30)}.")
            return

        for w in self.kw_suggest_frame.winfo_children():
            w.destroy()
        for d in items:
            row = ctk.CTkFrame(self.kw_suggest_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(
                row,
                text=f"{d['query'][:56]:<56}  {d['impressions']:>6} hiện  "
                     f"{d['clicks']:>5} clicks  (TB {d['position']:.1f})",
                font=ctk.CTkFont(family="Consolas", size=12),
            ).pack(side="left")
            ctk.CTkButton(
                row, text="+ Thêm", width=76, height=24,
                fg_color="#3a6b35", hover_color="#4a8544",
                command=lambda q=d["query"]: self.add_suggested_keyword(q),
            ).pack(side="right")

    def add_suggested_keyword(self, query: str):
        """Thêm một query đề xuất vào danh sách theo dõi (chống trùng, ghi file luôn)."""
        from utils.keywords import add_keyword
        added, msg = add_keyword(query)
        print(f"[Keyword] {'✅' if added else '⚠️'} {msg}")
        if added:
            self.txt_keywords.insert(END, "\n" + query)
            self.refresh_keyword_suggestions()

    # ═══════════════════════════════════════════════════════════════
    # OLLAMA TEST CONNECTION
    # ═══════════════════════════════════════════════════════════════

    def test_ollama_connection(self):
        self.btn_test_ollama.configure(state="disabled", text="Đang kiểm tra...")
        self.lbl_ollama_status.configure(text="● Đang kết nối...", text_color="yellow")
        threading.Thread(target=self._do_test_ollama, daemon=True).start()

    def _do_test_ollama(self):
        from utils.ollama_client import base_from_url
        base = base_from_url(self.entry_ollama_url.get().strip())
        try:
            resp = requests.get(f"{base}/api/tags", timeout=5)
            if resp.status_code == 200:
                n = len(resp.json().get("models", []))
                msg_ok = f"● Kết nối thành công  ({n} model)"
                self.after(0, lambda: self.lbl_ollama_status.configure(text=msg_ok, text_color="#00cc44"))
                self.after(0, lambda: self.lbl_ollama_sidebar.configure(text=f"● Online ({n} model)", text_color="#00cc44"))
            else:
                raise ConnectionError(f"HTTP {resp.status_code}")
        except Exception as e:
            msg_err = f"● Lỗi: {str(e)[:38]}"
            self.after(0, lambda: self.lbl_ollama_status.configure(text=msg_err, text_color="#cc2222"))
            self.after(0, lambda: self.lbl_ollama_sidebar.configure(text="● Offline", text_color="#cc2222"))
        finally:
            self.after(0, lambda: self.btn_test_ollama.configure(state="normal", text="🔌  Kiểm tra kết nối Ollama"))

    # ═══════════════════════════════════════════════════════════════
    # SESSION COUNTER
    # ═══════════════════════════════════════════════════════════════

    
    def refresh_ollama_models(self):
        """Lấy danh sách model từ Ollama server và cập nhật dropdown."""
        from utils.ollama_client import base_from_url
        base = base_from_url(self.entry_ollama_url.get().strip())
        try:
            resp = requests.get(f"{base}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                if models:
                    self.combo_model.configure(values=models)
                    self.combo_model.set(models[0])
                    self.after(0, lambda: self.lbl_ollama_status.configure(
                        text=f"✅ {len(models)} models loaded", text_color="#00cc44"))
                else:
                    self.after(0, lambda: self.lbl_ollama_status.configure(
                        text="❌ Không có model nào", text_color="#cc2222"))
        except Exception as e:
            self.after(0, lambda: self.lbl_ollama_status.configure(
                text=f"❌ Lỗi: {str(e)[:38]}", text_color="#cc2222"))
    def _inc_ok(self):
        self._session_ok += 1
        self.lbl_ok.configure(text=str(self._session_ok))

    def _inc_err(self):
        self._session_err += 1
        self.lbl_err.configure(text=str(self._session_err))

    def _reset_counters(self):
        self._session_ok = 0
        self._session_err = 0
        self.lbl_ok.configure(text="0")
        self.lbl_err.configure(text="0")

    # ═══════════════════════════════════════════════════════════════
    # LOGIC CHẠY
    # ═══════════════════════════════════════════════════════════════

    def start_thread(self):
        if self.is_running:
            return
        self.is_running = True
        self.stop_event.clear()
        self._reset_counters()
        self.update_ui_state(running=True)

        # F10b — site ở trên phải được ÁP DỤNG ĐÚNG NGHĨA trước khi ghi bất kỳ state nào:
        # chỉ ném TARGET_URL thì từ khóa bị save vào keywords.json của site sai
        # (nháp của site A rơi xuống site B). Cùng hiệu lực nút 🔀 (không reload gfx).
        url = self.entry_url.get().strip()
        if url and url != cfg.TARGET_URL:
            cfg.TARGET_URL = url if "://" in url else f"https://{url}"
            dom = site_paths.site_domain()
            if dom:
                cfg.GSC_SITE_URL = f"sc-domain:{dom}"
            print(f"[Site] Đã áp dụng site mới: {dom or cfg.TARGET_URL}"
                  f"  |  per-site={'BẬT' if site_paths.is_multi_site() else 'TẮT (chưa migrate)'}")
        else:
            cfg.TARGET_URL = url or cfg.TARGET_URL

        cfg.TRAFFIC_MODE = self.radio_var.get()

        kws = self.txt_keywords.get("0.0", "end").strip().split("\n")
        cleaned = [k.strip() for k in kws if k.strip()]
        if not cleaned:
            print("[Keyword] ⚠️ Danh sách từ khóa trống — search traffic và rank check không còn từ khóa để chạy.")
        save_keywords(cleaned)

        proxies = self.txt_proxy.get("0.0", "end").strip().split("\n")
        cfg.PROXY_LIST = [p.strip() for p in proxies if p.strip()]

        cfg.HEADLESS_MODE = bool(self.sw_headless.get())
        cfg.LOAD_IMAGES   = bool(self.sw_images.get())

        dev = self.combo_device.get()
        cfg.DEVICE_NAME   = dev
        cfg.VIEWPORT_SIZE = {"width": 1920, "height": 1080} if "Desktop" in dev else {"width": 390, "height": 844}

        try:
            min_val = int(self.entry_min_time.get())
            max_val = int(self.entry_max_time.get())
            cfg.DURATION_MIN = min(min_val, max_val)
            cfg.DURATION_MAX = max(min_val, max_val)
        except ValueError:
            cfg.DURATION_MIN, cfg.DURATION_MAX = 60, 120

        cfg.LOOP_ENABLE = bool(self.chk_loop.get())
        try:
            cfg.LOOP_DURATION_MINUTES = int(self.entry_loop_time.get())
        except ValueError:
            cfg.LOOP_DURATION_MINUTES = 60
        cfg.ALWAYS_NEW_USER = bool(self.chk_new_user.get())

        cfg.WARMUP_ENABLE    = bool(self.chk_warmup.get())
        cfg.WARMUP_YOUTUBE   = bool(self.chk_ytb.get())
        cfg.WARMUP_NEWS      = bool(self.chk_news.get())
        cfg.WARMUP_WIKIPEDIA = bool(self.chk_wiki.get())
        cfg.WARMUP_SHOPPING  = bool(self.chk_shop.get())
        cfg.WARMUP_FACEBOOK  = bool(self.chk_fb.get())
        cfg.WARMUP_INSTAGRAM = bool(self.chk_ig.get())

        # AI Engine
        cfg.OLLAMA_URL   = self.entry_ollama_url.get().strip()
        cfg.OLLAMA_MODEL = self.combo_model.get().strip()

        # Hành Vi SEO
        cfg.POGO_STICK_ENABLE        = bool(self.chk_pogo.get())
        cfg.POGO_STICK_MAX           = int(self.slider_pogo.get())
        cfg.WARMUP_SEARCH_ENABLE     = bool(self.chk_warmup_search.get())
        cfg.KEYWORD_VARIATION_ENABLE = bool(self.chk_kw_variation.get())
        cfg.THIRD_PAGE_ENABLE        = bool(self.chk_third_page.get())
        cfg.THIRD_PAGE_CHANCE        = int(self.slider_third_page.get())

        threads = int(self.slider_threads.get())
        threading.Thread(target=self.run_async_loop, args=(threads,), daemon=True).start()

    def stop_process(self):
        if not self.is_running:
            return
        print("\n[🛑] ĐANG DỪNG... (Chờ các luồng hiện tại chạy xong)")
        self.stop_event.set()

    def update_ui_state(self, running: bool):
        if running:
            self.btn_start.configure(state="disabled", text="⏳ ĐANG CHẠY...", fg_color="gray")
            self.btn_stop.configure(state="normal", fg_color="#7a1a1a")
            self.lbl_status.configure(text="● Đang chạy...", text_color="#00cc44")
        else:
            self.btn_start.configure(state="normal", text="▶  BẮT ĐẦU TREO MÁY", fg_color="#1a7a1a")
            self.btn_stop.configure(state="disabled", fg_color="gray")
            self.lbl_status.configure(text="● Đã dừng", text_color="gray")
            self.lbl_timer.configure(text="")

    def run_async_loop(self, max_tabs: int):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.main_logic(max_tabs))
        loop.close()
        self.is_running = False
        self.after(0, lambda: self.update_ui_state(running=False))

    async def process_single_session(self, manager, browser, proxy, worker_id: int):
        # Rate limiter - toi da 25 session/ngay
        from utils.rate_limiter import can_run_session, mark_session_run, get_today_summary
        allowed, reason = can_run_session()
        if not allowed:
            print(f"[W{worker_id}] [RATE] {reason}")
            return
        page = None
        try:
            if self.stop_event.is_set():
                return

            if cfg.ALWAYS_NEW_USER:
                p_id   = f"{proxy or 'Local'}_{uuid.uuid4().hex[:8]}"
                label  = "🆕 New"
            else:
                p_id   = proxy or f"Local_W{worker_id}"
                label  = "♻️ Returning"

            print(f"[W{worker_id}] 🚀 Mở Tab ({label}) | Proxy: {proxy or 'None'}")
            page = await manager.create_context(browser, proxy_info=proxy, profile_id=p_id)

            if cfg.WARMUP_ENABLE:
                modes = [m for m, flag in [
                    ("youtube",  cfg.WARMUP_YOUTUBE),
                    ("news",     cfg.WARMUP_NEWS),
                    ("wiki",     cfg.WARMUP_WIKIPEDIA),
                    ("shopping", cfg.WARMUP_SHOPPING),
                    ("facebook", cfg.WARMUP_FACEBOOK),
                    ("instagram", cfg.WARMUP_INSTAGRAM),
                ] if flag]
                if modes:
                    from scenarios.warmup import run_warmup
                    await run_warmup(page, modes)

            if not self.stop_event.is_set():
                cfg.TEST_DURATION = random.randint(cfg.DURATION_MIN, cfg.DURATION_MAX)
                mode = getattr(cfg, "TRAFFIC_MODE", "direct")
                if mode == "search":
                    from tests.test_search_flow import run_search_flow
                    await run_search_flow(page)
                elif mode == "aio":
                    from scenarios.aio_traffic import run_aio_session
                    await run_aio_session(page)
                elif mode == "mix":
                    r = __import__("random").random()
                    if r < 0.4:
                        from tests.test_search_flow import run_search_flow
                        await run_search_flow(page)
                    elif r < 0.7:
                        from scenarios.aio_traffic import run_aio_session
                        await run_aio_session(page)
                    else:
                        await run_deep_session(page)
                else:
                    await run_deep_session(page)

            print(f"[W{worker_id}] ✅ Hoàn thành phiên.")
            self.after(0, self._inc_ok)
            mark_session_run()

        except Exception as e:
            print(f"[W{worker_id}] ❌ Lỗi: {e}")
            self.after(0, self._inc_err)
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
        rest = random.randint(15, 45)
        print(f"[W{worker_id}] Nghi {rest}s...")
        await asyncio.sleep(rest)

    async def continuous_worker(self, manager, browser, proxy_iter, worker_id: int, end_time: float):
        # Stagger: moi luong cach nhau 10-30s
        stagger = random.randint(8, 25)
        print(f"[W{worker_id}] Cho {stagger}s de tranh phat hien...")
        await asyncio.sleep(stagger)

        while time.time() < end_time and not self.stop_event.is_set():
            proxy = next(proxy_iter)
            await self.process_single_session(manager, browser, proxy, worker_id)
            if self.stop_event.is_set():
                break
            rest = random.randint(3, 8)
            print(f"[W{worker_id}] 💤 Nghỉ {rest}s...")
            await asyncio.sleep(rest)

    async def main_logic(self, max_tabs: int):
        manager = BrowserManager()
        try:
            browser    = await manager.launch_browser()
            proxies    = cfg.PROXY_LIST or [None]
            proxy_iter = itertools.cycle(proxies)

            loop_minutes = cfg.LOOP_DURATION_MINUTES if cfg.LOOP_ENABLE else 999_999
            end_time     = time.time() + loop_minutes * 60
            print(f"\n--- 🕒 BẮT ĐẦU: {loop_minutes} phút | {max_tabs} luồng | Mode: {cfg.TRAFFIC_MODE.upper()} ---")

            workers = []
            for i in range(max_tabs):
                await asyncio.sleep(random.uniform(0.5, 2.0))
                workers.append(asyncio.create_task(
                    self.continuous_worker(manager, browser, proxy_iter, i + 1, end_time)
                ))

            while time.time() < end_time and not self.stop_event.is_set():
                remaining = int(end_time - time.time())
                m, s = divmod(remaining, 60)
                self.after(0, lambda t=f"{m:02d}:{s:02d}": self.lbl_timer.configure(text=f"⏳ {t}"))
                await asyncio.sleep(1)

            if self.stop_event.is_set():
                print("\n[🛑] Đã nhận lệnh dừng. Chờ các luồng đang chạy...")
            else:
                print("\n[🏁] Hết thời gian treo máy!")
                self.after(0, lambda: self.lbl_timer.configure(text="✅ HOÀN THÀNH"))

            await asyncio.gather(*workers, return_exceptions=True)

        except Exception as e:
            print(f"[CRITICAL] {e}")
        finally:
            await manager.close()


if __name__ == "__main__":
    try:
        app = TrafficBotUI()
        app.mainloop()
    except Exception:
        msg = traceback.format_exc()
        _real_stderr.write(msg)
        with open("ui_error.log", "w", encoding="utf-8") as _f:
            _f.write(msg)
