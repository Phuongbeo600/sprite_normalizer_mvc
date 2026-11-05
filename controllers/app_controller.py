import os
import json
from typing import Optional, Dict, Any, List, Tuple
from PIL import Image
import numpy as np
from tkinter import messagebox, filedialog

from models.character_analyzer import CharacterAnalyzer, CharacterMetrics
from models.prompt_advisor import PromptAdvisor
from models.sprite_resizer import SpriteResizer
from models.strip_animator import AnimationStripModel
from views.main_view import MainView
from views.sprite_size_dialog import SpriteSizeDialog
from views.export_dialog import ExportDialog


class AppController:
    """
    Controller trong mô hình MVC.
    Điều phối luồng dữ liệu & sự kiện:
    - Cắt dải AI thành các "TẤM" độc lập giữ trọn cả bìa & không bao giờ cắt phạm nhân vật
    - Quản lý 1 hoặc NHIỀU ảnh Sprite (Batch Processing)
    - Hiển thị & Đề xuất ĐỘ PHÂN GIẢI THẬT (Phần vẽ thực tế)
    - Batch Sprite Size hàng loạt và Xuất thư mục
    """

    def __init__(self, view: MainView, config_path: str = "config.json"):
        self.view = view
        self.config_path = config_path

        # State nhân vật mẫu cũ
        self.ref_image_path: Optional[str] = None
        self.ref_image_raw: Optional[Image.Image] = None
        self.ref_metrics: Optional[CharacterMetrics] = None

        # State nạp 1 hoặc NHIỀU ảnh (Batch State)
        self.batch_file_paths: List[str] = []
        self.batch_raw_images: List[Image.Image] = []
        self.batch_processed_images: List[Image.Image] = []
        self.current_batch_index: int = 0

        # State ảnh đang xét hiển thị
        self.current_working_image: Optional[Image.Image] = None
        self.final_sprite: Optional[Image.Image] = None

        # State các tấm hoạt cảnh
        self.animated_frames: List[Image.Image] = []

        self.api_key: Optional[str] = None
        self._load_config()
        self._bind_view_events()

    def _load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.api_key = data.get("gemini_api_key", None)
            except Exception:
                pass

    def _save_config(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump({"gemini_api_key": self.api_key or ""}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print("Không thể lưu config:", e)

    def _bind_view_events(self):
        self.view.on_select_ref_image = self.handle_select_ref_image
        self.view.on_toggle_overlay = self.handle_toggle_overlay
        self.view.on_generate_prompt = self.handle_generate_prompt
        self.view.on_select_new_images = self.handle_select_new_images
        self.view.on_batch_navigate = self.handle_batch_navigate
        self.view.on_open_sprite_size_dialog = self.handle_open_sprite_size_dialog
        self.view.on_apply_preset_size = self.handle_apply_preset_size
        self.view.on_auto_standardize = self.handle_auto_standardize
        self.view.on_split_strip = self.handle_split_strip
        self.view.on_export_frames_folder = self.handle_export_frames_folder
        self.view.on_export_batch_folder = self.handle_export_batch_folder
        self.view.on_export_gif = self.handle_export_gif
        self.view.on_save_final_sprite = self.handle_save_final_sprite
        self.view.on_export_sprite = self.handle_export_sprite
        self.view.on_save_api_key = self.handle_save_api_key

    # ------------------ HELPER ĐO ĐỘ PHÂN GIẢI THẬT ------------------
    @staticmethod
    def _get_visible_dimensions(image: Image.Image) -> Tuple[int, int]:
        """Đo kích thước phần vẽ thực tế (Visible size), loại bỏ vùng alpha/nền trong suốt."""
        img_rgba = image.convert("RGBA")
        arr = np.array(img_rgba)
        alpha = arr[:, :, 3]
        mask = alpha > 15
        if not np.any(mask):
            return image.size
        y_idx, x_idx = np.where(mask)
        vis_w = int(x_idx.max() - x_idx.min() + 1)
        vis_h = int(y_idx.max() - y_idx.min() + 1)
        return vis_w, vis_h

    def _update_norm_info_display(self):
        """Cập nhật nhãn hiển thị cả kích thước Canvas và Độ phân giải thật."""
        if not self.current_working_image:
            self.view.update_norm_info("Độ phân giải: Chưa có ảnh")
            return
        w, h = self.current_working_image.size
        vis_w, vis_h = self._get_visible_dimensions(self.current_working_image)
        self.view.update_norm_info(f"Canvas: {w} x {h} px  |  Độ phân giải THẬT: {vis_w} x {vis_h} px")

    # ------------------ XỬ LÝ NHÂN VẬT CŨ (REFERENCE) ------------------
    def handle_select_ref_image(self, file_path: str):
        try:
            self.ref_image_path = file_path
            self.ref_image_raw = Image.open(file_path).convert("RGBA")
            
            metrics = CharacterAnalyzer.analyze(self.ref_image_raw)
            if not metrics:
                self.view.set_status("Không tìm thấy pixel nhân vật (ảnh trống hoặc toàn bộ trong suốt)!", is_error=True)
                return

            self.ref_metrics = metrics
            self.view.update_ref_metrics(metrics)
            
            self._render_ref_display()
            self.view.set_status(f"Đã phân tích: {os.path.basename(file_path)} (Canvas: {metrics.canvas_width}x{metrics.canvas_height}, Thật: {metrics.visible_width}x{metrics.visible_height})")
            
            self.handle_generate_prompt({
                "head_rule": self.view.head_rule_var.get(),
                "body_width_rule": self.view.body_w_rule_var.get(),
                "body_height_rule": self.view.body_h_rule_var.get(),
                "concept": self.view.concept_var.get()
            })
        except Exception as e:
            self.view.set_status(f"Lỗi khi đọc ảnh cũ: {str(e)}", is_error=True)
            messagebox.showerror("Lỗi", f"Không thể đọc file ảnh cũ:\n{str(e)}")

    def handle_toggle_overlay(self, show_overlay: bool):
        if self.ref_image_raw and self.ref_metrics:
            self._render_ref_display()

    def _render_ref_display(self):
        if not self.ref_image_raw or not self.ref_metrics:
            return
        if self.view.show_overlay_var.get():
            annotated = CharacterAnalyzer.draw_annotated_image(self.ref_image_raw, self.ref_metrics)
            self.view.display_ref_image(annotated)
        else:
            self.view.display_ref_image(self.ref_image_raw)

    # ------------------ XỬ LÝ SINH PROMPT ------------------
    def handle_generate_prompt(self, options: Dict[str, Any]):
        if not self.ref_metrics:
            self.view.set_status("Vui lòng nạp ảnh Sprite cũ trước khi tạo Prompt!", is_error=True)
            return

        self.view.set_status("Đang phân tích và tạo Prompt...")
        try:
            results = PromptAdvisor.generate_prompt(
                metrics=self.ref_metrics,
                head_rule=options.get("head_rule", "Bằng nhân vật cũ"),
                body_width_rule=options.get("body_width_rule", "Bằng nhân vật cũ"),
                body_height_rule=options.get("body_height_rule", "Bằng nhân vật cũ"),
                character_concept=options.get("concept", "Chiến binh quái vật"),
                api_key=self.api_key
            )
            self.view.update_prompt_results(results)
            self.view.set_status(results.get("api_status", "Đã tạo prompt thành công!"))
        except Exception as e:
            self.view.set_status(f"Lỗi tạo prompt: {str(e)}", is_error=True)

    # ------------------ XỬ LÝ NẠP 1 HOẶC NHIỀU ẢNH (BATCH) ------------------
    def handle_select_new_images(self, file_paths: List[str]):
        if not file_paths:
            return

        try:
            self.batch_file_paths = file_paths
            self.batch_raw_images = [Image.open(p).convert("RGBA") for p in file_paths]
            self.batch_processed_images = [img.copy() for img in self.batch_raw_images]
            self.current_batch_index = 0

            self.current_working_image = self.batch_processed_images[0]
            self.final_sprite = self.current_working_image
            self.animated_frames = []
            self.view.set_animation_frames([])

            curr_fn = os.path.basename(file_paths[0])
            self.view.update_batch_info(0, len(file_paths), curr_fn)
            self.view.display_norm_image(self.current_working_image)
            self._update_norm_info_display()

            if len(file_paths) == 1:
                strip_info = AnimationStripModel.detect_strip(self.current_working_image)
                if strip_info["is_strip"]:
                    self.view.set_strip_frames_suggestion(strip_info["suggested_frames"])
                    self.view.set_status(f"🎞️ Phát hiện dải ({strip_info['suggested_frames']} frame). Bấm '⚡ Cắt Dải' để tách thành {strip_info['suggested_frames']} tấm an toàn!")
                else:
                    self.view.set_status(f"Đã nạp ảnh: {curr_fn}")
            else:
                self.view.set_status(f"Đã nạp {len(file_paths)} ảnh. Bạn có thể bấm 'Sprite Size Hàng Loạt'!")
        except Exception as e:
            self.view.set_status(f"Lỗi đọc ảnh mới: {str(e)}", is_error=True)
            messagebox.showerror("Lỗi", f"Không thể đọc file ảnh mới:\n{str(e)}")

    def handle_batch_navigate(self, direction: int):
        if not self.batch_processed_images:
            return
        total = len(self.batch_processed_images)
        self.current_batch_index = (self.current_batch_index + direction) % total
        self.current_working_image = self.batch_processed_images[self.current_batch_index]
        self.final_sprite = self.current_working_image

        fn = os.path.basename(self.batch_file_paths[self.current_batch_index])
        self.view.update_batch_info(self.current_batch_index, total, fn)
        self.view.display_norm_image(self.current_working_image)
        self._update_norm_info_display()

    # ------------------ XỬ LÝ CẮT DẢI THÀNH CÁC TẤM (KHÔNG CẮT VÀO NHÂN VẬT) ------------------
    def handle_split_strip(self, num_frames: int, keep_full_bounds: bool = True):
        source_img = self.batch_raw_images[self.current_batch_index] if self.batch_raw_images else self.current_working_image
        if not source_img:
            messagebox.showwarning("Chưa có ảnh", "Vui lòng nạp ảnh dải hoạt ảnh ở Cột 3!")
            return

        self.view.set_status(f"Đang phân tích khe hở an toàn và cắt dải thành {num_frames} tấm...")

        try:
            # Thuật toán cắt thành các tấm độc lập (giữ trọn cả bìa, an toàn tuyệt đối)
            result = AnimationStripModel.split_into_cards(
                image=source_img,
                num_frames=num_frames,
                auto_remove_bg=True
            )

            cards = result["cards"]
            self.animated_frames = cards
            self.batch_raw_images = [c.copy() for c in cards]
            self.batch_processed_images = [c.copy() for c in cards]
            
            orig_name = "tam"
            if self.batch_file_paths:
                orig_name = os.path.splitext(os.path.basename(self.batch_file_paths[self.current_batch_index]))[0]
            self.batch_file_paths = [f"{orig_name}_tam_{i+1}.png" for i in range(num_frames)]

            self.current_batch_index = 0
            self.current_working_image = self.batch_processed_images[0]
            self.final_sprite = result["spritesheet"]

            # Cập nhật giao diện
            self.view.update_batch_info(0, num_frames, self.batch_file_paths[0])
            self.view.set_animation_frames(cards)
            self._update_norm_info_display()

            self.view.set_status(
                f"✅ Đã cắt an toàn thành {num_frames} tấm (0% cắt phạm nhân vật, giữ trọn bìa)! Khổ: {result['card_width']}x{result['card_height']} px"
            )
        except Exception as e:
            self.view.set_status(f"Lỗi cắt dải: {str(e)}", is_error=True)
            messagebox.showerror("Lỗi cắt dải hoạt cảnh", f"Gặp lỗi khi cắt dải:\n{str(e)}")

    # ------------------ ĐẶT NHANH ĐỘ PHÂN GIẢI THẬT / CANVAS ------------------
    def handle_apply_preset_size(self, target_w: int, target_h: int):
        """Đặt nhanh kích thước (Canvas hoặc Độ phân giải thật) cho ảnh đang xét hoặc hàng loạt."""
        if not self.batch_processed_images and not self.current_working_image:
            messagebox.showwarning("Chưa có ảnh", "Vui lòng nạp ảnh mới ở Cột 3 trước!")
            return

        batch_count = len(self.batch_raw_images)
        self.view.set_status(f"Đang áp dụng độ phân giải {target_w}x{target_h} px (Nearest-neighbor)...")

        if batch_count > 1:
            new_batch = []
            for raw_img in self.batch_raw_images:
                resized = SpriteResizer.resize_sprite(raw_img, target_w, target_h, method="Nearest-neighbor")
                new_batch.append(resized)
            self.batch_processed_images = new_batch
            self.current_working_image = self.batch_processed_images[self.current_batch_index]
            self.final_sprite = self.current_working_image
            if self.animated_frames:
                self.animated_frames = new_batch
                self.view.set_animation_frames(new_batch)
            else:
                self.view.display_norm_image(self.current_working_image)
            self._update_norm_info_display()
            self.view.set_status(f"Đã đặt {target_w}x{target_h} px cho toàn bộ {batch_count} ảnh thành công!")
        else:
            resized = SpriteResizer.resize_sprite(self.current_working_image, target_w, target_h, method="Nearest-neighbor")
            self.current_working_image = resized
            self.final_sprite = resized
            if self.batch_processed_images:
                self.batch_processed_images[0] = resized
            self.view.display_norm_image(resized)
            self._update_norm_info_display()
            self.view.set_status(f"Đã đổi kích thước thành {target_w}x{target_h} px sắc nét!")

    # ------------------ XỬ LÝ SPRITE SIZE (HÀNG LOẠT HOẶC ĐƠN) ------------------
    def handle_open_sprite_size_dialog(self):
        target_img = self.current_working_image or (self.batch_raw_images[0] if self.batch_raw_images else self.ref_image_raw)
        if not target_img:
            messagebox.showwarning("Chưa có ảnh", "Vui lòng nạp ảnh trước khi mở Sprite Size!")
            return

        curr_w, curr_h = target_img.size
        ref_w = self.ref_metrics.canvas_width if self.ref_metrics else None
        ref_h = self.ref_metrics.canvas_height if self.ref_metrics else None
        ref_vis_w = self.ref_metrics.visible_width if self.ref_metrics else None
        ref_vis_h = self.ref_metrics.visible_height if self.ref_metrics else None

        batch_count = max(1, len(self.batch_raw_images))

        dialog = SpriteSizeDialog(
            parent=self.view,
            current_width=curr_w,
            current_height=curr_h,
            ref_width=ref_w,
            ref_height=ref_h,
            ref_vis_width=ref_vis_w,
            ref_vis_height=ref_vis_h,
            image_label_desc="Ảnh đang thao tác",
            batch_count=batch_count
        )
        self.view.wait_window(dialog)

        if dialog.result:
            target_w, target_h, method = dialog.result
            self.view.set_status(f"Đang co giãn theo {target_w}x{target_h} px ({method})...")

            if batch_count > 1:
                new_batch = []
                for raw_img in self.batch_raw_images:
                    resized = SpriteResizer.resize_sprite(raw_img, target_w, target_h, method=method)
                    new_batch.append(resized)
                self.batch_processed_images = new_batch
                self.current_working_image = self.batch_processed_images[self.current_batch_index]
                self.final_sprite = self.current_working_image
                if self.animated_frames:
                    self.animated_frames = new_batch
                    self.view.set_animation_frames(new_batch)
                else:
                    self.view.display_norm_image(self.current_working_image)
                self._update_norm_info_display()
                self.view.set_status(f"Đã hoàn thành Sprite Size HÀNG LOẠT ({batch_count} ảnh) về {target_w}x{target_h} px!")
            else:
                resized = SpriteResizer.resize_sprite(target_img, target_w, target_h, method=method)
                self.current_working_image = resized
                self.final_sprite = resized
                self.animated_frames = []
                self.view.set_animation_frames([])
                self.view.display_norm_image(resized)
                self._update_norm_info_display()
                self.view.set_status(f"Đã hoàn thành Sprite Size: {target_w}x{target_h} px sắc nét!")

    # ------------------ XỬ LÝ CHUẨN HOÁ 1-CLICK ------------------
    def handle_auto_standardize(self):
        source_img = self.current_working_image or (self.batch_raw_images[0] if self.batch_raw_images else None)
        if not source_img:
            messagebox.showwarning("Chưa có ảnh mới", "Vui lòng nạp ảnh mới ở Cột 3!")
            return
        if not self.ref_metrics:
            messagebox.showwarning("Chưa có ảnh mẫu", "Vui lòng nạp ảnh Sprite cũ ở Cột 1!")
            return

        self.view.set_status("Đang tự động chuẩn hoá thông minh...")
        try:
            result = SpriteResizer.auto_standardize_to_reference(
                new_image=source_img,
                ref_metrics=self.ref_metrics,
                body_height_rule=self.view.body_h_rule_var.get(),
                body_width_rule=self.view.body_w_rule_var.get(),
                method="Nearest-neighbor",
                auto_remove_bg=True
            )
            self.current_working_image = result
            self.final_sprite = result
            self.animated_frames = []
            self.view.set_animation_frames([])
            self.view.display_norm_image(result)
            self._update_norm_info_display()
            self.view.set_status(f"Đã chuẩn hoá thành công về khung {result.width}x{result.height} px!")
        except Exception as e:
            self.view.set_status(f"Lỗi chuẩn hoá: {str(e)}", is_error=True)
            messagebox.showerror("Lỗi", f"Gặp lỗi khi chuẩn hoá:\n{str(e)}")

    # ------------------ XUẤT HÀNG LOẠT (BATCH EXPORT TẤT CẢ TẤM) ------------------
    def handle_export_batch_folder(self):
        if not self.batch_processed_images:
            messagebox.showwarning("Chưa có ảnh", "Vui lòng nạp hoặc cắt ảnh trước khi xuất!")
            return

        folder = filedialog.askdirectory(parent=self.view, title="Chọn thư mục lưu tất cả các tấm ảnh")
        if not folder:
            return

        try:
            saved_count = 0
            for i, img in enumerate(self.batch_processed_images):
                orig_fn = self.batch_file_paths[i] if i < len(self.batch_file_paths) else f"tam_{i+1}.png"
                base, ext = os.path.splitext(os.path.basename(orig_fn))
                out_path = os.path.join(folder, f"{base}.png")
                img.save(out_path, "PNG")
                saved_count += 1

            messagebox.showinfo(
                "Xuất hàng loạt thành công", 
                f"Đã lưu thành công tất cả {saved_count} tấm ảnh vào thư mục:\n{folder}"
            )
            self.view.set_status(f"Đã xuất hàng loạt {saved_count} tấm vào thư mục!")
        except Exception as e:
            messagebox.showerror("Lỗi xuất hàng loạt", f"Không thể lưu các file:\n{str(e)}")

    # ------------------ XUẤT FRAME RỜI ------------------
    def handle_export_frames_folder(self):
        images_to_export = self.animated_frames or self.batch_processed_images
        if not images_to_export:
            messagebox.showwarning("Chưa có ảnh", "Vui lòng bấm '⚡ Cắt Dải' trước khi xuất từng tấm!")
            return

        folder = filedialog.askdirectory(parent=self.view, title="Chọn thư mục để lưu các tấm ảnh (.png)")
        if not folder:
            return

        base_name = "tam"
        if self.batch_file_paths:
            base_name = os.path.splitext(os.path.basename(self.batch_file_paths[0]))[0]

        try:
            saved_paths = AnimationStripModel.export_frames_to_folder(
                frames=images_to_export,
                folder_path=folder,
                base_name=base_name
            )
            messagebox.showinfo("Xuất file thành công", f"Đã xuất thành công {len(saved_paths)} tấm vào:\n{folder}")
            self.view.set_status(f"Đã xuất {len(saved_paths)} tấm vào thư mục!")
        except Exception as e:
            messagebox.showerror("Lỗi xuất tấm ảnh", f"Không thể lưu các tấm:\n{str(e)}")

    # ------------------ XUẤT GIF ĐỘNG ------------------
    def handle_export_gif(self, fps: int):
        frames = self.animated_frames or self.batch_processed_images
        if not frames:
            messagebox.showwarning("Chưa có ảnh", "Vui lòng nạp hoặc cắt ảnh trước khi xuất GIF!")
            return

        default_fn = "animation_walk.gif"
        if self.batch_file_paths:
            default_fn = f"{os.path.splitext(os.path.basename(self.batch_file_paths[0]))[0]}_anim.gif"

        save_path = filedialog.asksaveasfilename(
            parent=self.view,
            title="Lưu ảnh động GIF",
            initialfile=default_fn,
            defaultextension=".gif",
            filetypes=[("Animated GIF (*.gif)", "*.gif")]
        )
        if not save_path:
            return

        try:
            AnimationStripModel.export_animated_gif(frames, save_path, fps=fps)
            messagebox.showinfo("Xuất GIF thành công", f"Đã lưu ảnh động GIF thành công vào:\n{save_path}")
            self.view.set_status(f"Đã xuất file GIF: {os.path.basename(save_path)}")
        except Exception as e:
            messagebox.showerror("Lỗi xuất GIF", f"Không thể lưu file GIF:\n{str(e)}")

    # ------------------ EXPORT SPRITESHEET & LƯU FILE ------------------
    def handle_export_sprite(self):
        img_to_export = self.final_sprite or self.current_working_image or self.ref_image_raw
        if not img_to_export:
            messagebox.showwarning("Chưa có ảnh", "Vui lòng nạp hoặc chuẩn hóa ảnh trước khi Export!")
            return

        ref_base = "sprite"
        if self.batch_file_paths:
            ref_base = os.path.splitext(os.path.basename(self.batch_file_paths[self.current_batch_index]))[0]
        elif self.ref_image_path:
            ref_base = os.path.splitext(os.path.basename(self.ref_image_path))[0]

        default_fn = f"{ref_base}-export.png"
        default_dir = os.path.dirname(self.batch_file_paths[0]) if self.batch_file_paths else (
            os.path.dirname(self.ref_image_path) if self.ref_image_path else os.getcwd()
        )

        dialog = ExportDialog(self.view, img_to_export, default_filename=default_fn, default_dir=default_dir)
        self.view.wait_window(dialog)

        if dialog.exported_path:
            messagebox.showinfo("Xuất file thành công", f"Đã xuất file thành công vào:\n{dialog.exported_path}")
            self.view.set_status(f"Đã xuất file: {os.path.basename(dialog.exported_path)}")

    def handle_save_final_sprite(self, save_path: str):
        img_to_save = self.final_sprite or self.current_working_image or self.ref_image_raw
        if not img_to_save:
            messagebox.showwarning("Chưa có ảnh", "Vui lòng nạp hoặc chuẩn hóa ảnh trước khi lưu!")
            return

        try:
            if not os.path.splitext(save_path)[1]:
                save_path += ".png"
            os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
            img_to_save.save(save_path, "PNG")

            if os.path.exists(save_path):
                messagebox.showinfo("Lưu thành công", f"Đã lưu Sprite thành công vào:\n{save_path}")
                self.view.set_status(f"Đã lưu: {os.path.basename(save_path)}")
            else:
                raise IOError("File không xuất hiện sau khi ghi đĩa.")
        except Exception as e:
            self.view.set_status(f"Lỗi khi lưu: {str(e)}", is_error=True)
            messagebox.showerror("Lỗi khi lưu", f"Không thể lưu file vào:\n{save_path}\n\nLỗi: {str(e)}")

    def handle_save_api_key(self, api_key: str):
        self.api_key = api_key if api_key.strip() else None
        self._save_config()
        self.view.set_status("Đã cập nhật cấu hình API Key thành công!")
