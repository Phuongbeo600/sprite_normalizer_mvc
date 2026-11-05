import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Callable, Dict, Any, List
from PIL import Image, ImageTk, ImageDraw
from models.character_analyzer import CharacterMetrics


class MainView(tk.Tk):
    """
    Giao diện chính (View trong kiến trúc MVC).
    Hỗ trợ cả Sprite đơn, Dải hoạt ảnh (Animation Strip) và Xử lý Hàng loạt (Batch Processing):
    - Cột 1: Quản lý & Phân tích giải phẫu học Nhân vật cũ (Reference)
    - Cột 2: Tùy biến yêu cầu giải phẫu & Bộ sinh Prompt AI (Gemini / Heuristic)
    - Cột 3: Nạp 1 hoặc NHIỀU ảnh, Cắt dải cả bìa, Đề xuất độ phân giải thật, Batch Sprite Size
    """

    def __init__(self):
        super().__init__()
        self.title("Sprite AI Normalizer - Batch Sprite Size & Animation Tool (MVC)")
        self.geometry("1420x860")
        self.minsize(1200, 760)
        self.configure(bg="#1e1e1e")

        # Callbacks sẽ được Controller gán vào
        self.on_select_ref_image: Optional[Callable[[str], None]] = None
        self.on_toggle_overlay: Optional[Callable[[bool], None]] = None
        self.on_generate_prompt: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_select_new_images: Optional[Callable[[List[str]], None]] = None
        self.on_batch_navigate: Optional[Callable[[int], None]] = None
        self.on_open_sprite_size_dialog: Optional[Callable[[], None]] = None
        self.on_apply_preset_size: Optional[Callable[[int, int], None]] = None
        self.on_auto_standardize: Optional[Callable[[], None]] = None
        self.on_split_strip: Optional[Callable[[int, bool], None]] = None
        self.on_export_frames_folder: Optional[Callable[[], None]] = None
        self.on_export_batch_folder: Optional[Callable[[], None]] = None
        self.on_export_gif: Optional[Callable[[int], None]] = None
        self.on_save_final_sprite: Optional[Callable[[str], None]] = None
        self.on_export_sprite: Optional[Callable[[], None]] = None
        self.on_save_api_key: Optional[Callable[[str], None]] = None

        # Cache ảnh hiển thị
        self._ref_photo = None
        self._norm_photo = None

        # Quản lý hoạt ảnh (Animation Player)
        self.anim_frames: List[Image.Image] = []
        self.anim_index: int = 0
        self.anim_playing: bool = False
        self.anim_fps: int = 6
        self.anim_timer: Optional[str] = None

        self._init_theme()
        self._create_header()
        self._create_main_content()
        self._create_status_bar()

    def _init_theme(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure(".", background="#1e1e1e", foreground="#cccccc")
        style.configure("TLabel", background="#1e1e1e", foreground="#cccccc")
        style.configure("TFrame", background="#1e1e1e")
        style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"), foreground="#4ec9b0")
        style.configure("SubHeader.TLabel", font=("Segoe UI", 10, "bold"), foreground="#ffffff")
        style.configure("TCombobox", fieldbackground="#333333", background="#444444", foreground="#ffffff")

    def _create_header(self):
        header = tk.Frame(self, bg="#252526", padx=16, pady=8, relief="groove", bd=1)
        header.pack(fill=tk.X, side=tk.TOP)

        title_lbl = tk.Label(header, text="⚔️ SPRITE AI NORMALIZER & BATCH RESIZER", 
                             font=("Segoe UI", 13, "bold"), fg="#4ec9b0", bg="#252526")
        title_lbl.pack(side=tk.LEFT)

        subtitle_lbl = tk.Label(header, text=" | Cắt cả bìa dải AI, Đề xuất độ phân giải THẬT, Batch Sprite Size hàng loạt", 
                                font=("Segoe UI", 9), fg="#858585", bg="#252526")
        subtitle_lbl.pack(side=tk.LEFT)

        btn_apikey = tk.Button(header, text="🔑 Cài đặt Gemini API Key", bg="#0e639c", fg="#ffffff",
                               font=("Segoe UI", 9), relief="flat", padx=10, pady=3, command=self._popup_api_key_dialog)
        btn_apikey.pack(side=tk.RIGHT)

    def _create_main_content(self):
        container = tk.Frame(self, bg="#1e1e1e", padx=10, pady=6)
        container.pack(fill=tk.BOTH, expand=True)

        container.columnconfigure(0, weight=3, minsize=320)
        container.columnconfigure(1, weight=4, minsize=410)
        container.columnconfigure(2, weight=4, minsize=420)
        container.rowconfigure(0, weight=1)

        # Cột 1: NHÂN VẬT THAM CHIẾU (CŨ)
        card1 = tk.Frame(container, bg="#252526", padx=10, pady=8, relief="groove", bd=1)
        card1.grid(row=0, column=0, sticky="nsew", padx=4)
        self._build_col1_reference(card1)

        # Cột 2: CẤU HÌNH YÊU CẦU & PROMPT AI
        card2 = tk.Frame(container, bg="#252526", padx=10, pady=8, relief="groove", bd=1)
        card2.grid(row=0, column=1, sticky="nsew", padx=4)
        self._build_col2_prompt(card2)

        # Cột 3: NẠP NHIỀU ẢNH, CẮT CẢ BÌA, BATCH SPRITE SIZE
        card3 = tk.Frame(container, bg="#252526", padx=10, pady=8, relief="groove", bd=1)
        card3.grid(row=0, column=2, sticky="nsew", padx=4)
        self._build_col3_normalizer(card3)

    def _build_col1_reference(self, parent):
        tk.Label(parent, text="BƯỚC 1: NHÂN VẬT THAM CHIẾU (CŨ)", font=("Segoe UI", 11, "bold"), 
                 fg="#4ec9b0", bg="#252526").pack(anchor="w")

        btn_load = tk.Button(parent, text="📂 Chọn ảnh Sprite cũ (.png)", bg="#333333", fg="#ffffff",
                             font=("Segoe UI", 9, "bold"), relief="flat", pady=5, command=self._open_ref_file)
        btn_load.pack(fill=tk.X, pady=(6, 4))

        self.ref_canvas = tk.Canvas(parent, width=260, height=220, bg="#2d2d30", 
                                    highlightthickness=1, highlightbackground="#3e3e42")
        self.ref_canvas.pack(pady=2)

        self.show_overlay_var = tk.BooleanVar(value=True)
        cb_overlay = tk.Checkbutton(parent, text="👁️ Vẽ khung đo Đầu & Thân (AI Vision)", 
                                    variable=self.show_overlay_var, bg="#252526", fg="#dcdcaa",
                                    selectcolor="#333333", activebackground="#252526", activeforeground="#dcdcaa",
                                    command=self._on_toggle_overlay_cb)
        cb_overlay.pack(anchor="w", pady=(2, 2))

        lbl_info_title = tk.Label(parent, text="📊 Kết quả đo lường giải phẫu:", 
                                  font=("Segoe UI", 9, "bold"), fg="#9cdcfe", bg="#252526")
        lbl_info_title.pack(anchor="w", pady=(2, 2))

        self.ref_info_text = tk.Text(parent, height=10, bg="#1e1e1e", fg="#d4d4d4", 
                                     font=("Consolas", 9), relief="flat", padx=8, pady=6)
        self.ref_info_text.pack(fill=tk.BOTH, expand=True)
        self.ref_info_text.insert(tk.END, "Chưa chọn ảnh nhân vật cũ.\nVui lòng nhấn nút ở trên để tải ảnh...")
        self.ref_info_text.config(state="disabled")

    def _build_col2_prompt(self, parent):
        tk.Label(parent, text="BƯỚC 2: YÊU CẦU & BỘ SINH PROMPT AI", font=("Segoe UI", 11, "bold"), 
                 fg="#4ec9b0", bg="#252526").pack(anchor="w")

        form_frame = tk.Frame(parent, bg="#252526")
        form_frame.pack(fill=tk.X, pady=(6, 2))

        r1 = tk.Frame(form_frame, bg="#252526")
        r1.pack(fill=tk.X, pady=2)
        tk.Label(r1, text="Đầu nhân vật mới:", width=18, anchor="w", fg="#cccccc", bg="#252526", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.head_rule_var = tk.StringVar(value="Bằng nhân vật cũ (Tỉ lệ chuẩn)")
        self.head_combo = ttk.Combobox(r1, textvariable=self.head_rule_var, state="readonly",
                                       values=["Bằng nhân vật cũ (Tỉ lệ chuẩn)"])
        self.head_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        r2 = tk.Frame(form_frame, bg="#252526")
        r2.pack(fill=tk.X, pady=2)
        tk.Label(r2, text="Thân (Chiều rộng):", width=18, anchor="w", fg="#cccccc", bg="#252526", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.body_w_rule_var = tk.StringVar(value="Bằng nhân vật cũ")
        self.body_w_combo = ttk.Combobox(r2, textvariable=self.body_w_rule_var, state="readonly",
                                         values=["Bằng nhân vật cũ", "To hơn (Đô con / Dày mình)", "Nhỏ hơn (Thon gọn / Mảnh mai)"])
        self.body_w_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        r3 = tk.Frame(form_frame, bg="#252526")
        r3.pack(fill=tk.X, pady=2)
        tk.Label(r3, text="Thân (Chiều cao):", width=18, anchor="w", fg="#cccccc", bg="#252526", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.body_h_rule_var = tk.StringVar(value="Bằng nhân vật cũ")
        self.body_h_combo = ttk.Combobox(r3, textvariable=self.body_h_rule_var, state="readonly",
                                         values=["Bằng nhân vật cũ", "Cao hơn (Chân dài hơn)", "Thấp hơn (Đầm người / Lùn)"])
        self.body_h_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        r4 = tk.Frame(form_frame, bg="#252526")
        r4.pack(fill=tk.X, pady=2)
        tk.Label(r4, text="Ý tưởng nhân vật:", width=18, anchor="w", fg="#cccccc", bg="#252526", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.concept_var = tk.StringVar(value="Chiến binh quái thú / Dark Knight")
        self.concept_entry = tk.Entry(r4, textvariable=self.concept_var, bg="#3c3c3c", fg="#ffffff", insertbackground="white")
        self.concept_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        btn_gen = tk.Button(parent, text="✨ Phân tích Tỉ lệ & Tạo Cụm Prompt AI", bg="#007acc", fg="#ffffff",
                            font=("Segoe UI", 10, "bold"), relief="flat", pady=5, command=self._on_click_generate)
        btn_gen.pack(fill=tk.X, pady=(6, 4))

        self.style_lbl = tk.Label(parent, text="Chưa có phân tích phong cách.", fg="#4ec9b0", bg="#252526", 
                                  font=("Segoe UI", 9, "italic"), wraplength=400, justify="left")
        self.style_lbl.pack(anchor="w", pady=(0, 4))

        p_row = tk.Frame(parent, bg="#252526")
        p_row.pack(fill=tk.X)
        tk.Label(p_row, text="📋 Positive Prompt (Midjourney / SD):", font=("Segoe UI", 9, "bold"), 
                 fg="#ce9178", bg="#252526").pack(side=tk.LEFT)
        btn_copy_p = tk.Button(p_row, text="Copy Prompt", bg="#333333", fg="#ffffff", font=("Segoe UI", 8),
                               relief="flat", command=self._copy_positive_prompt)
        btn_copy_p.pack(side=tk.RIGHT)

        self.pos_prompt_text = tk.Text(parent, height=5, bg="#1e1e1e", fg="#d4d4d4", 
                                       font=("Consolas", 9), relief="flat", padx=6, pady=4, wrap="word")
        self.pos_prompt_text.pack(fill=tk.BOTH, expand=True, pady=(2, 4))

        n_row = tk.Frame(parent, bg="#252526")
        n_row.pack(fill=tk.X)
        tk.Label(n_row, text="🚫 Negative Prompt:", font=("Segoe UI", 9, "bold"), 
                 fg="#ce9178", bg="#252526").pack(side=tk.LEFT)
        btn_copy_n = tk.Button(n_row, text="Copy Negative", bg="#333333", fg="#ffffff", font=("Segoe UI", 8),
                               relief="flat", command=self._copy_negative_prompt)
        btn_copy_n.pack(side=tk.RIGHT)

        self.neg_prompt_text = tk.Text(parent, height=2, bg="#1e1e1e", fg="#d4d4d4", 
                                       font=("Consolas", 9), relief="flat", padx=6, pady=4, wrap="word")
        self.neg_prompt_text.pack(fill=tk.X, pady=(2, 0))

    def _build_col3_normalizer(self, parent):
        tk.Label(parent, text="BƯỚC 3: NẠP NHIỀU ẢNH, SPRITE SIZE & EXPORT", font=("Segoe UI", 11, "bold"), 
                 fg="#4ec9b0", bg="#252526").pack(anchor="w")

        # Nút chọn 1 hoặc nhiều ảnh cùng lúc
        btn_load_new = tk.Button(parent, text="📂 Nạp 1 hoặc NHIỀU ảnh Sprite / Dải AI (.png, .jpg)", bg="#333333", fg="#ffffff",
                                 font=("Segoe UI", 9, "bold"), relief="flat", pady=4, command=self._open_new_files)
        btn_load_new.pack(fill=tk.X, pady=(4, 2))

        # Thanh điều hướng khi nạp nhiều ảnh (Batch Navigation Bar)
        self.batch_nav_frame = tk.Frame(parent, bg="#252526")
        self.batch_nav_frame.pack(fill=tk.X, pady=(2, 2))

        self.btn_batch_prev = tk.Button(self.batch_nav_frame, text="◀ Trước", bg="#3e3e42", fg="#ffffff", 
                                        font=("Segoe UI", 8), relief="flat", padx=6, command=self._on_prev_image)
        self.btn_batch_prev.pack(side=tk.LEFT)

        self.batch_info_label = tk.Label(self.batch_nav_frame, text="Chưa nạp ảnh.", 
                                         fg="#dcdcaa", bg="#252526", font=("Segoe UI", 8, "bold"))
        self.batch_info_label.pack(side=tk.LEFT, padx=6)

        self.btn_batch_next = tk.Button(self.batch_nav_frame, text="Sau ▶", bg="#3e3e42", fg="#ffffff", 
                                        font=("Segoe UI", 8), relief="flat", padx=6, command=self._on_next_image)
        self.btn_batch_next.pack(side=tk.LEFT)

        # ------------------ KHUNG TÁCH DẢI (CẮT CẢ BÌA RA) ------------------
        self.strip_frame = tk.LabelFrame(parent, text=" 🎞️ Tách Dải Hoạt Ảnh (Animation Strip) ", 
                                         bg="#252526", fg="#dcdcaa", font=("Segoe UI", 8, "bold"), padx=6, pady=4)
        self.strip_frame.pack(fill=tk.X, pady=(2, 4))

        strip_row1 = tk.Frame(self.strip_frame, bg="#252526")
        strip_row1.pack(fill=tk.X, pady=1)

        tk.Label(strip_row1, text="Số Frame:", fg="#cccccc", bg="#252526", font=("Segoe UI", 8)).pack(side=tk.LEFT)
        self.strip_frames_var = tk.StringVar(value="4")
        self.strip_frames_combo = ttk.Combobox(strip_row1, textvariable=self.strip_frames_var, 
                                               values=["2", "3", "4", "5", "6", "8"], width=3, state="readonly")
        self.strip_frames_combo.pack(side=tk.LEFT, padx=(4, 8))

        # Checkbox CẮT CẢ BÌA RA
        self.keep_full_bounds_var = tk.BooleanVar(value=True)
        self.cb_full_bounds = tk.Checkbutton(strip_row1, text="Cắt cả bìa ra (Giữ trọn ô gốc)", 
                                             variable=self.keep_full_bounds_var, bg="#252526", fg="#4ec9b0",
                                             selectcolor="#333333", activebackground="#252526", activeforeground="#4ec9b0",
                                             font=("Segoe UI", 8, "bold"))
        self.cb_full_bounds.pack(side=tk.LEFT)

        btn_split_anim = tk.Button(strip_row1, text="⚡ Cắt Dải", bg="#e06c75", fg="#ffffff",
                                   font=("Segoe UI", 8, "bold"), relief="flat", padx=8, pady=2,
                                   command=self._on_split_strip_click)
        btn_split_anim.pack(side=tk.RIGHT)

        # ------------------ KHUNG ĐỀ XUẤT ĐỘ PHÂN GIẢI THẬT ------------------
        self.preset_box = tk.Frame(parent, bg="#252526")
        self.preset_box.pack(fill=tk.X, pady=(2, 2))

        self.btn_apply_canvas = tk.Button(self.preset_box, text="🎯 Đặt Canvas cũ", bg="#0e639c", fg="#ffffff",
                                          font=("Segoe UI", 8, "bold"), relief="flat", pady=2,
                                          command=self._on_click_apply_canvas)
        self.btn_apply_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))

        self.btn_apply_vis = tk.Button(self.preset_box, text="👤 Đặt ĐỘ PHÂN GIẢI THẬT cũ", bg="#2e7d32", fg="#ffffff",
                                       font=("Segoe UI", 8, "bold"), relief="flat", pady=2,
                                       command=self._on_click_apply_vis)
        self.btn_apply_vis.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(2, 0))

        # ------------------ NÚT THAO TÁC SPRITE SIZE ------------------
        btn_row_ops = tk.Frame(parent, bg="#252526")
        btn_row_ops.pack(fill=tk.X, pady=(2, 2))

        self.btn_sprite_size = tk.Button(btn_row_ops, text="📐 Sprite Size (LibreSprite)", bg="#007acc", fg="#ffffff",
                                         font=("Segoe UI", 8, "bold"), relief="flat", pady=3, command=self._on_open_dialog)
        self.btn_sprite_size.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))

        btn_auto_fit = tk.Button(btn_row_ops, text="⚡ Chuẩn hoá 1-Click", bg="#3e3e42", fg="#ffffff",
                                 font=("Segoe UI", 8, "bold"), relief="flat", pady=3, command=self._on_auto_standardize_click)
        btn_auto_fit.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(2, 0))

        # ------------------ CANVAS PREVIEW ------------------
        self.norm_canvas = tk.Canvas(parent, width=260, height=180, bg="#2d2d30", 
                                     highlightthickness=1, highlightbackground="#3e3e42")
        self.norm_canvas.pack(pady=2)

        # ------------------ ANIMATION CONTROLS ------------------
        self.player_frame = tk.Frame(parent, bg="#252526")
        self.player_frame.pack(fill=tk.X, pady=(1, 2))

        self.btn_play_pause = tk.Button(self.player_frame, text="▶️ Phát", bg="#007acc", fg="#ffffff",
                                        font=("Segoe UI", 8, "bold"), width=7, relief="flat", command=self.toggle_animation)
        self.btn_play_pause.pack(side=tk.LEFT, padx=(0, 4))

        tk.Label(self.player_frame, text="Tốc độ:", fg="#888888", bg="#252526", font=("Segoe UI", 8)).pack(side=tk.LEFT)
        self.fps_var = tk.StringVar(value="6 FPS")
        self.fps_combo = ttk.Combobox(self.player_frame, textvariable=self.fps_var, 
                                      values=["3 FPS", "4 FPS", "6 FPS", "8 FPS", "12 FPS"], width=6, state="readonly")
        self.fps_combo.pack(side=tk.LEFT, padx=3)
        self.fps_combo.bind("<<ComboboxSelected>>", self._on_fps_changed)

        self.anim_info_label = tk.Label(self.player_frame, text="Frame: -/-", fg="#4ec9b0", bg="#252526", font=("Consolas", 8, "bold"))
        self.anim_info_label.pack(side=tk.RIGHT)

        # Labels hiển thị cả Canvas và Độ phân giải thật
        self.norm_info_label = tk.Label(parent, text="Độ phân giải: Chưa có ảnh", 
                                        fg="#4ec9b0", bg="#252526", font=("Consolas", 9, "bold"))
        self.norm_info_label.pack(anchor="w", pady=(1, 2))

        # ------------------ NÚT EXPORT ------------------
        exp_row1 = tk.Frame(parent, bg="#252526")
        exp_row1.pack(fill=tk.X, pady=(2, 1))

        self.btn_exp_batch = tk.Button(exp_row1, text="📂 Xuất HÀNG LOẠT tất cả ảnh...", bg="#d19a66", fg="#1e1e1e",
                                       font=("Segoe UI", 8, "bold"), relief="flat", pady=3, command=self._on_export_batch_click)
        self.btn_exp_batch.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))

        btn_exp_frames = tk.Button(exp_row1, text="📂 Xuất Frame Rời (Godot)", bg="#e5c07b", fg="#1e1e1e",
                                   font=("Segoe UI", 8, "bold"), relief="flat", pady=3, command=self._on_export_frames_click)
        btn_exp_frames.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(2, 0))

        exp_row2 = tk.Frame(parent, bg="#252526")
        exp_row2.pack(fill=tk.X, pady=(1, 1))

        btn_export = tk.Button(exp_row2, text="📤 Export File (LibreSprite)", bg="#007acc", fg="#ffffff",
                               font=("Segoe UI", 8, "bold"), relief="flat", pady=3, command=self._on_export_click)
        btn_export.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))

        btn_exp_gif = tk.Button(exp_row2, text="🎞️ Xuất GIF Động", bg="#98c379", fg="#1e1e1e",
                                font=("Segoe UI", 8, "bold"), relief="flat", pady=3, command=self._on_export_gif_click)
        btn_exp_gif.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(2, 0))

        btn_save = tk.Button(parent, text="💾 Lưu file PNG (Save As)", bg="#c586c0", fg="#1e1e1e",
                             font=("Segoe UI", 8, "bold"), relief="flat", pady=3, command=self._save_file)
        btn_save.pack(fill=tk.X, pady=(1, 0))

    def _create_status_bar(self):
        self.status_bar = tk.Label(self, text="Sẵn sàng. Hãy chọn một Sprite cũ để bắt đầu phân tích.", 
                                   font=("Segoe UI", 9), fg="#ffffff", bg="#007acc", anchor="w", padx=10, pady=3)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    # ------------------ ANIMATION PLAYER LOGIC ------------------
    def set_animation_frames(self, frames: List[Image.Image]):
        self.stop_animation()
        self.anim_frames = frames
        self.anim_index = 0
        if frames:
            self.display_norm_image(frames[0])
            self.anim_info_label.config(text=f"Frame: 1/{len(frames)}")
            self.start_animation()
        else:
            self.anim_info_label.config(text="Frame: -/-")

    def start_animation(self):
        if not self.anim_frames:
            return
        self.anim_playing = True
        self.btn_play_pause.config(text="⏸️ Dừng", bg="#e06c75")
        self._anim_tick()

    def stop_animation(self):
        self.anim_playing = False
        if self.anim_timer:
            self.after_cancel(self.anim_timer)
            self.anim_timer = None
        self.btn_play_pause.config(text="▶️ Phát", bg="#007acc")

    def toggle_animation(self):
        if self.anim_playing:
            self.stop_animation()
        else:
            self.start_animation()

    def _on_fps_changed(self, event=None):
        try:
            val = int(self.fps_var.get().replace(" FPS", "").strip())
            self.anim_fps = max(1, val)
        except ValueError:
            pass

    def _anim_tick(self):
        if not self.anim_playing or not self.anim_frames:
            return
        
        self.anim_index = (self.anim_index + 1) % len(self.anim_frames)
        self.display_norm_image(self.anim_frames[self.anim_index])
        self.anim_info_label.config(text=f"Frame: {self.anim_index + 1}/{len(self.anim_frames)}")

        delay_ms = max(20, int(round(1000.0 / self.anim_fps)))
        self.anim_timer = self.after(delay_ms, self._anim_tick)

    # ------------------ EVENT HANDLERS ------------------
    def set_status(self, text: str, is_error: bool = False):
        self.status_bar.config(text=text, bg="#c72e2e" if is_error else "#007acc", fg="#ffffff")

    def _open_ref_file(self):
        path = filedialog.askopenfilename(
            title="Chọn file Sprite cũ",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.webp;*.bmp"), ("All Files", "*.*")]
        )
        if path and self.on_select_ref_image:
            self.on_select_ref_image(path)

    def _open_new_files(self):
        paths = filedialog.askopenfilenames(
            title="Chọn 1 hoặc NHIỀU file ảnh",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.webp;*.bmp"), ("All Files", "*.*")]
        )
        if paths and self.on_select_new_images:
            self.on_select_new_images(list(paths))

    def _on_prev_image(self):
        if self.on_batch_navigate:
            self.on_batch_navigate(-1)

    def _on_next_image(self):
        if self.on_batch_navigate:
            self.on_batch_navigate(1)

    def _on_toggle_overlay_cb(self):
        if self.on_toggle_overlay:
            self.on_toggle_overlay(self.show_overlay_var.get())

    def _on_click_generate(self):
        if self.on_generate_prompt:
            options = {
                "head_rule": self.head_rule_var.get(),
                "body_width_rule": self.body_w_rule_var.get(),
                "body_height_rule": self.body_h_rule_var.get(),
                "concept": self.concept_var.get()
            }
            self.on_generate_prompt(options)

    def _on_open_dialog(self):
        if self.on_open_sprite_size_dialog:
            self.on_open_sprite_size_dialog()

    def _on_click_apply_canvas(self):
        if hasattr(self, "_ref_w") and hasattr(self, "_ref_h") and self._ref_w and self._ref_h:
            if self.on_apply_preset_size:
                self.on_apply_preset_size(self._ref_w, self._ref_h)

    def _on_click_apply_vis(self):
        if hasattr(self, "_ref_vis_w") and hasattr(self, "_ref_vis_h") and self._ref_vis_w and self._ref_vis_h:
            if self.on_apply_preset_size:
                self.on_apply_preset_size(self._ref_vis_w, self._ref_vis_h)

    def _on_auto_standardize_click(self):
        if self.on_auto_standardize:
            self.on_auto_standardize()

    def _on_split_strip_click(self):
        if self.on_split_strip:
            try:
                num = int(self.strip_frames_var.get().strip())
            except ValueError:
                num = 4
            self.on_split_strip(num, self.keep_full_bounds_var.get())

    def _on_export_frames_click(self):
        if self.on_export_frames_folder:
            self.on_export_frames_folder()

    def _on_export_batch_click(self):
        if self.on_export_batch_folder:
            self.on_export_batch_folder()

    def _on_export_gif_click(self):
        if self.on_export_gif:
            self.on_export_gif(self.anim_fps)

    def _on_export_click(self):
        if self.on_export_sprite:
            self.on_export_sprite()

    def _save_file(self):
        if self.on_save_final_sprite:
            path = filedialog.asksaveasfilename(
                title="Lưu Sprite đã chuẩn hoá",
                defaultextension=".png",
                filetypes=[("PNG Image (*.png)", "*.png"), ("All Files", "*.*")]
            )
            if path:
                self.on_save_final_sprite(path)

    def _copy_positive_prompt(self):
        text = self.pos_prompt_text.get("1.0", tk.END).strip()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.set_status("Đã sao chép Positive Prompt vào Clipboard!")

    def _copy_negative_prompt(self):
        text = self.neg_prompt_text.get("1.0", tk.END).strip()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.set_status("Đã sao chép Negative Prompt vào Clipboard!")

    def _popup_api_key_dialog(self):
        top = tk.Toplevel(self)
        top.title("Cài đặt Gemini API Key")
        top.geometry("450x180")
        top.configure(bg="#252526")
        top.transient(self)
        top.grab_set()

        tk.Label(top, text="Nhập Google Gemini API Key:", font=("Segoe UI", 10, "bold"),
                 fg="#4ec9b0", bg="#252526").pack(anchor="w", padx=16, pady=(16, 4))
        
        tk.Label(top, text="(Nếu để trống, ứng dụng sẽ dùng bộ Heuristic cục bộ siêu chuẩn xác)",
                 font=("Segoe UI", 8), fg="#888888", bg="#252526").pack(anchor="w", padx=16, pady=(0, 8))

        key_var = tk.StringVar()
        entry = tk.Entry(top, textvariable=key_var, width=50, bg="#3c3c3c", fg="#ffffff", insertbackground="white")
        entry.pack(padx=16, pady=4, fill=tk.X)

        btn_row = tk.Frame(top, bg="#252526")
        btn_row.pack(side=tk.BOTTOM, fill=tk.X, padx=16, pady=16)

        def save_key():
            if self.on_save_api_key:
                self.on_save_api_key(key_var.get().strip())
            top.destroy()

        tk.Button(btn_row, text="Lưu API Key", bg="#007acc", fg="#ffffff", relief="flat", padx=12, pady=4, command=save_key).pack(side=tk.RIGHT)
        tk.Button(btn_row, text="Đóng", bg="#555555", fg="#ffffff", relief="flat", padx=12, pady=4, command=top.destroy).pack(side=tk.RIGHT, padx=8)

    # ------------------ METHODS CẬP NHẬT GIAO DIỆN TỪ CONTROLLER ------------------
    def display_ref_image(self, pil_image: Image.Image):
        self._ref_photo = self._render_to_canvas(self.ref_canvas, pil_image)

    def display_norm_image(self, pil_image: Image.Image):
        self._norm_photo = self._render_to_canvas(self.norm_canvas, pil_image)

    def update_ref_metrics(self, metrics: CharacterMetrics):
        self._ref_w = metrics.canvas_width
        self._ref_h = metrics.canvas_height
        self._ref_vis_w = metrics.visible_width
        self._ref_vis_h = metrics.visible_height

        self.btn_apply_canvas.config(text=f"🎯 Đặt Canvas cũ ({metrics.canvas_width}x{metrics.canvas_height})")
        self.btn_apply_vis.config(text=f"👤 Đặt ĐỘ PHÂN GIẢI THẬT ({metrics.visible_width}x{metrics.visible_height})")

        self.ref_info_text.config(state="normal")
        self.ref_info_text.delete("1.0", tk.END)
        self.ref_info_text.insert(tk.END, metrics.summary_text)
        self.ref_info_text.config(state="disabled")

    def update_prompt_results(self, results: Dict[str, Any]):
        self.style_lbl.config(text=results.get("style_analysis", ""))
        self.pos_prompt_text.delete("1.0", tk.END)
        self.pos_prompt_text.insert(tk.END, results.get("positive_prompt", ""))
        self.neg_prompt_text.delete("1.0", tk.END)
        self.neg_prompt_text.insert(tk.END, results.get("negative_prompt", ""))

    def update_batch_info(self, current_index: int, total_count: int, filename: str):
        if total_count > 1:
            self.batch_info_label.config(text=f"[{current_index + 1}/{total_count}] {filename}")
            self.btn_sprite_size.config(text=f"📐 Sprite Size HÀNG LOẠT ({total_count} ảnh)")
            self.btn_exp_batch.config(state="normal", text=f"📂 Xuất HÀNG LOẠT ({total_count} ảnh)...")
        else:
            self.batch_info_label.config(text=filename if total_count == 1 else "Chưa nạp ảnh.")
            self.btn_sprite_size.config(text="📐 Sprite Size (LibreSprite)")
            self.btn_exp_batch.config(state="disabled", text="📂 Xuất hàng loạt...")

    def update_norm_info(self, info_text: str):
        self.norm_info_label.config(text=info_text)

    def set_strip_frames_suggestion(self, num_frames: int):
        self.strip_frames_var.set(str(num_frames))

    def _render_to_canvas(self, canvas: tk.Canvas, img: Image.Image) -> ImageTk.PhotoImage:
        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        if cw <= 1:
            cw, ch = 260, 180

        tile_size = 12
        checker = Image.new("RGBA", (cw, ch), (40, 40, 43, 255))
        cdraw = ImageDraw.Draw(checker)
        for y in range(0, ch, tile_size):
            for x in range(0, cw, tile_size):
                if ((x // tile_size) + (y // tile_size)) % 2 == 0:
                    cdraw.rectangle([x, y, x + tile_size - 1, y + tile_size - 1], fill=(52, 52, 56, 255))

        w, h = img.size
        scale = min(cw / max(w, 1), ch / max(h, 1))
        if scale > 1.5:
            scale = int(scale)
        scale = max(0.05, scale)

        disp_w = max(1, int(round(w * scale)))
        disp_h = max(1, int(round(h * scale)))

        resized = img.resize((disp_w, disp_h), Image.Resampling.NEAREST).convert("RGBA")

        px = (cw - disp_w) // 2
        py = (ch - disp_h) // 2
        checker.paste(resized, (px, py), mask=resized)

        photo = ImageTk.PhotoImage(checker)
        canvas.delete("all")
        canvas.create_image(0, 0, anchor="nw", image=photo)
        return photo
