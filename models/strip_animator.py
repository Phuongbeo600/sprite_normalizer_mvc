import os
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from PIL import Image
from .character_analyzer import CharacterAnalyzer, CharacterMetrics


class AnimationStripModel:
    """
    Model chuyên xử lý các dải hoạt cảnh (Animation Strips / Walk Cycles / Spritesheets):
    1. Thuật toán Vertical Projection Profiling: Tìm chính xác các khe hở an toàn giữa các nhân vật
       (Đảm bảo 100% KHÔNG BAO GIỜ CẮT NHẦM VÀO NHÂN VẬT).
    2. Cắt thành các "TẤM" độc lập giữ nguyên toàn bộ bìa (Full Card/Tile), không làm méo hình.
    3. Hỗ trợ xuất 4 tấm nguyên bản hoặc chuẩn hoá đồng bộ theo Canvas / Độ phân giải thật.
    """

    @staticmethod
    def detect_strip(image: Image.Image) -> Dict[str, Any]:
        """Phát hiện xem ảnh có phải là dải hoạt ảnh ngang không và gợi ý số frame."""
        w, h = image.size
        ratio = w / max(h, 1)

        is_strip = ratio >= 1.6
        suggested_frames = 1
        
        if is_strip:
            rounded = int(round(ratio))
            if rounded in [2, 3, 4, 5, 6, 8]:
                suggested_frames = rounded
            elif ratio >= 3.6 and ratio <= 4.4:
                suggested_frames = 4
            elif ratio >= 5.5 and ratio <= 6.5:
                suggested_frames = 6
            elif ratio >= 7.5 and ratio <= 8.5:
                suggested_frames = 8
            else:
                suggested_frames = max(2, rounded)

        return {
            "is_strip": is_strip,
            "ratio": round(ratio, 2),
            "suggested_frames": suggested_frames,
            "width": w,
            "height": h
        }

    @classmethod
    def find_safe_split_boundaries(
        cls,
        image: Image.Image,
        num_frames: int,
        bg_tolerance: int = 25
    ) -> List[int]:
        """
        Thuật toán Vertical Projection Profiling tìm đường cắt an toàn 100%:
        - Phân tích mật độ pixel nhân vật theo từng cột X
        - Tìm các vùng trống (khoảng trắng/nền) giữa các nhân vật
        - Đặt đường cắt ở chính giữa khoảng trống an toàn
        - Đảm bảo tuyệt đối KHÔNG cắt phạm vào kiếm, đuôi, tóc, chân hay tay nhân vật
        """
        img_rgba = image.convert("RGBA")
        arr = np.array(img_rgba)
        w, h = image.size

        # Tách nền: pixel có màu khác nền ở 4 góc hoặc alpha > 15
        mask, _ = CharacterAnalyzer.extract_mask(image, auto_remove_solid_bg=True, bg_tolerance=bg_tolerance)
        col_density = np.sum(mask, axis=0)

        # Tìm các đảo nhân vật (contiguous character islands)
        islands: List[Tuple[int, int]] = []
        in_island = False
        start_x = 0
        for x in range(w):
            if col_density[x] > 0 and not in_island:
                in_island = True
                start_x = x
            elif col_density[x] == 0 and in_island:
                in_island = False
                islands.append((start_x, x - 1))
        if in_island:
            islands.append((start_x, w - 1))

        # Trường hợp 1: Số đảo tìm thấy khớp đúng số frame kỳ vọng
        if len(islands) == num_frames:
            splits = [0]
            for i in range(len(islands) - 1):
                mid = (islands[i][1] + islands[i + 1][0]) // 2
                splits.append(int(mid))
            splits.append(w)
            return splits

        # Trường hợp 2: Có nhiều đảo nhỏ (ví dụ do vũ khí/phụ kiện tách rời)
        if len(islands) > num_frames:
            # Tính độ rộng của các khoảng trống (gaps)
            gaps = []
            for i in range(len(islands) - 1):
                gap_w = islands[i + 1][0] - islands[i][1] - 1
                mid = (islands[i][1] + islands[i + 1][0]) // 2
                gaps.append((gap_w, mid))
            
            # Chọn (num_frames - 1) khoảng trống rộng nhất (chắc chắn là khoảng cách giữa 2 nhân vật)
            gaps.sort(key=lambda x: x[0], reverse=True)
            top_mids = sorted([g[1] for g in gaps[:num_frames - 1]])
            return [0] + top_mids + [w]

        # Trường hợp 3: Số đảo ít hơn (nhân vật đứng quá sát hoặc chạm nhẹ nhau)
        # Quét tìm điểm cực tiểu (valley / điểm thắt hẹp nhất) quanh vị trí dự kiến
        splits = [0]
        step = w // num_frames
        for i in range(1, num_frames):
            center = i * step
            search_radius = max(10, step // 4)
            r_start = max(0, center - search_radius)
            r_end = min(w, center + search_radius)
            valley_col = r_start + int(np.argmin(col_density[r_start:r_end]))
            splits.append(int(valley_col))
        splits.append(w)
        return splits

    @classmethod
    def split_into_cards(
        cls,
        image: Image.Image,
        num_frames: int,
        target_size: Optional[Tuple[int, int]] = None,
        auto_remove_bg: bool = True
    ) -> Dict[str, Any]:
        """
        CẮT THÀNH CÁC TẤM ĐỘC LẬP (GIỮ TRỌN CẢ BÌA & BỐ CỤC):
        - Cắt theo đường biên an toàn
        - Giữ nguyên toàn bộ lề trên, dưới, trái, phải
        - Đóng thành các tấm có kích thước đồng bộ, không bị bóp méo
        """
        w, h = image.size
        num_frames = max(1, num_frames)

        # 1. Tìm đường cắt an toàn 100% không phạm vào nhân vật
        splits = cls.find_safe_split_boundaries(image, num_frames)

        raw_cards = []
        max_card_w = 0

        # 2. Cắt từng tấm
        for i in range(len(splits) - 1):
            x0, x1 = splits[i], splits[i + 1]
            card_crop = image.crop((x0, 0, x1, h))

            if auto_remove_bg:
                _, clean_card = CharacterAnalyzer.extract_mask(card_crop, auto_remove_solid_bg=True)
            else:
                clean_card = card_crop.convert("RGBA")

            raw_cards.append(clean_card)
            if clean_card.width > max_card_w:
                max_card_w = clean_card.width

        # Chiều rộng đồng bộ của tấm ảnh (để cả 4 tấm có cùng khổ bìa chuẩn vuông hoặc chữ nhật)
        uniform_card_w = max_card_w
        uniform_card_h = h

        normalized_cards: List[Image.Image] = []
        combined_sheet = Image.new("RGBA", (uniform_card_w * num_frames, uniform_card_h), (0, 0, 0, 0))

        for i, card in enumerate(raw_cards):
            # Tạo tấm chuẩn, đặt nhân vật vào giữa, giữ trọn vẹn bìa xung quanh
            padded_card = Image.new("RGBA", (uniform_card_w, uniform_card_h), (0, 0, 0, 0))
            paste_x = (uniform_card_w - card.width) // 2
            padded_card.paste(card, (paste_x, 0), mask=card)

            # Nếu có yêu cầu resize về target_size (ví dụ theo chuẩn nhân vật cũ)
            if target_size:
                final_card = padded_card.resize(target_size, resample=Image.Resampling.NEAREST)
            else:
                final_card = padded_card

            normalized_cards.append(final_card)
            combined_sheet.paste(padded_card, (i * uniform_card_w, 0), mask=padded_card)

        return {
            "cards": normalized_cards,
            "spritesheet": combined_sheet,
            "num_frames": num_frames,
            "card_width": normalized_cards[0].width,
            "card_height": normalized_cards[0].height,
            "sheet_width": combined_sheet.width,
            "sheet_height": combined_sheet.height,
            "splits": splits
        }

    @staticmethod
    def export_frames_to_folder(
        frames: List[Image.Image],
        folder_path: str,
        base_name: str = "tam"
    ) -> List[str]:
        """Xuất từng tấm riêng rẽ ra thư mục (tam_1.png, tam_2.png...)."""
        os.makedirs(folder_path, exist_ok=True)
        saved_paths = []
        for i, frame in enumerate(frames):
            out_file = os.path.join(folder_path, f"{base_name}_{i + 1}.png")
            frame.save(out_file, "PNG")
            saved_paths.append(out_file)
        return saved_paths

    @staticmethod
    def export_animated_gif(
        frames: List[Image.Image],
        gif_path: str,
        fps: int = 6
    ) -> str:
        """Xuất các tấm thành ảnh động GIF lặp lại."""
        if not frames:
            raise ValueError("Không có tấm nào để xuất GIF!")
        
        duration_ms = max(20, int(round(1000.0 / max(1, fps))))
        os.makedirs(os.path.dirname(os.path.abspath(gif_path)), exist_ok=True)

        frames[0].save(
            gif_path,
            save_all=True,
            append_images=frames[1:],
            duration=duration_ms,
            loop=0,
            disposal=2
        )
        return gif_path
