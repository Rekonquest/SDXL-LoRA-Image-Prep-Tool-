from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Dict
import fnmatch, csv
import imagehash
from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool, Slot
from PIL import PngImagePlugin

from PySide6.QtGui import QImage
from image_processing import (
    load_image_fix, pil_to_cv, passes_basic_rules, auto_rotate,
    phash64, phash_distance, score_image, bucket_square, cv_to_pil,
    auto_fix_to_standard, intelligent_square_crop
)
from utils import slugify
from caption_providers import (
    lmstudio_caption, lmstudio_tags, lmstudio_describe, lmstudio_get_bbox
)

@dataclass
class ScanConfig:
    min_side: int = 1024
    aspect_min: float = 0.5
    aspect_max: float = 2.0
    blur_target: float = 150.0
    noise_max: float = 12.0
    w_sharp: float = 0.5
    w_contrast: float = 0.3
    w_noise: float = 0.2
    dedupe_tol: int = 8
    pass_threshold: float = 95.0
    sel_min_score: float = 90.0
    include_globs: str = ""  # comma-separated globs
    exclude_globs: str = ""  # comma-separated globs

def _megapixels(w: int, h: int) -> float:
    return (w*h)/1_000_000.0

class ScanSignals(QObject):
    image_scanned = Signal(dict)
    progress = Signal(int)
    finished = Signal()

class ScanImageRunnable(QRunnable):
    def __init__(self, p: Path, cfg: ScanConfig, signals: ScanSignals):
        super().__init__()
        self.p = p
        self.cfg = cfg
        self.signals = signals

    def run(self):
        try:
            im = load_image_fix(self.p)
            w, h = im.size
            thumb_im = im.copy()
            thumb_im.thumbnail((180, 180))
            if thumb_im.mode != "RGB":
                thumb_im = thumb_im.convert("RGB")
            qimg = QImage(thumb_im.tobytes(), thumb_im.width, thumb_im.height, thumb_im.width * 3, QImage.Format.Format_RGB888)

            status = "PASS" if passes_basic_rules(w, h, self.cfg.min_side, self.cfg.aspect_min, self.cfg.aspect_max) else "FAIL"
            hsh_obj = imagehash.phash(im, hash_size=16)
            hsh = str(hsh_obj)

            cv = pil_to_cv(im)
            cv_rot = auto_rotate(cv)
            scores = score_image(cv_rot, sharp_target=self.cfg.blur_target, noise_max=self.cfg.noise_max,
                                 w_sharp=self.cfg.w_sharp, w_contrast=self.cfg.w_contrast, w_noise=self.cfg.w_noise)
            item = {
                "name": self.p.name, "path": str(self.p), "width": w, "height": h,
                "mp": _megapixels(w, h),
                "status": status, "duplicate_of": None, "scores": scores,
                "thumbnail_qimage": qimg, "phash": hsh
            }
            self.signals.image_scanned.emit(item)
        except Exception:
            pass
        finally:
            self.signals.progress.emit(1)

class ScanManager(QObject):
    image_scanned = Signal(dict)
    progress = Signal(int, int)
    finished = Signal(list)

    def __init__(self, folder: Path, cfg: ScanConfig):
        super().__init__()
        self.folder = folder
        self.cfg = cfg
        self.pool = QThreadPool.globalInstance()
        self.signals = ScanSignals()
        self.signals.image_scanned.connect(self.on_image_scanned)
        self.done = 0
        self.total = 0
        self.results = []

    def on_image_scanned(self, item):
        self.results.append(item)
        self.image_scanned.emit(item)

    def run(self):
        exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
        files = [p for p in self.folder.rglob("*") if p.suffix.lower() in exts]
        self.total = len(files)
        self.signals.progress.connect(self.on_progress)

        for p in files:
            runnable = ScanImageRunnable(p, self.cfg, self.signals)
            self.pool.start(runnable)

    def on_progress(self, v):
        self.done += v
        self.progress.emit(self.done, self.total)
        if self.done == self.total:
            self.on_finished()

    def on_finished(self):
        # Dedupe must be done after all images are scanned
        phash_index: List[Tuple[object, dict]] = []
        for item in sorted(self.results, key=lambda x: x["name"]):
            hsh_obj = imagehash.hex_to_hash(item["phash"])
            is_dup = False
            for old_obj, meta in phash_index:
                if (hsh_obj - old_obj) <= self.cfg.dedupe_tol:
                    item["duplicate_of"] = meta["name"]
                    item["status"] = "DUPLICATE"
                    is_dup = True
                    break
            if not is_dup:
                phash_index.append((hsh_obj, {"name": item["name"]}))
        self.finished.emit(self.results)

class ExportManager(QObject):
    progress = Signal(int, int)
    finished = Signal(str)

    def __init__(self, items: List[dict], out_dir: Path, buckets=(1024,1152,1216),
                 apply_autofix=True, cfg: ScanConfig|None=None, lm_settings: dict|None=None,
                 metadata_template: dict|None=None, enable_intelligent_crop: bool=True):
        super().__init__()
        self.items = items
        self.out_dir = out_dir
        self.buckets = buckets
        self.apply_autofix = apply_autofix
        self.cfg = cfg or ScanConfig()
        self.lm_settings = lm_settings or {}
        self.metadata_template = metadata_template or {}
        self.enable_intelligent_crop = enable_intelligent_crop
        self.pool = QThreadPool.globalInstance()
        self.done = 0
        self.total = len(self.items)
        self.manifest_rows = []

    def run(self):
        self._prepare_dirs()
        # Logic to handle duplicates before exporting
        groups = self._group_duplicates(self.items)
        keepers = set()
        for root_name, group in groups.items():
            k = self._keeper_logic(group)
            keepers.add(k["name"])

        for i, item in enumerate(self.items):
            runnable = ExportImageRunnable(item, i, self.out_dir, self.buckets, self.apply_autofix, self.cfg, self.lm_settings, self.metadata_template, self.enable_intelligent_crop, keepers, self.on_export_progress)
            self.pool.start(runnable)

    def on_export_progress(self, manifest_row):
        if manifest_row:
            self.manifest_rows.append(manifest_row)
        self.done += 1
        self.progress.emit(self.done, self.total)
        if self.done == self.total:
            self.on_export_finished()

    def on_export_finished(self):
        with open(self.out_dir / "manifest.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["name","path","status","bucket","selected_for_training","final_score","dup_of"])
            w.writeheader()
            w.writerows(self.manifest_rows)
        self.finished.emit(str(self.out_dir))

    def _prepare_dirs(self):
        for name in ("pass", "rescued", "maybe", "fail", "duplicates", "reports"):
            (self.out_dir / name).mkdir(parents=True, exist_ok=True)

    def _keeper_logic(self, group: List[dict]) -> dict:
        return sorted(group, key=lambda it: (it.get("mp", 0), it.get("scores", {}).get("final", 0)), reverse=True)[0]

    def _group_duplicates(self, items: List[dict]) -> Dict[str, List[dict]]:
        groups = {}
        for it in items:
            key = it.get("duplicate_of") or it["name"]
            groups.setdefault(key, []).append(it)
        return groups

class ExportImageRunnable(QRunnable):
    def __init__(self, item: dict, index: int, out_dir: Path, buckets, apply_autofix,
                 cfg, lm_settings, metadata_template, enable_intelligent_crop: bool, keepers, callback):
        super().__init__()
        self.item = item
        self.index = index
        self.out_dir = out_dir
        self.buckets = buckets
        self.apply_autofix = apply_autofix
        self.cfg = cfg
        self.lm_settings = lm_settings
        self.metadata_template = metadata_template
        self.enable_intelligent_crop = enable_intelligent_crop
        self.keepers = keepers
        self.callback = callback

    def run(self):
        manifest_row = None
        try:
            src = Path(self.item["path"])
            label = self.item.get("status", "")
            pre = self.item.get("scores", {})
            post = pre
            category = label.lower()

            # Selection gate: include/exclude patterns and min score
            path_for_match = str(src)
            if self.cfg.include_globs and not any(fnmatch.fnmatch(path_for_match.lower().replace("\\","/"), pat.strip().lower()) for pat in self.cfg.include_globs.split(",")):
                selected_for_training = False
            else:
                if any(fnmatch.fnmatch(path_for_match.lower().replace("\\","/"), pat.strip().lower()) for pat in self.cfg.exclude_globs.split(",")):
                    selected_for_training = False
                else:
                    selected_for_training = (pre.get("final",0) >= self.cfg.sel_min_score)

            # Duplicate placement
            if self.item["name"] not in self.keepers and label == "DUPLICATE":
                (self.out_dir / "duplicates" / src.name).write_bytes(Path(src).read_bytes())
                category_out = "duplicates"
            else:
                fixed_img = None
                accepted = (label == "PASS")
                im = load_image_fix(src)
                cv_orig = pil_to_cv(im)

                if label == "FAIL" and self.apply_autofix:
                    fixed_img, pre, post = auto_fix_to_standard(
                        cv_orig,
                        pass_threshold=self.cfg.pass_threshold,
                        sharp_target=self.cfg.blur_target, noise_max=self.cfg.noise_max,
                        w_sharp=self.cfg.w_sharp, w_contrast=self.cfg.w_contrast, w_noise=self.cfg.w_noise,
                        min_side=self.cfg.min_side, aspect_min=self.cfg.aspect_min, aspect_max=self.cfg.aspect_max
                    )
                    accepted = (post.get("final",0) >= self.cfg.pass_threshold)

                if accepted:
                    target_dir = "rescued" if (label == "FAIL") else "pass"
                    cv = fixed_img if fixed_img is not None else cv_orig
                    target = min(self.buckets, key=lambda b: abs(b - max(cv.shape[:2])))
                    if fixed_img is not None and self.enable_intelligent_crop:
                        out = intelligent_square_crop(cv, target)
                    else:
                        out = bucket_square(cv, target)

                    final_stem = src.stem
                    if self.lm_settings.get("enabled") and self.lm_settings.get("rename_pattern"):
                        try:
                            desc = lmstudio_describe(
                                self.lm_settings.get("endpoint"),
                                self.lm_settings.get("model"),
                                str(src)
                            )
                            slug = slugify(desc) if (desc and desc != "untitled") else "image"
                            final_stem = self.lm_settings["rename_pattern"].format(
                                prefix=self.lm_settings.get("prefix", ""),
                                index=self.index,
                                slug=slug
                            )
                        except Exception as e:
                            print(f"LM Studio rename failed for {src.name}: {e}")
                            final_stem = f"rename-failed-{self.index:05d}"

                    saved_path = self.out_dir / target_dir / f"{final_stem}.{target}.png"
                    pil_out = cv_to_pil(out)

                    info = PngImagePlugin.PngInfo()
                    if self.metadata_template.get("Artist"):
                        info.add_text("Artist", self.metadata_template["Artist"])
                    if self.metadata_template.get("Copyright"):
                        info.add_text("Copyright", self.metadata_template["Copyright"])
                    if self.metadata_template.get("ImageDescription"):
                        info.add_text("Description", self.metadata_template["ImageDescription"])
                    if self.metadata_template.get("UserComment"):
                        info.add_text("Comment", self.metadata_template["UserComment"])

                    pil_out.save(saved_path, optimize=True, pnginfo=info)
                    category_out = target_dir

                    if self.lm_settings.get("enabled"):
                        prompt_key = "caption_prompt_pass"
                        if category_out == "rescued":
                            prompt_key = "caption_prompt_rescued"

                        cap_prompt = self.lm_settings.get(prompt_key, "")
                        tag_prompt = self.lm_settings.get("tags_prompt", "")

                        if cap_prompt and self.lm_settings.get("save_captions", True):
                            try:
                                caption = lmstudio_caption(
                                    self.lm_settings.get("endpoint"),
                                    self.lm_settings.get("model"),
                                    str(saved_path),
                                    cap_prompt,
                                    self.lm_settings.get("vision_mode", False)
                                )
                                (saved_path.parent / f"{final_stem}.txt").write_text(caption, encoding="utf-8")
                            except Exception as e:
                                print(f"LM Studio caption failed for {src.name}: {e}")

                        if tag_prompt and self.lm_settings.get("save_captions", True):
                            try:
                                tags = lmstudio_tags(
                                    self.lm_settings.get("endpoint"),
                                    self.lm_settings.get("model"),
                                    str(saved_path),
                                    tag_prompt,
                                    self.lm_settings.get("vision_mode", False)
                                )
                                (saved_path.parent / f"{final_stem}.tags.txt").write_text(tags, encoding="utf-8")
                            except Exception as e:
                                print(f"LM Studio tagging failed for {src.name}: {e}")
                else:
                    final_score = post.get("final", pre.get("final",0))
                    near = (self.cfg.pass_threshold - final_score) <= 5.0
                    metrics_below = sum([
                        post.get("sharpness", pre.get("sharpness",0)) < 90.0,
                        post.get("contrast", pre.get("contrast",0)) < 90.0,
                        post.get("noise", pre.get("noise",0)) < 90.0
                    ])
                    category_out = "maybe" if (near or metrics_below == 1) else "fail"
                    (self.out_dir / category_out / src.name).write_bytes(Path(src).read_bytes())

            rep = self.out_dir / "reports" / f"{src.stem}.txt"
            with open(rep, "w", encoding="utf-8") as f:
                f.write(f"Image: {src.name}\n")
                f.write(f"Initial status: {label}\n")
                f.write(f"Selected for training (rule gate): {selected_for_training} (min={self.cfg.sel_min_score}, include='{self.cfg.include_globs}', exclude='{self.cfg.exclude_globs}')\n")
                f.write(f"PRE — sharp:{pre.get('sharpness',0):.1f} contrast:{pre.get('contrast',0):.1f} noise:{pre.get('noise',0):.1f} final:{pre.get('final',0):.1f}\n")
                f.write(f"POST — sharp:{post.get('sharpness',0):.1f} contrast:{post.get('contrast',0):.1f} noise:{post.get('noise',0):.1f} final:{post.get('final',0):.1f}\n")
                f.write(f"Bucket: {category_out}\n")

            manifest_row = {
                "name": src.name,
                "path": str(src),
                "status": label,
                "bucket": category_out,
                "selected_for_training": selected_for_training,
                "final_score": f"{post.get('final', pre.get('final',0)):.1f}",
                "dup_of": self.item.get("duplicate_of","")
            }
        except Exception:
            # Log error
            pass
        finally:
            self.callback(manifest_row)

class VLMCropSignals(QObject):
    job_done = Signal(str)

class VLMCropRunnable(QRunnable):
    def __init__(self, path: str, output_dir: Path, prompt: str,
                 lm_settings: dict, signals: VLMCropSignals):
        super().__init__()
        self.path = path
        self.output_dir = output_dir
        self.prompt = prompt
        self.lm_settings = lm_settings
        self.signals = signals

    @Slot()
    def run(self):
        try:
            bbox = lmstudio_get_bbox(
                self.lm_settings.get("endpoint"),
                self.lm_settings.get("model"),
                self.path,
                self.prompt
            )

            if not bbox:
                raise Exception("VLM did not return a valid bounding box.")

            cv_img = pil_to_cv(load_image_fix(Path(self.path)))
            h, w = cv_img.shape[:2]

            x1, y1, x2, y2 = bbox

            # Safety-check and clamp coordinates to image bounds
            x1 = max(0, min(x1, w - 1))
            y1 = max(0, min(y1, h - 1))
            x2 = max(0, min(x2, w))
            y2 = max(0, min(y2, h))

            # Ensure coordinates are valid (x1 < x2, y1 < y2)
            if x1 >= x2 or y1 >= y2:
                raise Exception(f"Invalid coordinates: [{x1},{y1},{x2},{y2}]")

            crop_img = cv_img[y1:y2, x1:x2]

            if crop_img.size == 0:
                raise Exception("Crop resulted in an empty image.")

            out_path = self.output_dir / Path(self.path).name
            cv_to_pil(crop_img).save(out_path, optimize=True)

        except Exception as e:
            print(f"VLM Crop failed for {self.path}: {e}")
        finally:
            self.signals.job_done.emit(self.path)

class VLMCropManager(QObject):
    progress = Signal(int, int)
    finished = Signal()

    def __init__(self, image_paths: list[str], output_dir: Path,
                 prompt: str, lm_settings: dict):
        super().__init__()
        self.image_paths = image_paths
        self.output_dir = output_dir
        self.prompt = prompt
        self.lm_settings = lm_settings

        self.signals = VLMCropSignals()
        self.signals.job_done.connect(self.on_job_done)

        self.total = len(self.image_paths)
        self.done = 0

    @Slot(str)
    def on_job_done(self, path):
        self.done += 1
        self.progress.emit(self.done, self.total)
        if self.done == self.total:
            self.finished.emit()

    @Slot()
    def run(self):
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            for path in self.image_paths:
                runnable = VLMCropRunnable(
                    path,
                    self.output_dir,
                    self.prompt,
                    self.lm_settings,
                    self.signals
                )
                QThreadPool.globalInstance().start(runnable)
        except Exception as e:
            print(f"VLMCropManager failed to start: {e}")
            self.finished.emit()
