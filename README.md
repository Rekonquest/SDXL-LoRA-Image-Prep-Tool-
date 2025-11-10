# Jewels — SDXL LoRA Image Prep Tool (Analyst MVP + Auto-Fix + Selection)

New:
- Triage export folders: `pass/`, `rescued/`, `maybe/` (human review), `fail/`, `duplicates/`, plus `reports/`.
- Duplicate handling: keeps the best (highest megapixels, then higher score) and files others under `duplicates/` with a pointer.
- Selection rules: include/exclude glob patterns and a minimum score gate to choose only the images you want for training at scale.
- Manifest CSV: `manifest.csv` with per-image scores, status, dup-of, and final placement.

## Added features
- Settings with persistence (~/.jewels_settings.json)
- LM Studio optional captioning for renaming (localhost endpoint)
- Build training/ from manifest
- EXIF clear + template injection

- LM Studio captioning: when enabled, saves paired .txt captions next to pass/rescued outputs using your endpoint/model.

- LM Studio captioning now supports per-bucket prompts (pass vs rescued), optional vision mode (base64 data URI), and multi-caption outputs (.txt and .tags.txt). Safety filters are not applied.
