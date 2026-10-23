from PIL import Image, ImageDraw

def create_app_icon():
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Outer rounded rect / glow
    # Background rounded square
    margin = 12
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=48,
        fill=(22, 24, 38, 255),
        outline=(77, 170, 252, 220),
        width=6
    )

    # Draw a cute stylized robot face with Antigravity glow
    # Cyan eyes
    eye_w, eye_h = 36, 48
    draw.rounded_rectangle([70, 95, 70 + eye_w, 95 + eye_h], radius=16, fill=(77, 215, 252, 255))
    draw.rounded_rectangle([150, 95, 150 + eye_w, 95 + eye_h], radius=16, fill=(77, 215, 252, 255))
    # Eye shines
    draw.ellipse([88, 102, 98, 112], fill=(255, 255, 255, 240))
    draw.ellipse([168, 102, 178, 112], fill=(255, 255, 255, 240))

    # Cute smile
    draw.arc([100, 150, 156, 185], start=20, end=160, fill=(77, 215, 252, 255), width=6)

    # Antenna
    draw.line([128, margin + 4, 128, 60], fill=(168, 85, 247, 255), width=6)
    draw.ellipse([120, margin - 2, 136, margin + 14], fill=(77, 215, 252, 255))

    # BLE signal waves on the sides
    draw.arc([30, 100, 55, 140], start=110, end=250, fill=(77, 170, 252, 180), width=4)
    draw.arc([201, 100, 226, 140], start=-70, end=70, fill=(77, 170, 252, 180), width=4)

    img.save("/home/iamgyp/claude/esp32/app_icon.png", format="PNG")
    # Save as .ico with multiple sizes
    img.save(
        "/home/iamgyp/claude/esp32/app_icon.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    )
    print("Icons generated successfully!")

if __name__ == "__main__":
    create_app_icon()
