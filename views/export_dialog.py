import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Tuple
from PIL import Image
import numpy as np


class ExportDialog(tk.Toplevel):
    """
    Hộp thoại Export chuẩn LibreSprite / Aseprite:
    - Chọn đường dẫn và định dạng xuất (PNG, JPG, WEBP)
    - Resize theo tỉ lệ phóng đại nguyên (100%, 200%, 300%, 400%, 800%...)
    - Thuật toán Nearest-neighbor giữ pixel sắc nét
    - Chọn vùng xuất: Toàn bộ Canvas hoặc Cắt sát nhân vật (Trim)
    """

    def __init__(self, parent, image_to_export: Image.Image, default_filename: str = "sprite_export.png", default_dir: Optional[str] = None):
        super().__init__(parent)
        self.title("Export File - Chuẩn LibreSprite")
        self.geometry("480x420")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.source_image = image_to_export.copy().convert("RGBA")
        self.orig_w, self.orig_h = self.source_image.size
        self.exported_path: Optional[str] = None

        if not default_dir or not os.path.exists(default_dir):
            default_dir = os.getcwd()
        self.default_output_path = os.path.join(default_dir, default_filename)

        self.configure(bg="#252526")
        self._create_widgets()

        # Center relative to parent
        self.update_idletasks()
        try:
            x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
            y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
            self.geometry(f"+{max(10, x)}+{max(10, y)}")
        except Exception:
            pass

    def _create_widgets(self):
        main_frame = tk.Frame(self, bg="#252526", padx=16, pady=16)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ------------------ 1. OUTPUT FILE ------------------
        tk.Label(main_frame, text="Output File (Đường dẫn lưu file):", 
                 font=("Segoe UI", 9, "bold"), fg="#4ec9b0", bg="#252526").pack(anchor="w", pady=(0, 4))

        path_row = tk.Frame(main_frame, bg="#252526")
        path_row.pack(fill=tk.X, pady=(0, 12))

        self.path_var = tk.StringVar(value=self.default_output_path)
        self.path_entry = tk.Entry(path_row, textvariable=self.path_var, bg="#3c3c3c", fg="#ffffff", 
                                   insertbackground="white", font=("Segoe UI", 9))
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        btn_browse = tk.Button(path_row, text="...", width=4, bg="#3e3e42", fg="#ffffff",
                               font=("Segoe UI", 9, "bold"), relief="flat", command=self._browse_path)
        btn_browse.pack(side=tk.RIGHT)

        # ------------------ 2. RESIZE SCALE ------------------
        tk.Label(main_frame, text="Resize (Tỉ lệ phóng đại Pixel Art):", 
                 font=("Segoe UI", 9, "bold"), fg="#cccccc", bg="#252526").pack(anchor="w", pady=(0, 4))

        scale_row = tk.Frame(main_frame, bg="#252526")
        scale_row.pack(fill=tk.X, pady=(0, 10))

        scale_options = [
            f"100% (1x) - {self.orig_w}x{self.orig_h} px (Chuẩn đưa vào Game Engine)",
            f"200% (2x) - {self.orig_w*2}x{self.orig_h*2} px",
            f"300% (3x) - {self.orig_w*3}x{self.orig_h*3} px",
            f"400% (4x) - {self.orig_w*4}x{self.orig_h*4} px (Xem trước sắc nét)",
            f"800% (8x) - {self.orig_w*8}x{self.orig_h*8} px (Đăng mạng xã hội/Portfolio)",
            "Tùy chỉnh kích thước..."
        ]

        self.scale_var = tk.StringVar(value=scale_options[0])
        self.scale_combo = ttk.Combobox(scale_row, textvariable=self.scale_var, values=scale_options, 
                                        state="readonly", font=("Segoe UI", 9))
        self.scale_combo.pack(fill=tk.X)
        self.scale_combo.bind("<<ComboboxSelected>>", self._on_scale_selected)

        # Khung nhập kích thước tùy chỉnh (mặc định ẩn)
        self.custom_frame = tk.Frame(main_frame, bg="#252526")
        tk.Label(self.custom_frame, text="Rộng:", fg="#888888", bg="#252526").pack(side=tk.LEFT)
        self.custom_w_var = tk.StringVar(value=str(self.orig_w))
        tk.Entry(self.custom_frame, textvariable=self.custom_w_var, width=6, bg="#3c3c3c", fg="#fff").pack(side=tk.LEFT, padx=4)
        tk.Label(self.custom_frame, text="Cao:", fg="#888888", bg="#252526").pack(side=tk.LEFT, padx=(6, 0))
        self.custom_h_var = tk.StringVar(value=str(self.orig_h))
        tk.Entry(self.custom_frame, textvariable=self.custom_h_var, width=6, bg="#3c3c3c", fg="#fff").pack(side=tk.LEFT, padx=4)

        # ------------------ 3. AREA & BACKGROUND ------------------
        area_row = tk.Frame(main_frame, bg="#252526")
        area_row.pack(fill=tk.X, pady=(6, 8))

        tk.Label(area_row, text="Vùng xuất (Area):", width=16, anchor="w", fg="#cccccc", bg="#252526", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.area_var = tk.StringVar(value="Toàn bộ Canvas (Khuyên dùng)")
        self.area_combo = ttk.Combobox(area_row, textvariable=self.area_var, 
                                       values=["Toàn bộ Canvas (Khuyên dùng)", "Cắt sát nhân vật (Trim Bounding Box)"],
                                       state="readonly", width=30)
        self.area_combo.pack(side=tk.LEFT)

        # Interpolation
        interp_row = tk.Frame(main_frame, bg="#252526")
        interp_row.pack(fill=tk.X, pady=(4, 12))
        tk.Label(interp_row, text="Thuật toán (Filter):", width=16, anchor="w", fg="#cccccc", bg="#252526", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self.interp_var = tk.StringVar(value="Nearest-neighbor (Pixel Perfect)")
        self.interp_combo = ttk.Combobox(interp_row, textvariable=self.interp_var,
                                         values=["Nearest-neighbor (Pixel Perfect)", "Bilinear", "Bicubic"],
                                         state="readonly", width=30)
        self.interp_combo.pack(side=tk.LEFT)

        # Thông báo kích thước xuất dự kiến
        self.preview_info_lbl = tk.Label(main_frame, text=f"Kích thước xuất: {self.orig_w} x {self.orig_h} px",
                                         fg="#4ec9b0", bg="#252526", font=("Segoe UI", 9, "bold"))
        self.preview_info_lbl.pack(anchor="w", pady=(0, 14))

        # ------------------ 4. BUTTONS EXPORT / CANCEL ------------------
        btn_row = tk.Frame(main_frame, bg="#252526")
        btn_row.pack(side=tk.BOTTOM, fill=tk.X)

        btn_export = tk.Button(btn_row, text="Export", width=12, bg="#0e639c", fg="#ffffff", 
                               font=("Segoe UI", 10, "bold"), relief="flat", pady=5, command=self._on_export)
        btn_export.pack(side=tk.LEFT, padx=(20, 10))

        btn_cancel = tk.Button(btn_row, text="Cancel", width=12, bg="#555555", fg="#ffffff", 
                               font=("Segoe UI", 10), relief="flat", pady=5, command=self.destroy)
        btn_cancel.pack(side=tk.RIGHT, padx=(10, 20))

    def _on_scale_selected(self, event=None):
        sel = self.scale_var.get()
        if "Tùy chỉnh" in sel:
            self.custom_frame.pack(fill=tk.X, pady=(0, 8))
            self.preview_info_lbl.config(text=f"Kích thước xuất: Tùy chỉnh (Nhập ở trên)")
        else:
            self.custom_frame.pack_forget()
            if "100%" in sel:
                scale = 1
            elif "200%" in sel:
                scale = 2
            elif "300%" in sel:
                scale = 3
            elif "400%" in sel:
                scale = 4
            elif "800%" in sel:
                scale = 8
            else:
                scale = 1
            w = self.orig_w * scale
            h = self.orig_h * scale
            self.preview_info_lbl.config(text=f"Kích thước xuất: {w} x {h} px ({scale}x)")

    def _browse_path(self):
        curr_path = self.path_var.get()
        init_dir = os.path.dirname(curr_path) if curr_path else os.getcwd()
        init_file = os.path.basename(curr_path) if curr_path else "sprite_export.png"

        new_path = filedialog.asksaveasfilename(
            parent=self,
            title="Chọn đường dẫn xuất file",
            initialdir=init_dir,
            initialfile=init_file,
            defaultextension=".png",
            filetypes=[("PNG Image (*.png)", "*.png"), ("All Files", "*.*")]
        )
        if new_path:
            self.path_var.set(new_path)

    def _on_export(self):
        out_path = self.path_var.get().strip()
        if not out_path:
            messagebox.showerror("Lỗi", "Vui lòng chỉ định đường dẫn lưu file!", parent=self)
            return

        # Đảm bảo có đuôi .png nếu người dùng quên gõ
        if not os.path.splitext(out_path)[1]:
            out_path += ".png"

        try:
            # 1. Xử lý vùng xuất (Area: Canvas hay Trim)
            img = self.source_image.copy()
            if "Trim" in self.area_var.get():
                arr = np.array(img)
                alpha = arr[:, :, 3]
                mask = alpha > 10
                if np.any(mask):
                    y_idx, x_idx = np.where(mask)
                    img = img.crop((int(x_idx.min()), int(y_idx.min()), int(x_idx.max()) + 1, int(y_idx.max()) + 1))

            # 2. Xử lý Resize
            sel_scale = self.scale_var.get()
            if "Tùy chỉnh" in sel_scale:
                try:
                    final_w = int(self.custom_w_var.get())
                    final_h = int(self.custom_h_var.get())
                except ValueError:
                    messagebox.showerror("Lỗi", "Kích thước tùy chỉnh phải là số nguyên hợp lệ!", parent=self)
                    return
            else:
                scale = 1
                if "200%" in sel_scale:
                    scale = 2
                elif "300%" in sel_scale:
                    scale = 3
                elif "400%" in sel_scale:
                    scale = 4
                elif "800%" in sel_scale:
                    scale = 8
                final_w = img.width * scale
                final_h = img.height * scale

            # 3. Thuật toán nội suy
            interp = Image.Resampling.NEAREST
            if "Bilinear" in self.interp_var.get():
                interp = Image.Resampling.BILINEAR
            elif "Bicubic" in self.interp_var.get():
                interp = Image.Resampling.BICUBIC

            final_img = img.resize((max(1, final_w), max(1, final_h)), resample=interp)

            # 4. Lưu ra file
            os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
            final_img.save(out_path, format="PNG")

            self.exported_path = out_path
            self.destroy()

        except Exception as e:
            messagebox.showerror("Lỗi khi xuất file", f"Không thể xuất file:\n{str(e)}", parent=self)
