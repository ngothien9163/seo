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

        self._setup_tab_general()
        self._setup_tab_loop()
        self._setup_tab_browser()
        self._setup_tab_behavior()
        self._setup_tab_ai()
        self._setup_tab_warmup()
        self._setup_tab_rank()

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
        self.lbl_rank_last = ctk.CTkLabel(rf, text="", text_color="gray")
        self.lbl_rank_last.pack(side="left", padx=16)
        self.lbl_alert_mode = ctk.CTkLabel(rf, text="", text_color="gray")
        self.lbl_alert_mode.pack(side="left", padx=(0, 16))

        self.txt_rank = ctk.CTkTextbox(t, font=ctk.CTkFont(family="Consolas", size=12))
        self.txt_rank.grid(row=2, column=0, sticky="nsew", padx=20, pady=(4, 4))
        t.grid_rowconfigure(2, weight=1)
        t.grid_columnconfigure(0, weight=1)

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
        threading.Thread(target=self._alert_preview_worker, daemon=True).start()

    def _alert_preview_worker(self):
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
        self.after(0, self._refresh_alert_mode_label)

    def _refresh_rank_report(self):
        from utils.gsc_client import build_report as build_merged_report
        from utils.rank_tracker import _load_history
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
                    text=f"Lần check gần nhất: {sorted(checks.keys())[-1].replace('T', ' ')}")
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
        base = self.entry_ollama_url.get().replace("/api/generate", "").rstrip("/")
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
        """L?y danh s�ch model t? Ollama server v� c?p nh?t dropdown."""
        base = self.entry_ollama_url.get().replace("/api/generate", "").rstrip("/")
        try:
            resp = requests.get(f"{base}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                if models:
                    self.combo_model.configure(values=models)
                    self.combo_model.set(models[0])
                    self.after(0, lambda: self.lbl_ollama_status.configure(
                        text=f"? {len(models)} models loaded", text_color="#00cc44"))
                else:
                    self.after(0, lambda: self.lbl_ollama_status.configure(
                        text="? Kh�ng c� model n�o", text_color="#cc2222"))
        except Exception as e:
            self.after(0, lambda: self.lbl_ollama_status.configure(
                text=f"? L?i: {str(e)[:38]}", text_color="#cc2222"))
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

        cfg.TARGET_URL   = self.entry_url.get().strip()
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
