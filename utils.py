
import re, unicodedata, os, json
from pathlib import Path

def slugify(text: str, allow_unicode=False):
    text = str(text)
    if allow_unicode:
        text = unicodedata.normalize('NFKC', text)
    else:
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^\w\s-]', '', text.lower())
    text = re.sub(r'[-\s]+', '-', text).strip('-_')
    return text[:120]

class AppSettings:
    DEFAULTS = {
        "pass_threshold": 95.0,
        "select_min_score": 90.0,
        "include_globs": "",
        "exclude_globs": "",
        "buckets": [1024,1152,1216],
        "autofix": True,
        "enable_intelligent_crop": True,
        "max_upscale_factor": 2.0,
        "enable_deblock": True,
        "metadata_template": {
            "Artist": "",
            "Copyright": "",
            "ImageDescription": "",
            "UserComment": ""
        },
        "lmstudio": {
            "enabled": False,
            "endpoint": "http://127.0.0.1:1234/v1/chat/completions",
            "model": "gpt-4o-mini-gguf",
            "prefix": "",
            "rename_pattern": "{prefix}{index:05d}_{slug}",
            "save_captions": True,
            "vision_mode": False,
            "caption_prompt_pass": "Describe the image in 1–2 sentences for LoRA training: subject, pose, style, lighting, setting. Avoid punctuation-heavy prose.",
            "caption_prompt_rescued": "Provide a concise 1–2 sentence caption suitable for training on a cleaned/restored image. Focus on core visual content only.",
            "tags_prompt": "Return a comma-separated list of 8–15 short tags (no #) describing subject, style, media, lighting, composition, mood."
        }
    }

    def __init__(self, path: Path):
        self.path = Path(path)
        self.data = json.loads(json.dumps(self.DEFAULTS))  # deep copy
        self.load()

    def load(self):
        if self.path.exists():
            try:
                self.data.update(json.loads(self.path.read_text(encoding="utf-8")))
            except Exception:
                pass

    def save(self):
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
