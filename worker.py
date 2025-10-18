from PySide6.QtCore import QObject, Signal
import os
from image_processing import scan_image_quality
from transformers import pipeline
from PIL import Image

class ScanWorker(QObject):
    finished = Signal()
    progress = Signal(int)
    image_scanned = Signal(tuple)

    def __init__(self, folder_path, settings):
        super().__init__()
        self.folder_path = folder_path
        self.settings = settings
        self.image_files = []

    def run(self):
        self.image_files = [os.path.join(self.folder_path, f) for f in os.listdir(self.folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
        total_images = len(self.image_files)

        for i, image_path in enumerate(self.image_files):
            status, reason = scan_image_quality(image_path, self.settings)
            self.image_scanned.emit((image_path, status, reason))
            self.progress.emit(int(((i + 1) / total_images) * 100))

        self.finished.emit()

class LabelWorker(QObject):
    label_generated = Signal(str)

    def __init__(self, image_path):
        super().__init__()
        self.image_path = image_path
        # It's better to initialize the pipeline once and reuse it if possible,
        # but for simplicity in this worker, we'll initialize it here.
        # A more advanced implementation might use a shared pipeline instance.
        self.captioner = pipeline("image-to-text", model="Salesforce/blip-image-captioning-large")

    def run(self):
        if self.image_path:
            image = Image.open(self.image_path).convert("RGB")
            result = self.captioner(image)
            if result and result[0] and 'generated_text' in result[0]:
                self.label_generated.emit(result[0]['generated_text'])
