
import io, hashlib
from pathlib import Path
from typing import Tuple, Optional, Dict
import numpy as np
from PIL import Image, ImageOps, ImageCms
import cv2
import imagehash

def load_image_fix(path: Path) -> Image.Image:
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode not in ("RGB","RGBA","L"):
            im = im.convert("RGB")
        if im.mode == "RGBA":
            bg = Image.new("RGB", im.size, (0,0,0))
            bg.paste(im, mask=im.split()[-1])
            im = bg
        icc = im.info.get("icc_profile")
        if icc:
            try:
                srgb = ImageCms.createProfile("sRGB")
                src = ImageCms.ImageCmsProfile(io.BytesIO(icc))
                im = ImageCms.profileToProfile(im, src, srgb, outputMode="RGB")
            except Exception:
                im = im.convert("RGB")
        else:
            im = im.convert("RGB")
        return im

def pil_to_cv(im: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)

def cv_to_pil(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(arr, cv2.COLOR_BGR2RGB))

def sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256(); h.update(b); return h.hexdigest()

def laplacian_variance(cv_img: np.ndarray) -> float:
    return float(cv2.Laplacian(cv_img, cv2.CV_64F).var())

def histogram_contrast_score(cv_img_gray: np.ndarray) -> float:
    hist = cv2.calcHist([cv_img_gray],[0],None,[256],[0,256]).flatten()
    used_bins = np.where(hist > 0)[0]
    if used_bins.size == 0: return 0.0
    span = used_bins[-1] - used_bins[0] + 1
    return 100.0 * (span/256.0)

def estimate_noise_std(cv_img_gray: np.ndarray) -> float:
    k = 32
    H, W = cv_img_gray.shape
    best_std = 999.0
    for y in range(0, H-k+1, max(8, k//2)):
        for x in range(0, W-k+1, max(8, k//2)):
            patch = cv_img_gray[y:y+k, x:x+k]
            if cv2.Laplacian(patch, cv2.CV_64F).var() < 5.0:
                s = float(patch.std())
                if s < best_std: best_std = s
    if best_std == 999.0: best_std = float(cv_img_gray.std())
    return best_std

def score_image(cv_img: np.ndarray, sharp_target=150.0, noise_max=12.0,
                w_sharp=0.5, w_contrast=0.3, w_noise=0.2) -> Dict[str, float]:
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    lv = laplacian_variance(cv_img)
    sharp = min(100.0, (lv / sharp_target) * 100.0)
    contrast = histogram_contrast_score(gray)
    noise_std = estimate_noise_std(gray)
    noise_score = max(0.0, (1.0 - (noise_std / noise_max)) * 100.0)
    final = (w_sharp*sharp) + (w_contrast*contrast) + (w_noise*noise_score)
    return {
        "sharpness": sharp,
        "contrast": contrast,
        "noise": noise_score,
        "final": final,
        "lap_variance": lv,
        "noise_std": noise_std
    }

def passes_basic_rules(w: int, h: int, min_side=1024, aspect_min=0.5, aspect_max=2.0) -> bool:
    if min(w,h) < min_side: return False
    aspect = (w/h) if h else 0
    if aspect < aspect_min or aspect > aspect_max: return False
    return True

def phash64(im: Image.Image) -> str:
    return str(imagehash.phash(im, hash_size=16))

def phash_distance(h1, h2) -> int:
    return imagehash.hex_to_hash(h1) - imagehash.hex_to_hash(h2)

def auto_rotate(cv_img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLines(edges, 1, 3.14159/180.0, 120)
    if lines is None: return cv_img
    angles = []
    for rho_theta in lines:
        rho, theta = rho_theta[0]
        deg = theta * 180.0 / 3.14159
        if deg > 90: deg -= 180
        angles.append(deg)
    if not angles: return cv_img
    m = np.median(angles)
    if abs(abs(m) - 90) < 15:
        return cv2.rotate(cv_img, cv2.ROTATE_90_CLOCKWISE)
    return cv_img

def face_cascade_path() -> str:
    import cv2 as _cv2
    return str(Path(_cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")

def detect_face_rect(cv_img: np.ndarray):
    cascade = cv2.CascadeClassifier(face_cascade_path())
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(gray, 1.2, 5, minSize=(64,64))
    if len(faces) == 0: return None
    x,y,w,h = max(faces, key=lambda r: r[2]*r[3])
    return (x,y,w,h)

def saliency_center(cv_img: np.ndarray):
    sal = cv2.saliency.StaticSaliencySpectralResidual_create()
    ok, salmap = sal.computeSaliency(cv_img)
    h,w = cv_img.shape[:2]
    if not ok:
        side = min(h,w); x=(w-side)//2; y=(h-side)//2
        return (x,y,side,side)
    salmap = (salmap*255).astype("uint8")
    m = cv2.moments(salmap)
    cx = int(m["m10"]/m["m00"]) if m["m00"] != 0 else w//2
    cy = int(m["m01"]/m["m00"]) if m["m00"] != 0 else h//2
    side = min(h,w)
    x = max(0, min(w-side, cx - side//2))
    y = max(0, min(h-side, cy - side//2))
    return (x,y,side,side)

def intelligent_square_crop(cv_img: np.ndarray, target: int=1024) -> np.ndarray:
    h,w = cv_img.shape[:2]
    scale = target / max(h,w)
    if scale < 1.0:
        cv_img = cv2.resize(cv_img, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_LANCZOS4)
        h,w = cv_img.shape[:2]
    r = detect_face_rect(cv_img)
    if r is None:
        x,y,side,side = saliency_center(cv_img)
    else:
        x,y,fw,fh = r
        side = min(max(fw, fh)*2, min(h,w))
        x = max(0, min(w-side, x + fw//2 - side//2))
        y = max(0, min(h-side, y + fh//2 - side//2))
    crop = cv_img[y:y+side, x:x+side]
    if crop.shape[0] != target:
        crop = cv2.resize(crop, (target,target), interpolation=cv2.INTER_LANCZOS4)
    return crop

def unsharp_mask(cv_img: np.ndarray, radius=1.5, amount=1.0) -> np.ndarray:
    blur = cv2.GaussianBlur(cv_img, (0,0), radius)
    return cv2.addWeighted(cv_img, 1+amount, blur, -amount, 0)

def clahe_normalize(cv_img: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(cv_img, cv2.COLOR_BGR2LAB)
    l,a,b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    l2 = clahe.apply(l)
    lab2 = cv2.merge([l2,a,b])
    return cv2.cvtColor(lab2, cv2.COLOR_LAB2BGR)

def minside_upscale(cv_img: np.ndarray, min_side=1024) -> np.ndarray:
    h,w = cv_img.shape[:2]
    if min(h,w) >= min_side: return cv_img
    scale = float(min_side) / float(min(h,w))
    nh, nw = int(round(h*scale)), int(round(w*scale))
    return cv2.resize(cv_img, (nw, nh), interpolation=cv2.INTER_LANCZOS4)

def auto_fix_to_standard(cv_img: np.ndarray,
                         pass_threshold=95.0,
                         sharp_target=150.0, noise_max=12.0,
                         w_sharp=0.5, w_contrast=0.3, w_noise=0.2,
                         min_side=1024, aspect_min=0.5, aspect_max=2.0):
    pre = score_image(cv_img, sharp_target, noise_max, w_sharp, w_contrast, w_noise)

    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    noise_std = estimate_noise_std(gray)
    if noise_std > (noise_max * 0.75):
        cv_img = cv2.fastNlMeansDenoisingColored(cv_img, None, 3, 3, 7, 21)

    cv_img = clahe_normalize(cv_img)

    if pre["sharpness"] < (pass_threshold * 0.6):
        cv_img = unsharp_mask(cv_img, radius=1.2, amount=0.8)

    cv_img = minside_upscale(cv_img, min_side=min_side)

    cv_img = intelligent_square_crop(cv_img, target=min_side)

    post = score_image(cv_img, sharp_target, noise_max, w_sharp, w_contrast, w_noise)
    return cv_img, pre, post

def bucket_square(cv_img: np.ndarray, long_side: int) -> np.ndarray:
    h,w = cv_img.shape[:2]
    side = long_side
    scale = side / max(h,w)
    if scale != 1.0:
        cv_img = cv2.resize(cv_img, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_LANCZOS4)
        h,w = cv_img.shape[:2]
    if h != side or w != side:
        canvas = np.zeros((side, side, 3), dtype=np.uint8)
        y = (side - h)//2; x = (side - w)//2
        canvas[y:y+h, x:x+w] = cv_img[:min(h,side), :min(w,side)]
        cv_img = canvas
    return cv_img


def jpeg_deblock(cv_img: np.ndarray) -> np.ndarray:
    import cv2
    return cv2.fastNlMeansDenoisingColored(cv_img, None, 2, 2, 7, 21)

def minside_upscale_guarded(cv_img: np.ndarray, min_side=1024, max_factor=2.0) -> np.ndarray:
    h,w = cv_img.shape[:2]
    if min(h,w) >= min_side: return cv_img
    factor = float(min_side) / float(min(h,w))
    if factor > max_factor:
        return cv_img
    nh, nw = int(round(h*factor)), int(round(w*factor))
    return cv2.resize(cv_img, (nw, nh), interpolation=cv2.INTER_LANCZOS4)

def clear_metadata_pillow(im: Image.Image) -> Image.Image:
    data = list(im.getdata())
    new = Image.new(im.mode, im.size)
    new.putdata(data)
    return new

def apply_exif_template_jpeg(img_bytes: bytes, template: dict) -> bytes:
    try:
        import piexif
    except Exception:
        return img_bytes
    try:
        exif_dict = {"0th":{}, "Exif":{}, "GPS":{}, "1st":{}, "thumbnail":None}
        if template.get("Artist"):
            exif_dict["0th"][piexif.ImageIFD.Artist] = template["Artist"].encode("utf-8")
        if template.get("Copyright"):
            exif_dict["0th"][piexif.ImageIFD.Copyright] = template["Copyright"].encode("utf-8")
        if template.get("ImageDescription"):
            exif_dict["0th"][piexif.ImageIFD.ImageDescription] = template["ImageDescription"].encode("utf-8")
        if template.get("UserComment"):
            exif_dict["Exif"][piexif.ExifIFD.UserComment] = template["UserComment"].encode("utf-8")
        exif_bytes = piexif.dump(exif_dict)
        return piexif.insert(exif_bytes, img_bytes)
    except Exception:
        return img_bytes
