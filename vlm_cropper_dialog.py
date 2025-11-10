from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QVBoxLayout, QWidget,
    QLabel, QTextEdit, QListWidget, QPushButton, QFileDialog, QHBoxLayout,
    QLineEdit
)
from PySide6.QtCore import Qt
from pathlib import Path
from utils import AppSettings

class VLMCropperDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("VLM Cropper Tool")
        self.setMinimumWidth(600)

        self.image_paths = []

        lay = QVBoxLayout(self)

        # Image List
        lay.addWidget(QLabel("Images to Crop:"))
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.NoSelection)
        lay.addWidget(self.list_widget, 1)

        btn_lay = QHBoxLayout()
        add_btn = QPushButton("Add Images...")
        add_btn.clicked.connect(self.add_images)
        btn_lay.addWidget(add_btn)
        btn_lay.addStretch()
        lay.addLayout(btn_lay)

        # Output Folder
        lay.addWidget(QLabel("Output Folder:"))
        out_lay = QHBoxLayout()
        self.out_folder_edit = QLineEdit()
        self.out_folder_edit.setPlaceholderText("Select an output folder...")
        out_btn = QPushButton("Browse...")
        out_btn.clicked.connect(self.select_output)
        out_lay.addWidget(self.out_folder_edit, 1)
        out_lay.addWidget(out_btn)
        lay.addLayout(out_lay)

        # Prompt
        lay.addWidget(QLabel("VLM Prompt:"))
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setText(self.settings.data.get("vlm_cropper_prompt", ""))
        lay.addWidget(self.prompt_edit)

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def add_images(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Images to Crop", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if files:
            self.image_paths.extend(files)
            self.list_widget.addItems(files)

    def select_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.out_folder_edit.setText(folder)

    def get_settings(self) -> dict:
        """Returns the job settings if user clicked OK."""
        return {
            "image_paths": self.image_paths,
            "output_dir": Path(self.out_folder_edit.text()),
            "prompt": self.prompt_edit.toPlainText(),
            "lm_settings": self.settings.data.get("lmstudio", {})
        }
