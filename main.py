
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QSplitter, QComboBox, QMessageBox, QCheckBox, QSpinBox, QLineEdit
)

from ui_components import ThumbnailGallery, CropOverlay
from worker import ScanManager, ScanConfig, ExportManager
from PySide6.QtGui import QPixmap

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jewels — SDXL LoRA Image Prep Tool (Analyst + Auto-Fix + Selection)")
        self.resize(1400, 860)

        self.items = []
        self.filtered = []
        self.current = None

        open_btn = QPushButton("Select Image Folder")
        open_btn.clicked.connect(self.select_folder)

        self.filter_box = QComboBox()
        self.filter_box.addItems(["All", "PASS", "FAIL", "DUPLICATE"])
        self.filter_box.currentTextChanged.connect(self.apply_filter)

        self.autofix_chk = QCheckBox("Auto-fix failing images")
        self.pass_spin = QSpinBox(); self.pass_spin.setRange(50, 100); self.pass_spin.setValue(95)

        self.selmin_spin = QSpinBox(); self.selmin_spin.setRange(50, 100); self.selmin_spin.setValue(90)
        self.include_edit = QLineEdit(); self.include_edit.setPlaceholderText("include globs (comma-separated) e.g. */portraits/*, *2024*")
        self.exclude_edit = QLineEdit(); self.exclude_edit.setPlaceholderText("exclude globs e.g. */screenshots/*, *memes*")

        export_btn = QPushButton("Export (triage)")
        export_btn.clicked.connect(self.export_all)

        top = QHBoxLayout()
        top.addWidget(open_btn); top.addStretch(1)
        top.addWidget(QLabel("Filter:")); top.addWidget(self.filter_box)
        top.addStretch(1)
        top.addWidget(QLabel("Pass≥")); top.addWidget(self.pass_spin)
        top.addWidget(self.autofix_chk)
        top.addStretch(1)
        top.addWidget(QLabel("Select min score≥")); top.addWidget(self.selmin_spin)
        top.addWidget(self.include_edit, 2); top.addWidget(self.exclude_edit, 2)
        top.addStretch(1)
        top.addWidget(export_btn)

        self.gallery = ThumbnailGallery()
        self.gallery.itemSelectionChanged.connect(self.on_select)

        self.preview = CropOverlay()
        right = QVBoxLayout()
        self.preview_label = QLabel("Review Panel")
        right.addWidget(self.preview_label)
        right.addWidget(self.preview, 1)

        split = QSplitter()
        w1 = QWidget(); l1 = QVBoxLayout(w1); l1.addWidget(self.gallery)
        w2 = QWidget(); w2.setLayout(right)
        split.addWidget(w1); split.addWidget(w2); split.setSizes([720,720])

        self.progress = QProgressBar()
        self.statusBar().addPermanentWidget(self.progress, 1)

        central = QWidget(); lay = QVBoxLayout(central)
        lay.addLayout(top); lay.addWidget(split, 1)
        self.setCentralWidget(central)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select image folder")
        if not folder: return
        self.scan_folder(Path(folder))

    def scan_folder(self, folder: Path):
        self.items.clear(); self.filtered.clear(); self.gallery.clear()

        cfg = ScanConfig(
            pass_threshold=float(self.pass_spin.value()),
        )
        self.scan_manager = ScanManager(folder, cfg)
        self.scan_manager.image_scanned.connect(self.on_item)
        self.scan_manager.progress.connect(self.on_progress)
        self.scan_manager.finished.connect(self.on_finished)
        self.progress.setValue(0); self.progress.setFormat("Scanning %p%")
        self.scan_manager.run()

    def export_all(self):
        if not self.items:
            QMessageBox.information(self, "Export", "Nothing to export yet."); return
        out = QFileDialog.getExistingDirectory(self, "Select output folder")
        if not out: return

        to_export = [it for it in self.items if it.get("status") in ("PASS","FAIL","DUPLICATE")]
        if not to_export:
            QMessageBox.information(self, "Export", "No items to export."); return

        cfg = ScanConfig(
            pass_threshold=float(self.pass_spin.value()),
            sel_min_score=float(self.selmin_spin.value()),
            include_globs=self.include_edit.text().strip(),
            exclude_globs=self.exclude_edit.text().strip(),
        )
        self.export_manager = ExportManager(to_export, Path(out),
                                          apply_autofix=self.autofix_chk.isChecked(),
                                          cfg=cfg)
        self.export_manager.progress.connect(self.on_progress)
        self.export_manager.finished.connect(self.on_export_done)
        self.progress.setValue(0); self.progress.setFormat("Exporting %p%")
        self.export_manager.run()

    def on_progress(self, done, total):
        self.progress.setMaximum(total); self.progress.setValue(done)

    def on_item(self, item: dict):
        self.items.append(item)
        mode = self.filter_box.currentText()
        if mode == "All" or item.get("status") == mode:
            self.filtered.append(item)
            self.gallery.add_thumb(item)

    def on_finished(self, results):
        self.items = results
        self.apply_filter()
        self.statusBar().showMessage(f"Scan complete: {len(results)} items", 5000)

    def on_export_done(self, out_path):
        self.statusBar().showMessage(f"Exported to {out_path}", 5000)

    def apply_filter(self):
        mode = self.filter_box.currentText()
        self.filtered = self.items[:] if mode == "All" else [it for it in self.items if it.get("status")==mode]
        self.gallery.populate(self.filtered)

    def on_select(self):
        sel = self.gallery.selectedItems()
        if not sel: self.current=None; return
        name = sel[0].text()
        for it in self.filtered:
            if it["name"] == name: self.current = it; break
        if self.current:
            pm = QPixmap(self.current["path"]).scaled(QSize(720,720), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview.set_pixmap(pm)
            self.preview_label.setText(f"{self.current['name']} — {self.current['status']} | score: {self.current['scores']['final']:.1f}")

def headless_main(folder: Path):
    from worker import ScanManager, ScanConfig
    from PySide6.QtCore import QCoreApplication
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication(sys.argv)

    cfg = ScanConfig()
    manager = ScanManager(folder, cfg)

    def on_item(item):
        logging.info(f"Scanned item: {item['name']}")

    def on_finished(results):
        logging.info(f"Scan finished. Total items: {len(results)}")
        for item in results:
            logging.info(f"  - {item['name']}: {item['status']}")
        app.quit()

    manager.image_scanned.connect(on_item)
    manager.finished.connect(on_finished)

    logging.info(f"Starting headless scan of folder: {folder}")
    manager.run()
    app.exec()

def main():
    if len(sys.argv) > 1:
        folder_path = Path(sys.argv[1])
        if folder_path.is_dir():
            headless_main(folder_path)
            return

    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
