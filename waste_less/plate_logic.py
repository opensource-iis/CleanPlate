from __future__ import annotations

from PIL import Image


def evaluate_plate_image(file_storage) -> dict:
    """Estimate how much food remains on a plate from a photo.

    Returns a dict with a status, leftover_ratio, points, and a user-facing note.
    For the MVP demo, we use a simple heuristic based on darkness in the image:
    - clean plate => mostly bright, little dark food residue
    - partial leftovers => more dark pixels in the centre of the image
    - large leftovers => noticeable leftover food, so penalise the user
    """
    try:
        img = Image.open(file_storage).convert("RGB")
    except Exception:
        return {
            "status": "invalid",
            "leftover_ratio": 1.0,
            "points": -20,
            "message": "Invalid upload: this does not look like a real plate photo. You lost 20 points.",
        }

    width, height = img.size
    crop_left = int(width * 0.18)
    crop_top = int(height * 0.18)
    crop_right = int(width * 0.82)
    crop_bottom = int(height * 0.82)
    cropped = img.crop((crop_left, crop_top, crop_right, crop_bottom)).resize((150, 150))

    pixels = list(cropped.getdata())
    if not pixels:
        return {
            "status": "invalid",
            "leftover_ratio": 1.0,
            "points": -20,
            "message": "Invalid upload: this does not look like a real plate photo. You lost 20 points.",
        }

    dark_pixels = 0
    bright_pixels = 0
    luminance_values = []

    for r, g, b in pixels:
        luminance = (r * 0.299) + (g * 0.587) + (b * 0.114)
        luminance_values.append(luminance)
        if luminance < 170:
            dark_pixels += 1
        else:
            bright_pixels += 1

    total = dark_pixels + bright_pixels
    leftover_ratio = dark_pixels / total if total else 0.0
    avg_luminance = sum(luminance_values) / len(luminance_values) if luminance_values else 0
    luminance_variance = sum((v - avg_luminance) ** 2 for v in luminance_values) / len(luminance_values) if luminance_values else 0

    center_crop = img.crop((width * 0.2, height * 0.2, width * 0.8, height * 0.8)).resize((80, 80))
    center_pixels = list(center_crop.getdata())
    center_avg = sum((r * 0.299 + g * 0.587 + b * 0.114) for r, g, b in center_pixels) / len(center_pixels) if center_pixels else 0
    center_dark_ratio = sum(1 for r, g, b in center_pixels if (r * 0.299 + g * 0.587 + b * 0.114) < 170) / len(center_pixels) if center_pixels else 0

    border_crop = img.crop((width * 0.05, height * 0.05, width * 0.95, height * 0.95))
    border_pixels = list(border_crop.getdata())
    border_avg = sum((r * 0.299 + g * 0.587 + b * 0.114) for r, g, b in border_pixels) / len(border_pixels) if border_pixels else 0

    if (
        luminance_variance < 180
        and abs(center_avg - border_avg) < 35
        and (
            avg_luminance > 210
            or avg_luminance < 80
        )
    ):
        return {
            "status": "invalid",
            "leftover_ratio": round(leftover_ratio, 3),
            "points": -40,
            "message": "Invalid upload. You lost 40 points. Total points: {total_points}.",
        }

    if leftover_ratio > 0.55 and avg_luminance < 160 and center_avg < 110 and abs(center_avg - border_avg) < 45:
        return {
            "status": "invalid",
            "leftover_ratio": round(leftover_ratio, 3),
            "points": -40,
            "message": "Invalid upload. You lost 40 points. Total points: {total_points}.",
        }

    if center_dark_ratio > 0.32 or leftover_ratio >= 0.42:
        status = "leftover-heavy"
        points = -40
        message = "You lost 40 points. Total points: {total_points}."
    elif center_dark_ratio > 0.24 or leftover_ratio >= 0.30:
        status = "leftover-light"
        points = -15
        message = "You lost 15 points. Total points: {total_points}."
    else:
        status = "clean"
        points = 50
        message = "Plate approved! You earned 50 points. Total points: {total_points}."

    return {
        "status": status,
        "leftover_ratio": round(leftover_ratio, 3),
        "points": points,
        "message": message,
    }
