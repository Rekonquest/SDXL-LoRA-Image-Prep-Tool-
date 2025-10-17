from PIL import Image, ImageFilter, ImageDraw
import numpy as np

# 1. Valid Image (with some noise to avoid zero variance)
img_valid = Image.new('RGB', (1024, 1024), color = 'green')
draw = ImageDraw.Draw(img_valid)
for i in range(100):
    x = np.random.randint(0, 1024)
    y = np.random.randint(0, 1024)
    draw.point((x, y), fill='white')
img_valid.save('test_images/valid.png')

# 2. Low Resolution Image
img_low_res = Image.new('RGB', (512, 512), color = 'red')
img_low_res.save('test_images/low_res.png')

# 3. Extreme Aspect Ratio Image
img_aspect_ratio = Image.new('RGB', (2048, 1023), color = 'blue')
img_aspect_ratio.save('test_images/extreme_aspect.png')

# 4. Blurry Image
# Create a noisy image and then blur it to ensure it fails the blur check
array = np.random.randint(0, 255, (1024, 1024, 3), dtype=np.uint8)
img_noisy = Image.fromarray(array, 'RGB')
img_blurry = img_noisy.filter(ImageFilter.GaussianBlur(radius=10))
img_blurry.save('test_images/blurry.png')

print("Test images created successfully.")
