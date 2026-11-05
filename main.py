"""
Ứng dụng Sprite AI Normalizer & Resizer (Mô hình MVC)
- Model:
    + character_analyzer.py: Phân tích kích thước Đầu, Thân, Tỉ lệ bằng Computer Vision
    + prompt_advisor.py: Kết nối LLM API (Gemini) & Heuristic sinh Prompt chuẩn
    + sprite_resizer.py: Mô phỏng LibreSprite Sprite Size & Auto Standardizer
- View:
    + main_view.py: Giao diện chính 3 bước trực quan
    + sprite_size_dialog.py: Hộp thoại Sprite Size chuẩn LibreSprite
- Controller:
    + app_controller.py: Điều phối sự kiện và dữ liệu
"""
import sys
import os

# Thêm đường dẫn thư mục hiện tại vào sys.path để import dễ dàng
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from views.main_view import MainView
from controllers.app_controller import AppController


def main():
    print("Khởi động Sprite AI Normalizer (MVC)...")
    view = MainView()
    controller = AppController(view, config_path=os.path.join(CURRENT_DIR, "config.json"))
    view.mainloop()


if __name__ == "__main__":
    main()
