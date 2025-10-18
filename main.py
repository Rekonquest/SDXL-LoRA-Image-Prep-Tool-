import sys
import os
from PIL import Image
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QFileDialog, QScrollArea, QGridLayout,
                             QStatusBar, QProgressBar, QLineEdit)
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt, QThread, QRectF

from image_processing import scan_image_quality, auto_rotate_image, auto_crop_image
from ui_components import ClickableLabel, SettingsDialog, CropWidget
from worker import ScanWorker, LabelWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jewels - SDXL LoRA Image Prep Tool")
        self.setGeometry(100, 100, 1200, 800)
        self.image_data = {}
        self.current_filter = "All"
        self.setStatusBar(QStatusBar(self))
        self.showing_before = True

        self.settings = {
            "min_resolution": 1024, "min_aspect_ratio": 0.5,
            "max_aspect_ratio": 2.0, "blur_threshold": 50
        }

        # --- UI Setup ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        top_controls_layout = QHBoxLayout()
        main_layout.addLayout(top_controls_layout)

        self.select_folder_button = QPushButton("Select Image Folder")
        self.select_folder_button.clicked.connect(self.select_folder)
        top_controls_layout.addWidget(self.select_folder_button)

        self.settings_button = QPushButton("Settings")
        self.settings_button.clicked.connect(self.open_settings)
        top_controls_layout.addWidget(self.settings_button)

        self.export_button = QPushButton("Export Passed Images")
        self.export_button.clicked.connect(self.export_images)
        top_controls_layout.addWidget(self.export_button)

        # --- Progress Bar ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        filter_layout = QHBoxLayout()
        main_layout.addLayout(filter_layout)

        self.all_button = QPushButton("All")
        self.all_button.clicked.connect(lambda: self.populate_gallery("All"))
        self.pass_button = QPushButton("Pass")
        self.pass_button.clicked.connect(lambda: self.populate_gallery("Pass"))
        self.fail_button = QPushButton("Fail")
        self.fail_button.clicked.connect(lambda: self.populate_gallery("Fail"))
        filter_layout.addWidget(self.all_button)
        filter_layout.addWidget(self.pass_button)
        filter_layout.addWidget(self.fail_button)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        main_layout.addWidget(self.scroll_area)

        self.gallery_widget = QWidget()
        self.gallery_layout = QGridLayout(self.gallery_widget)
        self.scroll_area.setWidget(self.gallery_widget)

        self.review_panel = QWidget()
        self.review_layout = QVBoxLayout(self.review_panel)
        main_layout.addWidget(self.review_panel)

        self.crop_widget = CropWidget()
        self.review_layout.addWidget(self.crop_widget)

        # --- Labeling UI ---
        label_layout = QHBoxLayout()
        self.review_layout.addLayout(label_layout)
        self.label_input = QLineEdit()
        self.label_input.setPlaceholderText("Generated label will appear here...")
        self.label_input.textChanged.connect(self.update_label)
        label_layout.addWidget(self.label_input)
        self.auto_label_button = QPushButton("Auto-Label")
        self.auto_label_button.clicked.connect(self.auto_label)
        label_layout.addWidget(self.auto_label_button)

        button_layout = QHBoxLayout()
        self.review_layout.addLayout(button_layout)

        self.before_after_button = QPushButton("Show After")
        self.before_after_button.clicked.connect(self.toggle_view)
        button_layout.addWidget(self.before_after_button)

        self.auto_rotate_button = QPushButton("Auto-Rotate")
        self.auto_rotate_button.clicked.connect(self.auto_rotate)
        button_layout.addWidget(self.auto_rotate_button)

        self.auto_crop_button = QPushButton("Intelligent Crop")
        self.auto_crop_button.clicked.connect(self.auto_crop)
        button_layout.addWidget(self.auto_crop_button)

        self.apply_crop_button = QPushButton("Apply Manual Crop")
        self.apply_crop_button.clicked.connect(self.apply_manual_crop)
        button_layout.addWidget(self.apply_crop_button)

        self.override_button = QPushButton("Toggle Pass/Fail")
        self.override_button.clicked.connect(self.toggle_status)
        button_layout.addWidget(self.override_button)

        self.review_panel.setVisible(False)
        self.current_selected_image = None

    def open_settings(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self.settings = dialog.get_settings()
            self.statusBar().showMessage("Settings updated.", 3000)
            if self.image_data:
                self.rescan_images()

    def select_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            self.image_data = {}
            self.progress_bar.setVisible(True)
            self.select_folder_button.setEnabled(False)

            self.thread = QThread()
            self.worker = ScanWorker(folder_path, self.settings)
            self.worker.moveToThread(self.thread)

            self.thread.started.connect(self.worker.run)
            self.worker.finished.connect(self.thread.quit)
            self.worker.finished.connect(self.worker.deleteLater)
            self.thread.finished.connect(self.thread.deleteLater)
            self.thread.finished.connect(self.scan_finished)

            self.worker.progress.connect(self.update_progress)
            self.worker.image_scanned.connect(self.add_scanned_image)

            self.thread.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def add_scanned_image(self, data):
        image_path, status, reason = data
        self.image_data[image_path] = {"status": status, "reason": reason, "polished_image": None, "label": ""}

    def scan_finished(self):
        self.progress_bar.setVisible(False)
        self.select_folder_button.setEnabled(True)
        self.populate_gallery()
        self.statusBar().showMessage("Scan complete.", 3000)

    def rescan_images(self):
        for image_path in self.image_data:
            status, reason = scan_image_quality(image_path, self.settings)
            self.image_data[image_path]["status"] = status
            self.image_data[image_path]["reason"] = reason
        self.populate_gallery(self.current_filter)
        self.statusBar().showMessage("Images rescanned with new settings.", 3000)

    def populate_gallery(self, filter="All"):
        self.current_filter = filter
        for i in reversed(range(self.gallery_layout.count())):
            self.gallery_layout.itemAt(i).widget().setParent(None)

        row, col = 0, 0
        for image_path, data in self.image_data.items():
            if filter == "All" or data["status"] == filter:
                thumbnail = ClickableLabel(image_path)
                thumbnail.clicked.connect(self.show_in_review)
                pixmap = QPixmap(image_path)
                thumbnail.setPixmap(pixmap.scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation))

                thumbnail.setStyleSheet(f"border: 2px solid {'green' if data['status'] == 'Pass' else 'red'};")
                self.gallery_layout.addWidget(thumbnail, row, col)
                col += 1
                if col % 8 == 0: row, col = row + 1, 0

    def show_in_review(self, image_path):
        self.current_selected_image = image_path
        self.showing_before = True
        self.before_after_button.setText("Show After")
        self.before_after_button.setEnabled(self.image_data[image_path]["polished_image"] is not None)

        pixmap = QPixmap(image_path)
        self.crop_widget.set_image(pixmap)
        self.crop_widget.set_crop_rect(QRectF())

        self.label_input.setText(self.image_data[image_path]["label"])

        self.review_panel.setVisible(True)

    def update_label(self, text):
        if self.current_selected_image:
            self.image_data[self.current_selected_image]["label"] = text

    def auto_label(self):
        if self.current_selected_image:
            self.statusBar().showMessage("Generating label...", 3000)
            self.auto_label_button.setEnabled(False)

            self.label_thread = QThread()
            self.label_worker = LabelWorker(self.current_selected_image)
            self.label_worker.moveToThread(self.label_thread)

            self.label_thread.started.connect(self.label_worker.run)
            self.label_worker.label_generated.connect(self.update_label_field)
            self.label_worker.label_generated.connect(self.label_thread.quit)
            self.label_worker.label_generated.connect(self.label_worker.deleteLater)
            self.label_thread.finished.connect(self.label_thread.deleteLater)

            self.label_thread.start()

    def update_label_field(self, label):
        self.label_input.setText(label)
        self.statusBar().showMessage("Label generated successfully.", 3000)
        self.auto_label_button.setEnabled(True)

    def toggle_status(self):
        if self.current_selected_image:
            current_status = self.image_data[self.current_selected_image]["status"]
            self.image_data[self.current_selected_image]["status"] = "Fail" if current_status == "Pass" else "Pass"
            self.populate_gallery(self.current_filter)

    def auto_rotate(self):
        if self.current_selected_image:
            rotated_image = auto_rotate_image(self.current_selected_image)
            if rotated_image:
                self.image_data[self.current_selected_image]["polished_image"] = rotated_image
                self.update_review_pixmap(rotated_image)
                self.statusBar().showMessage("Image rotated successfully.", 3000)
                self.before_after_button.setEnabled(True)
            else:
                self.statusBar().showMessage("No EXIF data for rotation.", 3000)

    def auto_crop(self):
        if self.current_selected_image:
            crop_rect_tuple = auto_crop_image(self.current_selected_image)
            if crop_rect_tuple:
                x, y, w, h = crop_rect_tuple
                self.crop_widget.set_crop_rect(QRectF(x, y, w, h))
                self.statusBar().showMessage("Automated crop applied.", 3000)
            else:
                self.statusBar().showMessage("No subject detected for auto-crop.", 3000)

    def apply_manual_crop(self):
        if self.current_selected_image:
            crop_rect = self.crop_widget.get_crop_rect().toRect()
            original_image = Image.open(self.current_selected_image)
            cropped_image = original_image.crop((crop_rect.x(), crop_rect.y(),
                                                 crop_rect.x() + crop_rect.width(),
                                                 crop_rect.y() + crop_rect.height()))

            self.image_data[self.current_selected_image]["polished_image"] = cropped_image
            self.update_review_pixmap(cropped_image)
            self.statusBar().showMessage("Manual crop applied.", 3000)
            self.before_after_button.setEnabled(True)


    def toggle_view(self):
        if self.current_selected_image:
            if not self.showing_before:
                self.crop_widget.set_image(QPixmap(self.current_selected_image))
                self.before_after_button.setText("Show After")
            elif self.image_data[self.current_selected_image]["polished_image"]:
                self.update_review_pixmap(self.image_data[self.current_selected_image]["polished_image"])
                self.before_after_button.setText("Show Before")
            self.showing_before = not self.showing_before

    def update_review_pixmap(self, pil_image):
        w, h = pil_image.size
        pil_image = pil_image.convert("RGB") if pil_image.mode != "RGB" else pil_image
        qimage = QImage(pil_image.tobytes("raw", "RGB"), w, h, QImage.Format_RGB888)
        self.crop_widget.set_image(QPixmap.fromImage(qimage))

    def export_images(self):
        if self.image_data:
            output_folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
            if output_folder:
                exported_count = 0
                for image_path, data in self.image_data.items():
                    if data["status"] == "Pass":
                        image_to_save = data["polished_image"] or Image.open(image_path)

                        base_name = os.path.splitext(os.path.basename(image_path))[0]

                        # Save the image
                        image_output_path = os.path.join(output_folder, base_name + ".png")
                        image_to_save.save(image_output_path, "PNG")

                        # Save the label if it exists
                        if data["label"]:
                            label_output_path = os.path.join(output_folder, base_name + ".txt")
                            with open(label_output_path, "w") as f:
                                f.write(data["label"])

                        exported_count += 1
                self.statusBar().showMessage(f"Successfully exported {exported_count} images and labels.", 5000)
        else:
            self.statusBar().showMessage("No images to export.", 3000)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        default_settings = {"min_resolution": 1024, "min_aspect_ratio": 0.5, "max_aspect_ratio": 2.0, "blur_threshold": 50}
        folder_path = sys.argv[1]
        print(f"Scanning folder from command line: {folder_path}")
        for f in os.listdir(folder_path):
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                status, reason = scan_image_quality(os.path.join(folder_path, f), default_settings)
                print(f"[{status.upper()}] {f}: {reason}")
        sys.exit()

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
