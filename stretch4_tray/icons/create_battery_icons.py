import os
from PIL import Image, ImageDraw, ImageChops

from stretch4_tray.battery_monitor import BatteryLevel

# --- CONFIGURATION ---
INPUT_FILENAME = "tray_icon.png"
OUTPUT_DIR = "."


LIGHTNING_COLOR = (255, 255, 255) # White lightning bolt
# Alpha for the lightning bolt itself (0.6 ~ 153/255)
LIGHTNING_ALPHA_VAL = int(255 * 0.6)
# Alpha factor for the empty/top part of the battery (0.7)
EMPTY_AREA_ALPHA_FACTOR = 0.6

def create_placeholder_logo():
    img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Draw a blue circle as a dummy logo
    draw.ellipse([2, 2, 62, 62], fill=(52, 152, 219), outline=(41, 128, 185), width=2)
    img.save(INPUT_FILENAME)
    print(f"No input found. Created a placeholder '{INPUT_FILENAME}' for you.")

def create_dimmed_battery_level(image, percentage):
    """
    Composites the image so the bottom (percentage) is full brightness,
    and the top is completely visible but with alpha reduced by factor 0.7.
    """
    width, height = image.size

    # --- Step 1: Create the "Dimmed" version of the whole image ---
    # Create a solid gray mask representing the dim factor (e.g., 0.7 * 255 = ~178)
    dim_factor_mask = Image.new('L', image.size, int(255 * EMPTY_AREA_ALPHA_FACTOR))
    
    # Get original alpha and multiply it by the dim factor
    original_alpha = image.split()[3]
    dimmed_alpha = ImageChops.multiply(original_alpha, dim_factor_mask)
    
    # Create the dimmed image copy
    dimmed_image = image.copy()
    dimmed_image.putalpha(dimmed_alpha)

    # --- Step 2: Create the Level Split Mask ---
    # Black (0) for the top (empty part), White (255) for bottom (full part)
    split_mask = Image.new('L', (width, height), 0)
    draw = ImageDraw.Draw(split_mask)
    
    fill_height = int(height * (percentage / 100))
    y_start = height - fill_height
    
    # Draw white rectangle for the filled bottom portion
    draw.rectangle([0, y_start, width, height], fill=255)

    # --- Step 3: Composite ---
    # Image.composite(image_for_white_pixels, image_for_black_pixels, mask)
    # Where mask is white (bottom), use full strength 'image'.
    # Where mask is black (top), use 'dimmed_image'.
    result = Image.composite(image, dimmed_image, split_mask)
    
    return result

def draw_lightning_overlay(image):
    """
    Draws a scaled-down lightning bolt in the center with 0.6 Alpha.
    """
    w, h = image.size
    
    overlay = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Original normalized points covering most of the image
    points_norm_original = [
        (0.55, 0.10), (0.35, 0.10), (0.25, 0.50), 
        (0.45, 0.50), (0.35, 0.90), (0.75, 0.40), (0.55, 0.40),
    ]
    
    # --- Scaling Logic ---
    # 60% smaller means the new size is 40% of original. Scale factor = 0.4.
    scale_factor = 0.3
    cx, cy = 0.95, 0.15 # Center pivot point

    scaled_points_pixels = []
    for x, y in points_norm_original:
        # Scale distance from center
        nx = cx + (x - cx) * scale_factor
        ny = cy + (y - cy) * scale_factor
        # Convert to pixels and add to list
        scaled_points_pixels.append((nx * w, ny * h))

    # Define color with specific alpha for the bolt itself
    fill_color = LIGHTNING_COLOR + (LIGHTNING_ALPHA_VAL,)
    
    # Draw the scaled bolt
    draw.polygon(scaled_points_pixels, fill=fill_color)
    
    # Composite overlay onto the image
    return Image.alpha_composite(image, overlay)

def main():
    if not os.path.exists(INPUT_FILENAME):
        raise Exception(f"{INPUT_FILENAME} does not exist")
        
    try:
        original = Image.open(INPUT_FILENAME).convert("RGBA")
    except Exception as e:
        print(f"Error opening image: {e}")
        return

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    print(f"Generating icons based on '{INPUT_FILENAME}'...")

    # Range 0 to 100, step 10
    for level in range(0, 101, 10):
        
        # 1. Create the base icon (top dimmed, bottom full)
        base_img = create_dimmed_battery_level(original, level)
        
        # Save standard variant
        filename = f"{OUTPUT_DIR}/battery_{level:03d}.png"
        base_img.save(filename, "PNG")
        
        # 2. Add the smaller lightning bolt overlay
        charging_img = draw_lightning_overlay(base_img)
        
        # Save charging variant
        filename_charge = f"{OUTPUT_DIR}/charging_{level:03d}.png"
        charging_img.save(filename_charge, "PNG")

    for level in BatteryLevel:
        name, percentage = level.name, level.value
        # --- 1. Not Charging Variant ---
        base_img = create_dimmed_battery_level(original, percentage)
        filename_base = f"battery-{name}.png"
        path_base = os.path.join(OUTPUT_DIR, filename_base)
        base_img.save(path_base, "PNG")
        print(f"Saved: {filename_base}")
        
        # --- 2. Charging Variant ---
        charge_img = draw_lightning_overlay(base_img)
        filename_charge = f"battery-{name}-charging.png"
        path_charge = os.path.join(OUTPUT_DIR, filename_charge)
        charge_img.save(path_charge, "PNG")
        print(f"Saved: {filename_charge}")


    print(f"Done! Created 27 icons in '{OUTPUT_DIR}'")

if __name__ == "__main__":
    main()