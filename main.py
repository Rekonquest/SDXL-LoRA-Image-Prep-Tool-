import sys
import os
from PIL import Image
import cv2
import numpy as np

def scan_image_quality(image_path):
    try:
        # 1. Aspect Ratio and Resolution Check
        with Image.open(image_path) as img:
            width, height = img.size
            aspect_ratio = width / height
            if aspect_ratio > 2.0 or aspect_ratio < 0.5:
                return "Fail", f"Extreme aspect ratio ({aspect_ratio:.2f})"
            if width < 1024 or height < 1024:
                return "Fail", f"Resolution too low ({width}x{height})"

        # 2. Blur Check
        image = cv2.imread(image_path)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        if laplacian_var < 50:  # Lowered threshold
            return "Fail", f"Image is likely blurry (Laplacian variance: {laplacian_var:.2f})"

        return "Pass", "All checks passed"

    except Exception as e:
        return "Error", f"Could not process: {e}"

# This block will only be executed when the script is run directly
if __name__ == "__main__":
    # If a folder is provided as a command-line argument, run the scan directly
    if len(sys.argv) > 1:
        folder_path = sys.argv[1]
        print(f"Scanning folder from command line: {folder_path}")
        image_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
        for image_path in image_files:
            status, reason = scan_image_quality(image_path)
            print(f"[{status.upper()}] {os.path.basename(image_path)}: {reason}")
        sys.exit()

    # If no command-line arguments, start the GUI application
    from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                                 QPushButton, QLabel, QFileDialog, QScrollArea, QGridLayout)
    from PySide6.QtGui import QPixmap
    from PySide6.QtCore import Qt


    class MainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Jewels - SDXL LoRA Image Prep Tool")
            self.setGeometry(100, 100, 1200, 800)
            self.image_data = {}  # Data model to store image info

            # Main widget and layout
            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            main_layout = QVBoxLayout(central_widget)

            # --- Top Controls ---
            controls_widget = QWidget()
            controls_layout = QVBoxLayout(controls_widget)
            main_layout.addWidget(controls_widget)

            # 1. Select Folder Button
            self.select_folder_button = QPushButton("Select Image Folder")
            self.select_folder_button.clicked.connect(self.select_folder)
            controls_layout.addWidget(self.select_folder_button)

            # --- Filter Buttons ---
            filter_widget = QWidget()
            filter_layout = QHBoxLayout(filter_widget)
            controls_layout.addWidget(filter_widget)

            self.all_button = QPushButton("All")
            self.all_button.clicked.connect(lambda: self.populate_gallery("All"))
            self.pass_button = QPushButton("Pass")
            self.pass_button.clicked.connect(lambda: self.populate_gallery("Pass"))
            self.fail_button = QPushButton("Fail")
            self.fail_button.clicked.connect(lambda: self.populate_gallery("Fail"))
            filter_layout.addWidget(self.all_button)
            filter_layout.addWidget(self.pass_button)
            filter_layout.addWidget(self.fail_button)

            # --- Thumbnail Gallery ---
            self.scroll_area = QScrollArea()
            self.scroll_area.setWidgetResizable(True)
            main_layout.addWidget(self.scroll_area)

            self.gallery_widget = QWidget()
            self.gallery_layout = QGridLayout(self.gallery_widget)
            self.scroll_area.setWidget(self.gallery_widget)

            # --- Review & Edit Panel (Placeholder) ---
            review_label = QLabel("Review & Edit Panel Area")
            main_layout.addWidget(review_label)

        def select_folder(self):
            folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
            if folder_path:
                image_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
                for image_path in image_files:
                    status, reason = scan_image_quality(image_path)
                    self.image_data[image_path] = {"status": status, "reason": reason}
                self.populate_gallery()

        def populate_gallery(self, filter="All"):
            # Clear existing widgets
            for i in reversed(range(self.gallery_layout.count())):
                widget = self.gallery_layout.itemAt(i).widget()
                if widget is not None:
                    widget.deleteLater()

            row, col = 0, 0
            for image_path, data in self.image_data.items():
                if filter == "All" or data["status"] == filter:
                    thumbnail = QLabel()
                    pixmap = QPixmap(image_path)
                    thumbnail.setPixmap(pixmap.scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation))

                    if data["status"] == "Pass":
                        thumbnail.setStyleSheet("border: 2px solid green;")
                    elif data["status"] == "Fail":
                        thumbnail.setStyleSheet("border: 2px solid red;")

                    self.gallery_layout.addWidget(thumbnail, row, col)
                    col += 1
                    if col % 8 == 0:
                        row += 1
                        col = 0

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
