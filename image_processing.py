from PIL import Image, ExifTags
import cv2
import numpy as np

# Load the Haar Cascade for face detection
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def scan_image_quality(image_path, settings):
    try:
        # 1. Aspect Ratio and Resolution Check
        with Image.open(image_path) as img:
            width, height = img.size
            aspect_ratio = width / height
            if aspect_ratio > settings["max_aspect_ratio"] or aspect_ratio < settings["min_aspect_ratio"]:
                return "Fail", f"Extreme aspect ratio ({aspect_ratio:.2f})"
            if width < settings["min_resolution"] or height < settings["min_resolution"]:
                return "Fail", f"Resolution too low ({width}x{height})"

        # 2. Blur Check
        image = cv2.imread(image_path)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        if laplacian_var < settings["blur_threshold"]:
            return "Fail", f"Image is likely blurry (Laplacian variance: {laplacian_var:.2f})"

        return "Pass", "All checks passed"

    except Exception as e:
        return "Error", f"Could not process: {e}"

def auto_rotate_image(image_path):
    try:
        image = Image.open(image_path)

        # Check for EXIF orientation tag
        for orientation in ExifTags.TAGS.keys():
            if ExifTags.TAGS[orientation] == 'Orientation':
                break

        exif = dict(image._getexif().items())

        if exif[orientation] == 3:
            return image.rotate(180, expand=True)
        elif exif[orientation] == 6:
            return image.rotate(270, expand=True)
        elif exif[orientation] == 8:
            return image.rotate(90, expand=True)

        return image # Return original if no rotation needed
    except (AttributeError, KeyError, IndexError):
        # Content-aware fallback
        img = cv2.imread(image_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100, minLineLength=100, maxLineGap=10)

        if lines is not None:
            angles = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                angles.append(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)

            median_angle = np.median(angles)

            if abs(median_angle) < 45: # Horizontal
                return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            elif abs(median_angle - 90) < 45: # Rotated 90 degrees
                return Image.fromarray(cv2.cvtColor(cv2.rotate(img, cv2.ROTATE_90_COUNTER_CLOCKWISE), cv2.COLOR_BGR2RGB))
            elif abs(median_angle + 90) < 45: # Rotated -90 degrees
                return Image.fromarray(cv2.cvtColor(cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE), cv2.COLOR_BGR2RGB))

        return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)) # Return original if no lines found

def auto_crop_image(image_path):
    image = cv2.imread(image_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)

    if len(faces) > 0:
        x, y, w, h = faces[0]
        return x, y, w, h # Return the rect
    else:
        # Saliency-based fallback
        saliency = cv2.saliency.StaticSaliencyFineGrained_create()
        (success, saliencyMap) = saliency.computeSaliency(image)
        saliencyMap = (saliencyMap * 255).astype("uint8")

        # Threshold the saliency map to get a binary map
        threshMap = cv2.threshold(saliencyMap, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]

        # Find contours of the most salient region
        contours, _ = cv2.findContours(threshMap, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            # Get the largest contour
            largest_contour = max(contours, key=cv2.contourArea)
            return cv2.boundingRect(largest_contour)

    return None
