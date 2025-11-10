
from PySide6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox, QLineEdit, QDoubleSpinBox, QCheckBox
from utils import AppSettings

class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.s = settings
        lay = QFormLayout(self)

        self.pass_thr = QDoubleSpinBox(); self.pass_thr.setRange(50,100); self.pass_thr.setValue(self.s.data["pass_threshold"])
        self.sel_thr = QDoubleSpinBox(); self.sel_thr.setRange(50,100); self.sel_thr.setValue(self.s.data["select_min_score"])
        self.include = QLineEdit(self.s.data["include_globs"])
        self.exclude = QLineEdit(self.s.data["exclude_globs"])
        self.max_up = QDoubleSpinBox(); self.max_up.setRange(1.0,8.0); self.max_up.setSingleStep(0.1); self.max_up.setValue(self.s.data["max_upscale_factor"])
        self.deblock = QCheckBox(); self.deblock.setChecked(self.s.data["enable_deblock"])
        self.enable_crop = QCheckBox(); self.enable_crop.setChecked(self.s.data["enable_intelligent_crop"])
        self.artist = QLineEdit(self.s.data["metadata_template"].get("Artist",""))
        self.copyright = QLineEdit(self.s.data["metadata_template"].get("Copyright",""))
        self.desc = QLineEdit(self.s.data["metadata_template"].get("ImageDescription",""))
        self.comment = QLineEdit(self.s.data["metadata_template"].get("UserComment",""))
        self.lm_en = QCheckBox(); self.lm_en.setChecked(self.s.data["lmstudio"]["enabled"])
        self.lm_ep = QLineEdit(self.s.data["lmstudio"]["endpoint"])
        self.lm_model = QLineEdit(self.s.data["lmstudio"]["model"])
        self.lm_prefix = QLineEdit(self.s.data["lmstudio"]["prefix"])
        self.lm_pattern = QLineEdit(self.s.data["lmstudio"]["rename_pattern"])

        lay.addRow("Pass threshold ≥", self.pass_thr)
        lay.addRow("Select min score ≥", self.sel_thr)
        lay.addRow("Include globs", self.include)
        lay.addRow("Exclude globs", self.exclude)
        lay.addRow("Max upscale factor", self.max_up)
        lay.addRow("Enable JPEG deblock", self.deblock)
        lay.addRow("Enable intelligent crop", self.enable_crop)
        lay.addRow("EXIF Artist", self.artist)
        lay.addRow("EXIF Copyright", self.copyright)
        lay.addRow("EXIF ImageDescription", self.desc)
        lay.addRow("EXIF UserComment", self.comment)
        lay.addRow("LM Studio enable", self.lm_en)
        lay.addRow("LM Studio endpoint", self.lm_ep)
        lay.addRow("LM Studio model", self.lm_model)
        lay.addRow("Filename prefix", self.lm_prefix)
        lay.addRow("Rename pattern", self.lm_pattern)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addRow(btns)

    def accept(self):
        self.s.data["pass_threshold"] = float(self.pass_thr.value())
        self.s.data["select_min_score"] = float(self.sel_thr.value())
        self.s.data["include_globs"] = self.include.text().strip()
        self.s.data["exclude_globs"] = self.exclude.text().strip()
        self.s.data["max_upscale_factor"] = float(self.max_up.value())
        self.s.data["enable_deblock"] = self.deblock.isChecked()
        self.s.data["enable_intelligent_crop"] = self.enable_crop.isChecked()
        self.s.data["metadata_template"] = {
            "Artist": self.artist.text(),
            "Copyright": self.copyright.text(),
            "ImageDescription": self.desc.text(),
            "UserComment": self.comment.text(),
        }
        self.s.data["lmstudio"]["enabled"] = self.lm_en.isChecked()
        self.s.data["lmstudio"]["endpoint"] = self.lm_ep.text().strip()
        self.s.data["lmstudio"]["model"] = self.lm_model.text().strip()
        self.s.data["lmstudio"]["prefix"] = self.lm_prefix.text().strip()
        self.s.data["lmstudio"]["rename_pattern"] = self.lm_pattern.text().strip()
        self.s.save()
        super().accept()
