from typing import Tuple, Optional
import numpy as np
from PIL import Image
from .character_analyzer import CharacterAnalyzer, CharacterMetrics


class SpriteResizer:
    """
    Model phụ trách:
    1. Mô phỏng 100% chức năng 'Sprite Size' của LibreSprite:
       - Thay đổi kích thước theo Pixel / Phần trăm.
       - Hỗ trợ Khóa tỉ lệ (Lock Ratio).
       - Thuật toán nội suy chuyên dụng Pixel Art: Nearest-neighbor (hoặc Bilinear, Bicubic).
    2. Chuẩn hoá tự động thông minh (Smart Normalization):
       - Tách nền ảnh AI mới sinh (trắng/đen/xanh).
       - Cắt sát vùng nhìn thấy (Crop visible bounding box).
       - Downsample bằng Nearest-neighbor sao cho khớp chuẩn tỉ lệ/kích thước nhân vật cũ.
       - Đặt vào khung Canvas chuẩn (ví dụ 115x128 hoặc 128x128), căn đáy chân và căn giữa trục ngang.
    """

    INTERPOLATION_MAP = {
        "Nearest-neighbor": Image.Resampling.NEAREST,
        "Bilinear": Image.Resampling.BILINEAR,
        "Bicubic": Image.Resampling.BICUBIC
    }

    @classmethod
    def resize_sprite(
        cls,
        image: Image.Image,
        target_width: int,
        target_height: int,
        method: str = "Nearest-neighbor"
    ) -> Image.Image:
        """Co giãn sprite trực tiếp theo chuẩn Sprite Size của LibreSprite."""
        resample_mode = cls.INTERPOLATION_MAP.get(method, Image.Resampling.NEAREST)
        target_w = max(1, int(target_width))
        target_h = max(1, int(target_height))
        return image.resize((target_w, target_h), resample=resample_mode)

    @classmethod
    def auto_standardize_to_reference(
        cls,
        new_image: Image.Image,
        ref_metrics: CharacterMetrics,
        body_height_rule: str = "Bằng nhân vật cũ",
        body_width_rule: str = "Bằng nhân vật cũ",
        method: str = "Nearest-neighbor",
        auto_remove_bg: bool = True
    ) -> Image.Image:
        """
        Chuẩn hóa toàn diện ảnh mới tạo theo nhân vật tham chiếu cũ:
        1. Lọc nền
        2. Đo bounding box nhân vật mới
        3. Tính toán hệ số scale phù hợp (kết hợp với yêu cầu Cao hơn / To hơn)
        4. Resize bằng Nearest-Neighbor
        5. Đặt vào khung Canvas chuẩn của nhân vật cũ, căn chân chạm đất
        """
        resample_mode = cls.INTERPOLATION_MAP.get(method, Image.Resampling.NEAREST)
        
        # 1. Tách nền và lấy mask
        mask, clean_img = CharacterAnalyzer.extract_mask(new_image, auto_remove_solid_bg=auto_remove_bg)
        if not np.any(mask):
            # Nếu không tìm thấy, resize trực tiếp theo kích thước canvas cũ
            return cls.resize_sprite(new_image, ref_metrics.canvas_width, ref_metrics.canvas_height, method=method)

        # 2. Cắt sát bounding box của nhân vật mới
        y_indices, x_indices = np.where(mask)
        y_min, y_max = int(y_indices.min()), int(y_indices.max())
        x_min, x_max = int(x_indices.min()), int(x_indices.max())
        cropped_char = clean_img.crop((x_min, y_min, x_max + 1, y_max + 1))

        # 3. Tính toán kích thước mục tiêu
        # Chiều cao mục tiêu của phần nhìn thấy
        target_vis_h = float(ref_metrics.visible_height)
        if "Cao hơn" in body_height_rule:
            target_vis_h *= 1.15
        elif "Thấp hơn" in body_height_rule:
            target_vis_h *= 0.88

        # Hệ số scale dọc
        scale_y = target_vis_h / max(cropped_char.height, 1)

        # Chiều rộng mục tiêu
        if "To hơn" in body_width_rule:
            scale_x = scale_y * 1.25  # Làm thân nở rộng hơn 25%
        elif "Nhỏ hơn" in body_width_rule:
            scale_x = scale_y * 0.85  # Thon gọn hơn 15%
        else:
            scale_x = scale_y  # Giữ nguyên tỉ lệ ảnh gốc

        final_w = max(1, int(round(cropped_char.width * scale_x)))
        final_h = max(1, int(round(cropped_char.height * scale_y)))

        # 4. Downsample với Nearest-neighbor
        resized_char = cropped_char.resize((final_w, final_h), resample=resample_mode)

        # 5. Đặt vào khung Canvas chuẩn của nhân vật cũ
        canvas_w = max(ref_metrics.canvas_width, final_w)
        canvas_h = max(ref_metrics.canvas_height, final_h)

        result_canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

        # Căn chỉnh vị trí: Căn giữa theo trục ngang (X)
        paste_x = (canvas_w - final_w) // 2

        # Căn vị trí chân (Y) sao cho chân của nhân vật mới chạm cùng độ cao mặt đất với nhân vật cũ
        margin_bottom = ref_metrics.canvas_height - (ref_metrics.visible_y_max + 1)
        paste_y = canvas_h - final_h - max(0, margin_bottom)
        
        # Giới hạn nếu tràn viền trên
        if paste_y < 0:
            paste_y = 0

        result_canvas.paste(resized_char, (paste_x, paste_y), mask=resized_char)
        return result_canvas
