"""
OG Image Generator — creates share preview cards for social media.
"""

from PIL import Image, ImageDraw, ImageFont
import io


def generate_og_image(title=None, subtitle=None) -> bytes:
    """
    Generate a 1200x630 OG share image.
    Dark background, clean typography, blue accent.
    """
    W, H = 1200, 630
    img = Image.new("RGBA", (W, H), "#171717")
    draw = ImageDraw.Draw(img)

    # Blue accent bar at top
    draw.rectangle([(0, 0), (W, 8)], fill="#0072F5")

    # Try to find system fonts (macOS)
    font_paths = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSDisplay.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    title_font = None
    sub_font = None
    for fp in font_paths:
        try:
            title_font = ImageFont.truetype(fp, 64)
            sub_font = ImageFont.truetype(fp, 28)
            break
        except Exception:
            continue

    if not title_font:
        title_font = ImageFont.load_default()
        sub_font = ImageFont.load_default()

    # Logo area
    draw.ellipse([(60, 50), (80, 70)], fill="#0072F5")
    draw.text((95, 38), "TrendPulse", fill="#666666", font=ImageFont.truetype(title_font.path, 24) if title_font else sub_font)

    # Main title
    main_title = title or "Real-time Market Data & Tech News"
    draw.text((60, 200), main_title, fill="#FFFFFF", font=title_font)

    # Subtitle
    sub = subtitle or "Hacker News · Stocks · Crypto · GitHub Trending"
    draw.text((60, 310), sub, fill="#808080", font=sub_font)

    # Bottom tags
    tags = ["📈 Stocks", "₿ Crypto", "🔗 HN", "💻 GitHub"]
    x = 60
    y = H - 100
    tag_font = sub_font
    for tag in tags:
        bbox = draw.textbbox((0, 0), tag, font=tag_font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        pad = 16
        draw.rounded_rectangle([(x, y), (x + tw + pad*2, y + th + pad)], radius=20, fill="#2A2A2A")
        draw.text((x + pad, y + pad//2), tag, fill="#999999", font=tag_font)
        x += tw + pad*2 + 16

    # URL at bottom
    draw.text((60, H - 38), "trendscan.org", fill="#555555", font=tag_font)

    # Save to bytes
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
