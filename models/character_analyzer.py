import os
from dataclasses import dataclass, asdict
from typing import Optional, Tuple, Dict, Any
import numpy as np
from PIL import Image, ImageDraw, ImageFont


@dataclass
class CharacterMetrics:
    canvas_width: int
    canvas_height: int
    
    # Bounding box toàn bộ nhân vật (phần nhìn thấy)
    visible_x_min: int
    visible_y_min: int
    visible_x_max: int
    visible_y_max: int
    visible_width: int
    visible_height: int
    
    # Vị trí cổ (ranh giới đầu và thân)
    neck_y: int
    
    # Phần Đầu (Head)
    head_x_min: int
    head_y_min: int
    head_x_max: int
    head_y_max: int
    head_width: int
    head_height: int
    
    # Phần Thân (Body = từ cổ đến chân)
    body_x_min: int
    body_y_min: int
    body_x_max: int
    body_y_max: int
    body_width: int
    body_height: int
    
    # Phần Ngực/Bụng (Torso - không tính chân)
    torso_height: int
    torso_width: int
    
    # Các tỉ lệ vàng quan trọng
    head_ratio: float               # head_height / visible_height (ví dụ 0.20 = 20%)
    heads_tall: float               # Chiều cao toàn thân tính bằng số đầu (ví dụ 2.5 đầu, 5.0 đầu)
    head_to_body_width_ratio: float # head_width / body_width
    body_aspect_ratio: float        # body_width / body_height
    
    # Nhận diện phong cách
    style_category: str             # "Chibi (2 - 2.5 đầu)", "Semi-Chibi (3 - 4 đầu)", "Tiêu chuẩn / Heroic (5+ đầu)"
    summary_text: str               # Tóm tắt nhanh bằng tiếng Việt


class CharacterAnalyzer:
    """
    Model phân tích hình học & giải phẫu học của Sprite Pixel Art bằng Computer Vision.
    - Tách kênh Alpha / Lọc phông nền
    - Xác định Bounding Box thực tế
    - Dùng biểu đồ Horizontal Projection Profile để nhận diện ranh giới cổ (Neck)
    - Tính kích thước Đầu, Thân và các tỉ lệ giải phẫu học
    """

    @staticmethod
    def extract_mask(image: Image.Image, auto_remove_solid_bg: bool = True, bg_tolerance: int = 25) -> Tuple[np.ndarray, Image.Image]:
        """
        Trích xuất mask boolean (True là pixel nhân vật, False là nền).
        Nếu ảnh không có alpha trong suốt (ảnh do AI sinh ra thường có nền trắng/đen/xanh),
        tự động phát hiện màu nền ở 4 góc và tách nền.
        """
        img_rgba = image.convert('RGBA')
        arr = np.array(img_rgba)
        alpha = arr[:, :, 3]
        
        # Kiểm tra xem ảnh có sẵn alpha trong suốt thực sự không
        has_transparency = np.any(alpha < 240)
        
        if has_transparency:
            mask = alpha > 25
            return mask, img_rgba
        
        # Nếu không có alpha (ảnh nền đặc do AI sinh ra)
        if auto_remove_solid_bg:
            rgb = arr[:, :, :3].astype(float)
            h, w = arr.shape[:2]
            corners = [
                rgb[0, 0],
                rgb[0, w - 1],
                rgb[h - 1, 0],
                rgb[h - 1, w - 1]
            ]
            # Tính màu nền trung bình từ 4 góc
            bg_color = np.mean(corners, axis=0)
            
            # Tính khoảng cách Euclidean màu
            color_diff = np.linalg.norm(rgb - bg_color, axis=2)
            mask = color_diff > bg_tolerance
            
            # Cập nhật lại kênh alpha cho ảnh
            new_alpha = np.where(mask, 255, 0).astype(np.uint8)
            arr[:, :, 3] = new_alpha
            processed_img = Image.fromarray(arr, 'RGBA')
            return mask, processed_img
            
        return (alpha > 0), img_rgba

    @classmethod
    def analyze(cls, image_or_path: Any, auto_remove_solid_bg: bool = True) -> Optional[CharacterMetrics]:
        if isinstance(image_or_path, str):
            if not os.path.exists(image_or_path):
                return None
            image = Image.open(image_or_path)
        else:
            image = image_or_path

        mask, _ = cls.extract_mask(image, auto_remove_solid_bg=auto_remove_solid_bg)
        
        if not np.any(mask):
            return None

        canvas_w, canvas_h = image.size
        y_indices, x_indices = np.where(mask)
        y_min, y_max = int(y_indices.min()), int(y_indices.max())
        x_min, x_max = int(x_indices.min()), int(x_indices.max())
        
        vis_h = y_max - y_min + 1
        vis_w = x_max - x_min + 1

        # Tạo biểu đồ chiều rộng theo từng hàng y (Horizontal Projection Profile)
        widths = []
        left_xs = []
        right_xs = []
        counts = []
        
        for y in range(y_min, y_max + 1):
            xs = np.where(mask[y, :])[0]
            if len(xs) > 0:
                widths.append(int(xs.max() - xs.min() + 1))
                left_xs.append(int(xs.min()))
                right_xs.append(int(xs.max()))
                counts.append(int(len(xs)))
            else:
                widths.append(0)
                left_xs.append(x_min)
                right_xs.append(x_min)
                counts.append(0)

        widths_arr = np.array(widths, dtype=float)
        # Lọc nhiễu nhẹ bằng kernel làm mượt 3 hàng
        kernel = np.array([0.2, 0.6, 0.2])
        smoothed_widths = np.convolve(widths_arr, kernel, mode='same')

        # Vùng tìm kiếm cổ (Neck Search Window): từ 16% đến 55% chiều cao nhân vật
        neck_search_start = max(1, int(vis_h * 0.16))
        neck_search_end = min(vis_h - 2, int(vis_h * 0.55))

        if neck_search_end > neck_search_start:
            window = smoothed_widths[neck_search_start:neck_search_end]
            # Cổ thường là điểm thắt đáy cục bộ (chiều ngang hẹp nhất trước khi vai mở rộng)
            neck_relative_idx = neck_search_start + int(np.argmin(window))
        else:
            neck_relative_idx = max(1, int(vis_h * 0.30))

        neck_y = y_min + neck_relative_idx

        # 1. Phần Đầu (Head)
        head_h = neck_relative_idx
        head_w = int(max(widths[:neck_relative_idx])) if neck_relative_idx > 0 else 0
        head_x_min = int(min(left_xs[:neck_relative_idx])) if neck_relative_idx > 0 else x_min
        head_x_max = int(max(right_xs[:neck_relative_idx])) if neck_relative_idx > 0 else x_max

        # 2. Phần Thân toàn bộ (Body = Cổ -> Đáy chân)
        body_h = vis_h - head_h
        body_w = int(max(widths[neck_relative_idx:])) if neck_relative_idx < vis_h else 0
        body_x_min = int(min(left_xs[neck_relative_idx:])) if neck_relative_idx < vis_h else x_min
        body_x_max = int(max(right_xs[neck_relative_idx:])) if neck_relative_idx < vis_h else x_max

        # 3. Phân tách Ngực/Bụng (Torso) và Chân (Legs) nếu có điểm phân chân
        crotch_start = int(vis_h * 0.48)
        crotch_end = int(vis_h * 0.78)
        torso_h = body_h
        torso_w = body_w
        if crotch_end > crotch_start:
            sub_counts = np.array(counts[crotch_start:crotch_end], dtype=float)
            crotch_rel = crotch_start + int(np.argmin(sub_counts))
            if crotch_rel > neck_relative_idx:
                torso_h = crotch_rel - neck_relative_idx
                torso_w = int(max(widths[neck_relative_idx:crotch_rel]))

        # Tính các tỉ lệ
        head_ratio = head_h / max(vis_h, 1)
        heads_tall = vis_h / max(head_h, 1)
        head_to_body_w = head_w / max(body_w, 1)
        body_aspect = body_w / max(body_h, 1)

        # Đánh giá phong cách
        if heads_tall <= 2.6:
            style_cat = "Chibi Lùn (2.0 - 2.5 đầu)"
        elif heads_tall <= 4.0:
            style_cat = "Semi-Chibi / Retro RPG (3.0 - 4.0 đầu)"
        else:
            style_cat = "Dáng Thật / Heroic (5.0+ đầu)"

        summary = (
            f"Phong cách: {style_cat}\n"
            f"Kích thước hiển thị: {vis_w}x{vis_h} px (Canvas: {canvas_w}x{canvas_h} px)\n"
            f"Độ to đầu: {head_w}x{head_h} px ({head_ratio*100:.1f}% chiều cao, tỉ lệ 1:{heads_tall:.1f} đầu)\n"
            f"Độ to thân: Rộng {body_w} px, Cao {body_h} px (Tỉ lệ ngang Đầu/Thân: {head_to_body_w:.2f})"
        )

        return CharacterMetrics(
            canvas_width=canvas_w,
            canvas_height=canvas_h,
            visible_x_min=x_min,
            visible_y_min=y_min,
            visible_x_max=x_max,
            visible_y_max=y_max,
            visible_width=vis_w,
            visible_height=vis_h,
            neck_y=neck_y,
            head_x_min=head_x_min,
            head_y_min=y_min,
            head_x_max=head_x_max,
            head_y_max=neck_y,
            head_width=head_w,
            head_height=head_h,
            body_x_min=body_x_min,
            body_y_min=neck_y + 1,
            body_x_max=body_x_max,
            body_y_max=y_max,
            body_width=body_w,
            body_height=body_h,
            torso_height=torso_h,
            torso_width=torso_w,
            head_ratio=round(head_ratio, 3),
            heads_tall=round(heads_tall, 2),
            head_to_body_width_ratio=round(head_to_body_w, 2),
            body_aspect_ratio=round(body_aspect, 2),
            style_category=style_cat,
            summary_text=summary
        )

    @classmethod
    def draw_annotated_image(cls, image: Image.Image, metrics: CharacterMetrics, scale: int = 1) -> Image.Image:
        """
        Vẽ overlay trực quan màu sắc đánh dấu vùng Đầu (Xanh lục/Cyan), Thân (Cam/Đỏ) và đường ranh giới Cổ.
        """
        _, clean_img = cls.extract_mask(image)
        base = clean_img.convert('RGBA')
        
        if scale > 1:
            base = base.resize((base.width * scale, base.height * scale), Image.Resampling.NEAREST)

        overlay = Image.new('RGBA', base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Scale tọa độ
        s = scale
        hx0, hy0 = metrics.head_x_min * s, metrics.head_y_min * s
        hx1, hy1 = (metrics.head_x_max + 1) * s, (metrics.head_y_max + 1) * s
        
        bx0, by0 = metrics.body_x_min * s, metrics.body_y_min * s
        bx1, by1 = (metrics.body_x_max + 1) * s, (metrics.body_y_max + 1) * s
        
        neck_y = (metrics.neck_y + 1) * s

        # Vẽ hộp Đầu (Xanh Cyan)
        draw.rectangle([hx0, hy0, hx1, hy1], outline=(0, 230, 255, 230), width=max(1, 2 * s // 4))
        draw.rectangle([hx0, hy0, hx1, hy1], fill=(0, 200, 255, 45))

        # Vẽ hộp Thân (Cam ấm)
        draw.rectangle([bx0, by0, bx1, by1], outline=(255, 140, 0, 230), width=max(1, 2 * s // 4))
        draw.rectangle([bx0, by0, bx1, by1], fill=(255, 120, 0, 45))

        # Vẽ đường ranh giới Cổ (Vàng rực)
        draw.line([(0, neck_y), (base.width, neck_y)], fill=(255, 255, 0, 240), width=max(1, 2 * s // 4))

        # Ghép overlay vào ảnh gốc
        result = Image.alpha_composite(base, overlay)
        return result
