#!/usr/bin/env python3
import os
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SCALE = 3
W = 320 * SCALE
H = 240 * SCALE

OUT_DIR = '/home/iamgyp/.gemini/antigravity/brain/4ac204ad-4cf7-4045-ae00-1a5d5eee63aa'

font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
font_regular = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'

font_sm = ImageFont.truetype(font_path, 10 * SCALE)
font_md = ImageFont.truetype(font_path, 14 * SCALE)
font_lg = ImageFont.truetype(font_path, 18 * SCALE)
font_xl = ImageFont.truetype(font_path, 20 * SCALE)

def create_base_canvas():
    img = Image.new('RGB', (W, H), (2, 4, 12))
    draw = ImageDraw.Draw(img)

    # Ambient particles
    particles = [
        (40, 60, 2, (30, 80, 140)),
        (120, 180, 3, (20, 120, 180)),
        (280, 70, 2, (40, 100, 160)),
        (70, 140, 4, (15, 60, 120)),
        (250, 190, 3, (30, 140, 200)),
        (300, 130, 2, (20, 90, 150)),
        (180, 45, 3, (50, 150, 220)),
        (90, 210, 2, (20, 80, 130)),
    ]
    for px, py, pr, pcol in particles:
        draw.ellipse([
            (px - pr) * SCALE, (py - pr) * SCALE,
            (px + pr) * SCALE, (py + pr) * SCALE
        ], fill=pcol)

    # Top Status Bar
    draw.line([(15 * SCALE, 20 * SCALE), (305 * SCALE, 20 * SCALE)], fill=(12, 36, 60), width=SCALE)
    # Pulsing Green Dot
    draw.ellipse([(22 * SCALE, 9 * SCALE), (28 * SCALE, 15 * SCALE)], fill=(0, 230, 64))
    draw.text((33 * SCALE, 12 * SCALE), "ANTIGRAVITY", fill=(130, 145, 165), font=font_sm, anchor="lm")
    draw.text((305 * SCALE, 12 * SCALE), "BLE 5.0", fill=(0, 190, 255), font=font_sm, anchor="rm")

    return img, draw

def draw_status_pill(draw, text):
    pill_w = 220 * SCALE
    pill_h = 28 * SCALE
    pill_x = (W - pill_w) // 2
    pill_y = 200 * SCALE
    draw.rounded_rectangle([pill_x, pill_y, pill_x + pill_w, pill_y + pill_h], radius=14 * SCALE, fill=(10, 28, 48), outline=(32, 75, 110), width=SCALE)
    draw.text((W // 2, pill_y + pill_h // 2), text, fill=(225, 240, 255), font=font_md, anchor="mm")

def render_idle():
    img, draw = create_base_canvas()

    def draw_eye(cx, cy, w, h, look_x, look_y):
        cx *= SCALE
        cy *= SCALE
        w *= SCALE
        h *= SCALE
        r = w // 3

        # Outer Neon Glow
        glow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow)
        for offset, alpha in [(12 * SCALE, 25), (7 * SCALE, 60), (3 * SCALE, 120)]:
            gdraw.rounded_rectangle([
                cx - w//2 - offset, cy - h//2 - offset,
                cx + w//2 + offset, cy + h//2 + offset
            ], radius=r + offset, fill=(0, 210, 255, alpha))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=2 * SCALE))
        img.paste(Image.alpha_composite(Image.new('RGBA', (W, H), (0, 0, 0, 0)), glow), (0, 0), glow)

        # Main Cyan Body
        draw.rounded_rectangle([cx - w//2, cy - h//2, cx + w//2, cy + h//2], radius=r, fill=(0, 235, 255))

        # Inner Iris
        iw = w - 16 * SCALE
        ih = h - 16 * SCALE
        ix = cx + int(look_x * 0.7 * SCALE)
        iy = cy + int(look_y * 0.7 * SCALE)
        ir = iw // 3
        draw.rounded_rectangle([ix - iw//2, iy - ih//2, ix + iw//2, iy + ih//2], radius=ir, fill=(0, 130, 180))

        # Core Pupil
        cw = iw - 14 * SCALE
        ch = ih - 14 * SCALE
        cr = cw // 3
        draw.rounded_rectangle([ix - cw//2, iy - ch//2, ix + cw//2, iy + ch//2], radius=cr, fill=(0, 235, 255))

        # 3D Pixar Specular Catchlights (Parallax)
        spec1_x = cx - w // 4 + int(look_x * 0.25 * SCALE)
        spec1_y = cy - h // 4 + int(look_y * 0.25 * SCALE)
        draw.ellipse([spec1_x - 6*SCALE, spec1_y - 6*SCALE, spec1_x + 6*SCALE, spec1_y + 6*SCALE], fill=(210, 250, 255))
        draw.ellipse([spec1_x - 4*SCALE, spec1_y - 4*SCALE, spec1_x + 4*SCALE, spec1_y + 4*SCALE], fill=(255, 255, 255))

        spec2_x = cx + w // 5 + int(look_x * 0.2 * SCALE)
        spec2_y = cy + h // 5 + int(look_y * 0.2 * SCALE)
        draw.ellipse([spec2_x - 2*SCALE, spec2_y - 2*SCALE, spec2_x + 2*SCALE, spec2_y + 2*SCALE], fill=(255, 255, 255))

    draw_eye(105, 105, 68, 84, 4, -2)
    draw_eye(215, 105, 68, 84, 4, -2)

    draw_status_pill(draw, "Antigravity Ready")
    path = os.path.join(OUT_DIR, "screen_idle.png")
    img.save(path)
    print("Saved:", path)

def render_thinking():
    img, draw = create_base_canvas()

    def draw_thinking_eye(cx, cy):
        cx *= SCALE
        cy *= SCALE
        w = 66 * SCALE
        h = 78 * SCALE
        r = w // 3

        # Outer Amber Glow
        glow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow)
        for offset, alpha in [(10 * SCALE, 30), (5 * SCALE, 80)]:
            gdraw.rounded_rectangle([
                cx - w//2 - offset, cy - h//2 - offset,
                cx + w//2 + offset, cy + h//2 + offset
            ], radius=r + offset, fill=(255, 190, 0, alpha))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=2 * SCALE))
        img.paste(Image.alpha_composite(Image.new('RGBA', (W, H), (0, 0, 0, 0)), glow), (0, 0), glow)

        # Amber Body
        draw.rounded_rectangle([cx - w//2, cy - h//2, cx + w//2, cy + h//2], radius=r, fill=(255, 205, 0))

        # Deep Core
        iw = w - 16 * SCALE
        ih = h - 16 * SCALE
        draw.rounded_rectangle([cx - iw//2, cy - ih//2, cx + iw//2, cy + ih//2], radius=iw//3, fill=(180, 110, 0))
        cw = iw - 14 * SCALE
        ch = ih - 14 * SCALE
        draw.rounded_rectangle([cx - cw//2, cy - ch//2, cx + cw//2, cy + ch//2], radius=cw//3, fill=(255, 215, 20))

        # 3D Orbiting planetary ring guide
        draw.ellipse([cx - 45*SCALE, cy - 28*SCALE, cx + 45*SCALE, cy + 28*SCALE], outline=(60, 45, 15), width=SCALE)

        # Orbiting Particle 1 (Gold)
        ox = int(26 * math.cos(0.8) * SCALE)
        oy = int(16 * math.sin(0.8) * SCALE)
        draw.ellipse([cx + ox - 6*SCALE, cy + oy - 6*SCALE, cx + ox + 6*SCALE, cy + oy + 6*SCALE], fill=(255, 160, 0))
        draw.ellipse([cx + ox - 4*SCALE, cy + oy - 4*SCALE, cx + ox + 4*SCALE, cy + oy + 4*SCALE], fill=(255, 255, 255))

        # Orbiting Particle 2 (Cyan)
        draw.ellipse([cx - ox - 4*SCALE, cy - oy - 4*SCALE, cx - ox + 4*SCALE, cy - oy + 4*SCALE], fill=(0, 220, 255))

    draw_thinking_eye(105, 105)
    draw_thinking_eye(215, 105)

    draw_status_pill(draw, "Synthesizing Solution...")
    path = os.path.join(OUT_DIR, "screen_thinking.png")
    img.save(path)
    print("Saved:", path)

def render_approval():
    img = Image.new('RGB', (W, H), (4, 8, 16))
    draw = ImageDraw.Draw(img)

    # Glassmorphism Card
    card_x = 10 * SCALE
    card_y = 8 * SCALE
    card_w = 300 * SCALE
    card_h = 224 * SCALE
    draw.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + card_h], radius=16 * SCALE, fill=(10, 20, 32), outline=(15, 55, 90), width=SCALE)
    draw.rounded_rectangle([card_x + 2*SCALE, card_y + 2*SCALE, card_x + card_w - 2*SCALE, card_y + card_h - 2*SCALE], radius=14 * SCALE, outline=(10, 35, 60), width=SCALE)

    # Tech Corner Brackets (Neon Cyan)
    b_len = 18 * SCALE
    col_bracket = (0, 220, 255)
    # Top-Left
    draw.line([(card_x, card_y), (card_x + b_len, card_y)], fill=col_bracket, width=2*SCALE)
    draw.line([(card_x, card_y), (card_x, card_y + b_len)], fill=col_bracket, width=2*SCALE)
    # Top-Right
    draw.line([(card_x + card_w - b_len, card_y), (card_x + card_w, card_y)], fill=col_bracket, width=2*SCALE)
    draw.line([(card_x + card_w, card_y), (card_x + card_w, card_y + b_len)], fill=col_bracket, width=2*SCALE)
    # Bottom-Left
    draw.line([(card_x, card_y + card_h), (card_x + b_len, card_y + card_h)], fill=col_bracket, width=2*SCALE)
    draw.line([(card_x, card_y + card_h - b_len), (card_x, card_y + card_h)], fill=col_bracket, width=2*SCALE)
    # Bottom-Right
    draw.line([(card_x + card_w - b_len, card_y + card_h), (card_x + card_w, card_y + card_h)], fill=col_bracket, width=2*SCALE)
    draw.line([(card_x + card_w, card_y + card_h - b_len), (card_x + card_w, card_y + card_h)], fill=col_bracket, width=2*SCALE)

    # Top Warning Badge
    badge_x = 22 * SCALE
    badge_y = 18 * SCALE
    badge_w = 276 * SCALE
    badge_h = 36 * SCALE
    draw.rounded_rectangle([badge_x, badge_y, badge_x + badge_w, badge_y + badge_h], radius=10 * SCALE, fill=(210, 60, 20))
    draw.text((W // 2, badge_y + badge_h // 2), "[ ! ] SECURITY PROMPT", fill=(255, 255, 255), font=font_md, anchor="mm")

    # Prompt Content Box
    box_x = 22 * SCALE
    box_y = 62 * SCALE
    box_w = 276 * SCALE
    box_h = 88 * SCALE
    draw.rounded_rectangle([box_x, box_y, box_x + box_w, box_y + box_h], radius=10 * SCALE, fill=(16, 28, 44), outline=(30, 50, 75), width=SCALE)
    draw.text((W // 2, box_y + box_h // 2), "Deploy to Production?", fill=(255, 220, 0), font=font_lg, anchor="mm")

    # Button 1: [ APPROVE ]
    btn1_x = 22 * SCALE
    btn1_y = 160 * SCALE
    btn1_w = 130 * SCALE
    btn1_h = 56 * SCALE
    draw.rounded_rectangle([btn1_x, btn1_y, btn1_x + btn1_w, btn1_y + btn1_h], radius=14 * SCALE, fill=(0, 160, 80), outline=(80, 240, 160), width=2*SCALE)
    draw.rounded_rectangle([btn1_x + 4*SCALE, btn1_y + 4*SCALE, btn1_x + btn1_w - 4*SCALE, btn1_y + 16*SCALE], radius=7 * SCALE, fill=(50, 200, 120))
    draw.text((btn1_x + btn1_w // 2, btn1_y + btn1_h // 2), "[ APPROVE ]", fill=(255, 255, 255), font=font_md, anchor="mm")

    # Button 2: [ DENY ]
    btn2_x = 168 * SCALE
    btn2_y = 160 * SCALE
    btn2_w = 130 * SCALE
    btn2_h = 56 * SCALE
    draw.rounded_rectangle([btn2_x, btn2_y, btn2_x + btn2_w, btn2_y + btn2_h], radius=14 * SCALE, fill=(190, 40, 40), outline=(255, 120, 120), width=2*SCALE)
    draw.rounded_rectangle([btn2_x + 4*SCALE, btn2_y + 4*SCALE, btn2_x + btn2_w - 4*SCALE, btn2_y + 16*SCALE], radius=7 * SCALE, fill=(230, 80, 80))
    draw.text((btn2_x + btn2_w // 2, btn2_y + btn2_h // 2), "[ DENY ]", fill=(255, 255, 255), font=font_md, anchor="mm")

    path = os.path.join(OUT_DIR, "screen_approval.png")
    img.save(path)
    print("Saved:", path)

def render_success():
    img, draw = create_base_canvas()

    def draw_happy_eye(cx, cy):
        cx *= SCALE
        cy *= SCALE
        r1 = 38 * SCALE
        r2 = 35 * SCALE
        # Smiling crescent arch
        draw.ellipse([cx - r1, cy - r1, cx + r1, cy + r1], fill=(0, 235, 100))
        draw.ellipse([cx - r2, cy - r2 + 15*SCALE, cx + r2, cy + r2 + 15*SCALE], fill=(2, 4, 12))

    draw_happy_eye(105, 102)
    draw_happy_eye(215, 102)

    # Glowing Blush Cheeks
    for cx in [78 * SCALE, 242 * SCALE]:
        cy = 138 * SCALE
        draw.ellipse([cx - 14*SCALE, cy - 14*SCALE, cx + 14*SCALE, cy + 14*SCALE], fill=(250, 90, 140))
        draw.ellipse([cx - 8*SCALE, cy - 8*SCALE, cx + 8*SCALE, cy + 8*SCALE], fill=(255, 150, 190))

    # Twinkling Sparkle Stars
    def draw_star(sx, sy, size):
        sx *= SCALE
        sy *= SCALE
        size *= SCALE
        draw.line([(sx - size, sy), (sx + size, sy)], fill=(255, 230, 0), width=2*SCALE)
        draw.line([(sx, sy - size), (sx, sy + size)], fill=(255, 230, 0), width=2*SCALE)
        draw.ellipse([sx - 2*SCALE, sy - 2*SCALE, sx + 2*SCALE, sy + 2*SCALE], fill=(255, 255, 255))

    draw_star(62, 75, 10)
    draw_star(258, 75, 10)

    draw_status_pill(draw, "Build Succeeded! (100%)")
    path = os.path.join(OUT_DIR, "screen_success.png")
    img.save(path)
    print("Saved:", path)

def render_composite_showcase():
    # Render a 2x2 grid showcase
    comp_w = W * 2 + 60
    comp_h = H * 2 + 140
    comp = Image.new('RGB', (comp_w, comp_h), (12, 16, 25))
    cdraw = ImageDraw.Draw(comp)

    # Title
    font_title = ImageFont.truetype(font_path, 28)
    font_sub = ImageFont.truetype(font_regular, 16)
    cdraw.text((comp_w // 2, 35), "Antigravity Desktop Buddy - Expressive Visual System", fill=(0, 220, 255), font=font_title, anchor="mm")
    cdraw.text((comp_w // 2, 68), "ESP32-S3 320x240 IPS Color Display | Real-Time Hardware Capture", fill=(140, 160, 185), font=font_sub, anchor="mm")

    s_idle = Image.open(os.path.join(OUT_DIR, "screen_idle.png")).resize((W, H))
    s_think = Image.open(os.path.join(OUT_DIR, "screen_thinking.png")).resize((W, H))
    s_appr = Image.open(os.path.join(OUT_DIR, "screen_approval.png")).resize((W, H))
    s_succ = Image.open(os.path.join(OUT_DIR, "screen_success.png")).resize((W, H))

    # Add Device Bezel to each
    def paste_with_bezel(src, x, y, label):
        bezel_pad = 12
        cdraw.rounded_rectangle([
            x - bezel_pad, y - bezel_pad,
            x + W + bezel_pad, y + H + bezel_pad
        ], radius=16, fill=(28, 32, 42), outline=(50, 60, 75), width=2)
        comp.paste(src, (x, y))
        cdraw.text((x + W // 2, y + H + 20), label, fill=(200, 220, 240), font=font_sub, anchor="mm")

    x1 = 20
    x2 = W + 40
    y1 = 95
    y2 = H + 135

    paste_with_bezel(s_idle, x1, y1, "1. IDLE (Pixar 3D Parallax Cyan Eyes + Breathing)")
    paste_with_bezel(s_think, x2, y1, "2. THINKING (Amber Gold Eyes + 3D Orbiting Rings)")
    paste_with_bezel(s_appr, x1, y2, "3. APPROVAL (Glassmorphism HUD + Touch Buttons)")
    paste_with_bezel(s_succ, x2, y2, "4. SUCCESS (Bouncy Smiling Eyes + Blush & Stars)")

    path = os.path.join(OUT_DIR, "showcase_all_states.png")
    comp.save(path)
    print("Saved composite showcase:", path)

if __name__ == '__main__':
    render_idle()
    render_thinking()
    render_approval()
    render_success()
    render_composite_showcase()
