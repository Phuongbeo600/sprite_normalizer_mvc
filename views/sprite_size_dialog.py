import tkinter as tk
from tkinter import ttk
from typing import Optional, Tuple


class SpriteSizeDialog(tk.Toplevel):
    """
    Hộp thoại mô phỏng chính xác giao diện và logic của 'Sprite Size' trong LibreSprite/Aseprite:
    - Lấy chuẩn xác độ phân giải của ẢNH ĐANG XÉT
    - Đề xuất cả 2 thông số chuẩn của nhân vật cũ:
        1. Kích thước Canvas cũ (ví dụ 115 x 128 px)
        2. ĐỘ PHÂN GIẢI THẬT (Kích thước phần vẽ thực tế, ví dụ 79 x 114 px)
    - Pixels: Width / Height px
    - Lock Ratio (Khóa tỉ lệ)
    - Percentage: Width / Height %
    - Interpolation: Nearest-neighbor, Bilinear, Bicubic
    """

    def __init__(
        self,
        parent,
        current_width: int,
        current_height: int,
        ref_width: Optional[int] = None,
        ref_height: Optional[int] = None,
        ref_vis_width: Optional[int] = None,
        ref_vis_height: Optional[int] = None,
        image_label_desc: str = "Ảnh đang xét",
        batch_count: int = 1
    ):
        super().__init__(parent)
        self.title("Sprite Size (LibreSprite Clone)")
        self.geometry("420x510")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.orig_w = max(1, current_width)
        self.orig_h = max(1, current_height)
        self.ref_w = ref_width
        self.ref_h = ref_height
        self.ref_vis_w = ref_vis_width
        self.ref_vis_h = ref_vis_height
        self.image_label_desc = image_label_desc
        self.batch_count = batch_count
        
        self.result: Optional[Tuple[int, int, str]] = None
        self._updating = False

        self.configure(bg="#2d2d30")
        self._create_widgets()
        self._sync_from_pixels(self.orig_w, self.orig_h)

        self.update_idletasks()
        try:
            x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
            y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
            self.geometry(f"+{max(10, x)}+{max(10, y)}")
        except Exception:
            pass

    def _create_widgets(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        
        main_frame = tk.Frame(self, bg="#252526", padx=16, pady=12)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ------------------ THÔNG TIN ĐỘ PHÂN GIẢI HIỆN TẠI ------------------
        info_header = tk.Frame(main_frame, bg="#252526")
        info_header.pack(fill=tk.X, pady=(0, 8))

        desc_text = f"📌 {self.image_label_desc}"
        if self.batch_count > 1:
            desc_text += f" (Hàng loạt: {self.batch_count} ảnh)"
        tk.Label(info_header, text=desc_text, font=("Segoe UI", 9, "bold"), 
                 fg="#dcdcaa" if self.batch_count > 1 else "#858585", bg="#252526").pack(side=tk.LEFT)
        tk.Label(info_header, text=f"{self.orig_w} x {self.orig_h} px", font=("Consolas", 10, "bold"), 
                 fg="#4ec9b0", bg="#252526").pack(side=tk.RIGHT)

        # ------------------ ĐỀ XUẤT ĐỘ PHÂN GIẢI TỪ NHÂN VẬT CŨ ------------------
        if self.ref_w or self.ref_vis_w:
            preset_frame = tk.LabelFrame(main_frame, text=" 💡 Đề xuất độ phân giải (từ nhân vật cũ) ", 
                                         bg="#252526", fg="#4ec9b0", font=("Segoe UI", 8, "bold"), padx=6, pady=5)
            preset_frame.pack(fill=tk.X, pady=(0, 10))

            if self.ref_w and self.ref_h:
                btn_ref_canvas = tk.Button(
                    preset_frame, 
                    text=f"🎯 Đề xuất Canvas: {self.ref_w} x {self.ref_h} px",
                    bg="#0e639c", fg="#ffffff", font=("Segoe UI", 8, "bold"), relief="flat", padx=6, pady=2,
                    command=lambda: self._apply_custom_size(self.ref_w, self.ref_h)
                )
                btn_ref_canvas.pack(fill=tk.X, pady=2)

            if self.ref_vis_w and self.ref_vis_h:
                btn_ref_vis = tk.Button(
                    preset_frame, 
                    text=f"👤 Đề xuất ĐỘ PHÂN GIẢI THẬT: {self.ref_vis_w} x {self.ref_vis_h} px (Phần vẽ thực)",
                    bg="#2e7d32", fg="#ffffff", font=("Segoe UI", 8, "bold"), relief="flat", padx=6, pady=2,
                    command=lambda: self._apply_custom_size(self.ref_vis_w, self.ref_vis_h)
                )
                btn_ref_vis.pack(fill=tk.X, pady=2)

            btn_reset_curr = tk.Button(
                preset_frame,
                text=f"🔄 Kích thước gốc ảnh đang xét ({self.orig_w} x {self.orig_h} px)",
                bg="#333333", fg="#aaaaaa", font=("Segoe UI", 8), relief="flat", padx=6, pady=2,
                command=lambda: self._apply_custom_size(self.orig_w, self.orig_h)
            )
            btn_reset_curr.pack(fill=tk.X, pady=2)

        # ------------------ PHẦN PIXELS ------------------
        pixel_header = tk.Label(main_frame, text="-- Pixels: -----------------------------------------", 
                                fg="#858585", bg="#252526", font=("Consolas", 10))
        pixel_header.pack(anchor="w", pady=(2, 4))

        row1 = tk.Frame(main_frame, bg="#252526")
        row1.pack(fill=tk.X, pady=2)
        tk.Label(row1, text="Width:", width=8, anchor="w", fg="#cccccc", bg="#252526", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        self.width_var = tk.StringVar(value=str(self.orig_w))
        self.width_entry = tk.Entry(row1, textvariable=self.width_var, width=10, bg="#3c3c3c", fg="#ffffff", insertbackground="white")
        self.width_entry.pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(row1, text="px", fg="#888888", bg="#252526").pack(side=tk.LEFT)

        self.lock_ratio_var = tk.BooleanVar(value=True)
        self.lock_cb = tk.Checkbutton(row1, text="Lock Ratio", variable=self.lock_ratio_var, 
                                      bg="#252526", fg="#4ec9b0", selectcolor="#333333", 
                                      activebackground="#252526", activeforeground="#4ec9b0")
        self.lock_cb.pack(side=tk.RIGHT, padx=6)

        row2 = tk.Frame(main_frame, bg="#252526")
        row2.pack(fill=tk.X, pady=2)
        tk.Label(row2, text="Height:", width=8, anchor="w", fg="#cccccc", bg="#252526", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        self.height_var = tk.StringVar(value=str(self.orig_h))
        self.height_entry = tk.Entry(row2, textvariable=self.height_var, width=10, bg="#3c3c3c", fg="#ffffff", insertbackground="white")
        self.height_entry.pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(row2, text="px", fg="#888888", bg="#252526").pack(side=tk.LEFT)

        # ------------------ PHẦN PERCENTAGE ------------------
        pct_header = tk.Label(main_frame, text="-- Percentage: ------------------------------------", 
                              fg="#858585", bg="#252526", font=("Consolas", 10))
        pct_header.pack(anchor="w", pady=(8, 4))

        row3 = tk.Frame(main_frame, bg="#252526")
        row3.pack(fill=tk.X, pady=2)
        tk.Label(row3, text="Width:", width=8, anchor="w", fg="#cccccc", bg="#252526", font=("Arial", 9)).pack(side=tk.LEFT)
        self.pct_w_var = tk.StringVar(value="100.0")
        self.pct_w_entry = tk.Entry(row3, textvariable=self.pct_w_var, width=10, bg="#3c3c3c", fg="#ffffff", insertbackground="white")
        self.pct_w_entry.pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(row3, text="%", fg="#888888", bg="#252526").pack(side=tk.LEFT)

        row4 = tk.Frame(main_frame, bg="#252526")
        row4.pack(fill=tk.X, pady=2)
        tk.Label(row4, text="Height:", width=8, anchor="w", fg="#cccccc", bg="#252526", font=("Arial", 9)).pack(side=tk.LEFT)
        self.pct_h_var = tk.StringVar(value="100.0")
        self.pct_h_entry = tk.Entry(row4, textvariable=self.pct_h_var, width=10, bg="#3c3c3c", fg="#ffffff", insertbackground="white")
        self.pct_h_entry.pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(row4, text="%", fg="#888888", bg="#252526").pack(side=tk.LEFT)

        # ------------------ PHẦN INTERPOLATION ------------------
        interp_header = tk.Label(main_frame, text="-- Interpolation: ---------------------------------", 
                                 fg="#858585", bg="#252526", font=("Consolas", 10))
        interp_header.pack(anchor="w", pady=(8, 4))

        row5 = tk.Frame(main_frame, bg="#252526")
        row5.pack(fill=tk.X, pady=2)
        tk.Label(row5, text="Method:", width=8, anchor="w", fg="#cccccc", bg="#252526", font=("Arial", 9)).pack(side=tk.LEFT)
        
        self.method_var = tk.StringVar(value="Nearest-neighbor")
        self.method_combo = ttk.Combobox(row5, textvariable=self.method_var, 
                                         values=["Nearest-neighbor", "Bilinear", "Bicubic"], 
                                         state="readonly", width=18)
        self.method_combo.pack(side=tk.LEFT)

        # ------------------ BUTTONS OK / CANCEL ------------------
        btn_frame = tk.Frame(main_frame, bg="#252526")
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))

        ok_text = "OK (Áp dụng hàng loạt)" if self.batch_count > 1 else "OK"
        btn_ok = tk.Button(btn_frame, text=ok_text, width=20 if self.batch_count > 1 else 12, 
                           bg="#339933", fg="#ffffff", font=("Segoe UI", 9, "bold"), relief="flat", pady=4, command=self._on_ok)
        btn_ok.pack(side=tk.LEFT, padx=(10, 10))

        btn_cancel = tk.Button(btn_frame, text="Cancel", width=10, bg="#555555", fg="#ffffff", 
                               font=("Segoe UI", 9), relief="flat", pady=4, command=self._on_cancel)
        btn_cancel.pack(side=tk.RIGHT, padx=(10, 10))

        # Bind events
        self.width_var.trace_add("write", self._on_width_changed)
        self.height_var.trace_add("write", self._on_height_changed)
        self.pct_w_var.trace_add("write", self._on_pct_w_changed)
        self.pct_h_var.trace_add("write", self._on_pct_h_changed)

    def _apply_custom_size(self, w: int, h: int):
        old_lock = self.lock_ratio_var.get()
        self.lock_ratio_var.set(False)
        self._sync_from_pixels(w, h)
        self.lock_ratio_var.set(old_lock)

    def _sync_from_pixels(self, w: int, h: int):
        self._updating = True
        self.width_var.set(str(w))
        self.height_var.set(str(h))
        self.pct_w_var.set(f"{(w / self.orig_w) * 100:.1f}")
        self.pct_h_var.set(f"{(h / self.orig_h) * 100:.1f}")
        self._updating = False

    def _on_width_changed(self, *args):
        if self._updating:
            return
        try:
            w = int(self.width_var.get())
            if w <= 0:
                return
            self._updating = True
            if self.lock_ratio_var.get():
                h = max(1, int(round(w * self.orig_h / self.orig_w)))
                self.height_var.set(str(h))
            else:
                h = int(self.height_var.get())
            self.pct_w_var.set(f"{(w / self.orig_w) * 100:.1f}")
            self.pct_h_var.set(f"{(h / self.orig_h) * 100:.1f}")
            self._updating = False
        except ValueError:
            pass

    def _on_height_changed(self, *args):
        if self._updating:
            return
        try:
            h = int(self.height_var.get())
            if h <= 0:
                return
            self._updating = True
            if self.lock_ratio_var.get():
                w = max(1, int(round(h * self.orig_w / self.orig_h)))
                self.width_var.set(str(w))
            else:
                w = int(self.width_var.get())
            self.pct_w_var.set(f"{(w / self.orig_w) * 100:.1f}")
            self.pct_h_var.set(f"{(h / self.orig_h) * 100:.1f}")
            self._updating = False
        except ValueError:
            pass

    def _on_pct_w_changed(self, *args):
        if self._updating:
            return
        try:
            pct_w = float(self.pct_w_var.get())
            if pct_w <= 0:
                return
            self._updating = True
            w = max(1, int(round(self.orig_w * (pct_w / 100.0))))
            self.width_var.set(str(w))
            if self.lock_ratio_var.get():
                self.pct_h_var.set(f"{pct_w:.1f}")
                h = max(1, int(round(self.orig_h * (pct_w / 100.0))))
                self.height_var.set(str(h))
            self._updating = False
        except ValueError:
            pass

    def _on_pct_h_changed(self, *args):
        if self._updating:
            return
        try:
            pct_h = float(self.pct_h_var.get())
            if pct_h <= 0:
                return
            self._updating = True
            h = max(1, int(round(self.orig_h * (pct_h / 100.0))))
            self.height_var.set(str(h))
            if self.lock_ratio_var.get():
                self.pct_w_var.set(f"{pct_h:.1f}")
                w = max(1, int(round(self.orig_h * (pct_h / 100.0))))
                self.width_var.set(str(w))
            self._updating = False
        except ValueError:
            pass

    def _on_ok(self):
        try:
            w = int(self.width_var.get())
            h = int(self.height_var.get())
            method = self.method_var.get()
            self.result = (w, h, method)
            self.destroy()
        except ValueError:
            pass

    def _on_cancel(self):
        self.result = None
        self.destroy()
