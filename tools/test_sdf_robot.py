#!/usr/bin/env python3
"""
V3 Final Prototype of the C++ 3D SDF + Phong Shader & Visor Neon Shader for ESP32-S3 (320x240).
Includes kinematic waving arm rotation, full-visibility Approval hologram, and all 5 states.
"""
import math
import os
import random
from PIL import Image, ImageDraw, ImageFont

W, H = 320, 240
OUT_DIR = "/home/iamgyp/.gemini/antigravity/brain/4ac204ad-4cf7-4045-ae00-1a5d5eee63aa"

def clamp(x, a, b):
    return a if x < a else (b if x > b else x)

def smoothstep(edge0, edge1, x):
    t = clamp((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)

def mix(a, b, t):
    return a + (b - a) * t

def mix_color(c1, c2, t):
    t = clamp(t, 0.0, 1.0)
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )

def add_glow(base, glow_col, intensity):
    intensity = clamp(intensity, 0.0, 1.0)
    return (
        min(255, int(base[0] + glow_col[0] * intensity)),
        min(255, int(base[1] + glow_col[1] * intensity)),
        min(255, int(base[2] + glow_col[2] * intensity)),
    )

def sd_round_box(px, py, bx, by, r):
    qx = abs(px) - bx + r
    qy = abs(py) - by + r
    return math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - r

def sd_segment(px, py, ax, ay, bx, by):
    pax, pay = px - ax, py - ay
    bax, bay = bx - ax, by - ay
    h = clamp((pax * bax + pay * bay) / max(bax * bax + bay * bay, 0.0001), 0.0, 1.0)
    return math.hypot(pax - bax * h, pay - bay * h), h

def armor_3d_color(nx, ny):
    nz2 = max(0.0, 1.0 - nx*nx - ny*ny)
    nz = math.sqrt(nz2)

    lx, ly, lz = -0.40, -0.52, 0.75
    diff = max(0.0, nx*lx + ny*ly + nz*lz)

    hx, hy, hz = -0.20, -0.26, 0.94
    spec = max(0.0, nx*hx + ny*hy + nz*hz) ** 28.0

    rim = (1.0 - nz) ** 2.4

    d_pow = diff ** 0.72
    r = mix(92, 240, d_pow) + spec * 58.0
    g = mix(122, 247, d_pow) + spec * 58.0
    b = mix(164, 255, d_pow) + spec * 58.0

    if nx > 0.05 or ny > 0.15:
        r = mix(r, 55, rim * 0.48)
        g = mix(g, 195, rim * 0.48)
        b = mix(b, 255, rim * 0.48)
    else:
        r = mix(r, 255, rim * 0.35)
        g = mix(g, 255, rim * 0.35)
        b = mix(b, 255, rim * 0.35)

    return (int(clamp(r, 0, 255)), int(clamp(g, 0, 255)), int(clamp(b, 0, 255)))

def draw_sdf_capsule(pixels, x1, y1, x2, y2, r1, r2, mode="armor"):
    pad = int(max(r1, r2) + 3)
    x0 = max(0, int(min(x1, x2) - pad))
    x_end = min(W - 1, int(max(x1, x2) + pad))
    y0 = max(0, int(min(y1, y2) - pad))
    y_end = min(H - 1, int(max(y1, y2) + pad))

    dx_line = x2 - x1
    dy_line = y2 - y1
    len_sq = max(dx_line * dx_line + dy_line * dy_line, 0.001)

    for y in range(y0, y_end + 1):
        for x in range(x0, x_end + 1):
            pax, pay = x - x1, y - y1
            h = clamp((pax * dx_line + pay * dy_line) / len_sq, 0.0, 1.0)
            cx = x1 + dx_line * h
            cy = y1 + dy_line * h
            r = r1 + (r2 - r1) * h
            dx = x - cx
            dy = y - cy
            dist = math.hypot(dx, dy) - r
            if dist < 0.75:
                cov = smoothstep(0.75, -0.55, dist)
                nx = clamp(dx / max(r, 1.0), -0.95, 0.95)
                ny = clamp(dy / max(r, 1.0), -0.95, 0.95)
                if mode == "dark_joint":
                    lit = max(0.0, -0.4 * nx - 0.5 * ny + 0.55)
                    col = mix_color((25, 36, 52), (92, 112, 138), lit)
                else:
                    col = armor_3d_color(nx, ny)
                pixels[x, y] = mix_color(pixels[x, y], col, cov)

def draw_sdf_disc(pixels, cx, cy, r, inner_col, outer_col, rim_col=None, glow_col=None, glow_r=0.0):
    max_r = r + glow_r + 2
    x0, x1 = max(0, int(cx - max_r)), min(W - 1, int(cx + max_r))
    y0, y1 = max(0, int(cy - max_r)), min(H - 1, int(cy + max_r))
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            d = math.hypot(x - cx, y - cy) - r
            if glow_col and d > 0 and d < glow_r:
                g_int = (1.0 - d / glow_r) ** 2.0 * 0.55
                pixels[x, y] = add_glow(pixels[x, y], glow_col, g_int)
            if d < 0.75:
                cov = smoothstep(0.75, -0.55, d)
                t = clamp((d + r) / max(r, 1.0), 0.0, 1.0)
                col = mix_color(inner_col, outer_col, t)
                if rim_col and d > -1.3:
                    col = mix_color(col, rim_col, smoothstep(-1.3, 0.0, d))
                pixels[x, y] = mix_color(pixels[x, y], col, cov)

def draw_waving_right_arm(pixels, elbow_x, elbow_y, wave_deg, y_off=0.0):
    # Shoulder joint & upper arm
    draw_sdf_capsule(pixels, 114, 148 + y_off, 114, 148 + y_off, 9.5, 9.5, "dark_joint")
    draw_sdf_capsule(pixels, 108, 145 + y_off, elbow_x + 2, elbow_y + 3 + y_off, 9.5, 10.5, "armor")
    draw_sdf_capsule(pixels, elbow_x, elbow_y + y_off, elbow_x, elbow_y + y_off, 8.2, 8.2, "dark_joint")

    # Rotate forearm & hand around elbow_x, elbow_y by wave_deg
    rad = math.radians(wave_deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)

    def rot(dx, dy):
        return (elbow_x + dx * cos_a - dy * sin_a, elbow_y + y_off + dx * sin_a + dy * cos_a)

    # Forearm from (0, -2) to (-10, -20)
    fa1 = rot(-1, -2)
    fa2 = rot(-10, -20)
    draw_sdf_capsule(pixels, fa1[0], fa1[1], fa2[0], fa2[1], 10.2, 8.8, "armor")

    # Palm at (-13, -27)
    palm = rot(-13, -27)
    draw_sdf_capsule(pixels, palm[0], palm[1], palm[0], palm[1], 7.2, 7.2, "dark_joint")

    # 4 Fingers relative to elbow
    finger_defs = [
        (-19, -28, -27, -33, 2.7),
        (-17, -33, -21, -42, 2.8),
        (-12, -34, -13, -44, 2.8),
        ( -7, -32,  -5, -41, 2.6),
    ]
    for fx1, fy1, fx2, fy2, fr in finger_defs:
        p1 = rot(fx1, fy1)
        p2 = rot(fx2, fy2)
        draw_sdf_capsule(pixels, p1[0], p1[1], p2[0], p2[1], fr, fr * 0.85, "armor")

def render_bot_state(state="idle"):
    img = Image.new("RGB", (W, H), (0, 0, 0))
    pixels = img.load()

    is_err = (state == "error")
    is_think = (state == "thinking")
    is_succ = (state == "success")
    is_appr = (state == "approval")

    cx_bg, cy_bg = 160.0, 115.0
    hud_col = (255, 70, 50) if is_err else ((255, 200, 40) if is_think else (0, 210, 255))

    for y in range(H):
        for x in range(W):
            dx = x - cx_bg
            dy = y - cy_bg
            dist_norm = math.hypot(dx / 145.0, dy / 118.0)
            t = clamp(1.0 - dist_norm * 0.85, 0.0, 1.0)
            t2 = t * t
            if is_err:
                r, g, b = int(mix(6, 52, t2)), int(mix(4, 14, t2)), int(mix(14, 28, t2))
            else:
                r, g, b = int(mix(2, 16, t2)), int(mix(6, 72, t2)), int(mix(18, 136, t2))

            rad = math.hypot(dx, dy)
            ang = math.degrees(math.atan2(dy, dx)) % 360.0

            d_r1 = abs(rad - 106.0)
            if d_r1 < 1.2:
                r, g, b = add_glow((r, g, b), hud_col, (1.0 - d_r1 / 1.2) * 0.22)

            d_r2 = abs(rad - 98.0)
            if d_r2 < 2.0:
                if (132 <= ang <= 228) or (ang >= 312 or ang <= 48):
                    r, g, b = add_glow((r, g, b), hud_col, smoothstep(2.0, 0.4, d_r2) * 0.42)

            d_r3 = abs(rad - 91.0)
            if d_r3 < 1.1:
                r, g, b = add_glow((r, g, b), hud_col, (1.0 - d_r3 / 1.1) * 0.30)

            if 84.0 <= rad <= 89.5:
                if (125 <= ang <= 235) or (ang >= 305 or ang <= 55):
                    rem = ang % 4.0
                    dist_ang = min(rem, 4.0 - rem) * (rad * 0.01745)
                    is_major = (min(ang % 16.0, 16.0 - (ang % 16.0)) < 0.8)
                    max_tick_r = 89.2 if is_major else 87.5
                    if rad <= max_tick_r and dist_ang < 0.9:
                        r, g, b = add_glow((r, g, b), hud_col, (1.0 - dist_ang / 0.9) * (0.48 if is_major else 0.25))

            d_r5 = abs(rad - 80.0)
            if d_r5 < 1.5:
                if (148 <= ang <= 212) or (ang >= 328 or ang <= 32):
                    r, g, b = add_glow((r, g, b), (0, 210, 255), smoothstep(1.5, 0.2, d_r5) * 0.32)

            pixels[x, y] = (r, g, b)

    draw = ImageDraw.Draw(img, "RGBA")

    # Binary Matrix Rain
    random.seed(42)
    font_tiny = ImageFont.load_default()
    binary_cols = [14, 24, 34, 44, 272, 282, 292, 302]
    for bx in binary_cols:
        for by in range(26, 204, 10):
            if random.random() < 0.62:
                bit = "1" if random.random() < 0.5 else "0"
                dist_y = abs(by - 115) / 95.0
                alpha = int(clamp((1.0 - dist_y) * random.randint(40, 115), 15, 115))
                b_col = (255, 90, 70, alpha) if is_err else ((255, 220, 80, alpha) if is_think and random.random() < 0.3 else (0, 210, 255, alpha))
                draw.text((bx, by), bit, fill=b_col, font=font_tiny)

    # Smooth Bokeh Particles
    bokeh_list = [
        (46, 62, 2.8), (64, 40, 1.8), (32, 118, 2.2),
        (54, 176, 2.6), (76, 194, 1.6), (266, 50, 2.8),
        (286, 86, 2.0), (274, 146, 3.2), (256, 188, 2.2),
        (104, 28, 1.8), (218, 30, 2.2), (86, 166, 1.5),
        (98, 52, 1.5), (226, 54, 1.8),
    ]
    for px, py, pr in bokeh_list:
        p_col = (255, 100, 80) if is_err else ((255, 220, 90) if (is_think or is_succ) and (int(px) % 2 == 0) else (130, 235, 255))
        draw_sdf_disc(pixels, px, py, pr, (255, 255, 255), p_col, glow_col=hud_col, glow_r=pr * 2.8)

    # Keep y_off gentle (-7 for approval so antenna + radio rings stay 100% visible!)
    y_off = -7.0 if is_appr else (-4.0 if is_succ else 0.0)

    if not is_appr:
        for y in range(196, 222):
            for x in range(100, 220):
                dx = (x - 160.0) / 52.0
                dy = (y - 209.0) / 8.0
                d = math.hypot(dx, dy)
                if d < 1.0:
                    sh = (1.0 - d * d) * 0.68
                    pixels[x, y] = mix_color(pixels[x, y], (1, 4, 12), sh)

    head_cx, head_cy = 160.0, 91.0 + y_off
    torso_cx, torso_cy = 160.0, 164.0 + y_off

    # Arms
    if is_succ:
        # Both arms raised in celebration! \o/
        draw_sdf_capsule(pixels, 114, 146 + y_off, 92, 126 + y_off, 9.0, 10.0, "armor")
        draw_sdf_capsule(pixels, 90, 124 + y_off, 78, 98 + y_off, 9.5, 8.5, "armor")
        draw_sdf_capsule(pixels, 76, 93 + y_off, 76, 93 + y_off, 7.0, 7.0, "dark_joint")
        for fx, fy in [(68, 84), (73, 81), (78, 81), (83, 84)]:
            draw_sdf_capsule(pixels, 76, 91 + y_off, fx, fy + y_off, 2.6, 2.1, "armor")

        draw_sdf_capsule(pixels, 206, 146 + y_off, 228, 126 + y_off, 9.0, 10.0, "armor")
        draw_sdf_capsule(pixels, 230, 124 + y_off, 242, 98 + y_off, 9.5, 8.5, "armor")
        draw_sdf_capsule(pixels, 244, 93 + y_off, 244, 93 + y_off, 7.0, 7.0, "dark_joint")
        for fx, fy in [(237, 84), (242, 81), (247, 81), (252, 84)]:
            draw_sdf_capsule(pixels, 244, 91 + y_off, fx, fy + y_off, 2.6, 2.1, "armor")
    else:
        wave_angle = 12.0 if is_think else 0.0
        draw_waving_right_arm(pixels, 90.0, 131.0, wave_angle, y_off)

        # Left Arm
        draw_sdf_capsule(pixels, 206, 148 + y_off, 206, 148 + y_off, 9.5, 9.5, "dark_joint")
        draw_sdf_capsule(pixels, 209, 146 + y_off, 220, 156 + y_off, 11.2, 9.8, "armor")
        draw_sdf_disc(pixels, 217.5, 149.5 + y_off, 4.2, (255, 195, 60), (240, 120, 10), rim_col=(70, 45, 20))
        draw_sdf_capsule(pixels, 223, 164 + y_off, 223, 164 + y_off, 7.8, 7.8, "dark_joint")
        draw_sdf_capsule(pixels, 225, 168 + y_off, 229, 184 + y_off, 10.2, 8.4, "armor")
        draw_sdf_disc(pixels, 228.5, 174.0 + y_off, 3.5, (180, 255, 255), (0, 200, 255), rim_col=(30, 90, 140), glow_col=(0, 200, 255), glow_r=3.0)
        draw_sdf_capsule(pixels, 229, 192 + y_off, 229, 192 + y_off, 6.2, 6.2, "dark_joint")
        draw_sdf_capsule(pixels, 225, 194 + y_off, 224, 200 + y_off, 2.5, 2.0, "armor")
        draw_sdf_capsule(pixels, 230, 195 + y_off, 229, 202 + y_off, 2.5, 2.0, "armor")
        draw_sdf_capsule(pixels, 234, 193 + y_off, 234, 199 + y_off, 2.4, 1.9, "armor")

    # Wheels & Fenders
    for wx, side in [(126.0, -1.0), (194.0, 1.0)]:
        wy = 198.0 + y_off
        for y in range(max(0, int(wy - 14)), min(H - 1, int(wy + 15))):
            for x in range(int(wx - 13), int(wx + 14)):
                dx = x - wx
                dy = y - wy
                d_tire = sd_round_box(dx, dy, 9.5, 11.5, 4.5)
                if d_tire < 0.75:
                    cov = smoothstep(0.75, -0.55, d_tire)
                    shade = int(mix(20, 62, max(0.0, -dy / 12.0 + 0.5)))
                    col = (shade, shade + 6, shade + 14)
                    rim_dx = (dx - side * 4.2) / 3.8
                    rim_dy = dy / 8.5
                    d_rim = abs(math.hypot(rim_dx, rim_dy) - 1.0) * 4.5
                    if d_rim < 1.3:
                        col = mix_color(col, (0, 235, 255), smoothstep(1.3, 0.2, d_rim))
                    pixels[x, y] = mix_color(pixels[x, y], col, cov)
        draw_sdf_capsule(pixels, wx - side * 2, wy - 10, wx + side * 5, wy - 3, 7.5, 6.5, "armor")

    # Torso
    y_min_t = max(0, int(125 + y_off))
    y_max_t = min(H - 1, int(206 + y_off))
    for y in range(y_min_t, y_max_t):
        for x in range(105, 215):
            dy = y - torso_cy
            taper = 1.0 - max(0.0, (torso_cy - y) / 88.0) * 0.17
            rx = 46.5 * taper
            ry = 37.5
            dx = x - torso_cx
            d = sd_round_box(dx, dy, rx, ry, 27.5)
            if d < 0.75:
                cov = smoothstep(0.75, -0.55, d)
                nx = clamp(dx / (rx + 4.0), -0.95, 0.95)
                ny = clamp(dy / (ry + 4.0), -0.95, 0.95)
                col = armor_3d_color(nx, ny)

                seam_y = (154.0 + y_off) + (dx * dx) * 0.0035
                d_seam1 = abs(y - seam_y)
                if d_seam1 < 1.1:
                    col = mix_color(col, (82, 104, 134), smoothstep(1.1, 0.0, d_seam1) * 0.85)

                if y > seam_y:
                    side_seam_x = 26.5 + (y - seam_y) * 0.16
                    d_seam2 = abs(abs(dx) - side_seam_x)
                    if d_seam2 < 1.1:
                        col = mix_color(col, (92, 114, 144), smoothstep(1.1, 0.0, d_seam2) * 0.8)

                d_pad = sd_round_box(dx, dy - 26.0, 15.0, 6.5, 4.0)
                if d_pad < 0.8:
                    pad_col = mix_color((140, 162, 190), (195, 212, 232), max(0.0, -ny + 0.3))
                    if abs(d_pad) < 0.9:
                        pad_col = (85, 105, 132)
                    col = mix_color(col, pad_col, smoothstep(0.8, -0.4, d_pad))

                d_chest = sd_round_box(dx, dy + 20.0, 18.0, 5.8, 4.5)
                if d_chest < 0.75:
                    panel_col = mix_color((65, 82, 104), (105, 125, 148), clamp((dy + 25.0) / 10.0, 0.0, 1.0))
                    d_pill = sd_round_box(dx + 4.5, dy + 20.0, 9.5, 2.6, 2.2)
                    if d_pill < 1.8:
                        panel_col = add_glow(panel_col, (0, 220, 255), smoothstep(1.8, 0.0, d_pill) * 0.6)
                    if d_pill < 0.6:
                        panel_col = mix_color(panel_col, (160, 252, 255), smoothstep(0.6, -0.4, d_pill))
                    d_amb = sd_round_box(dx - 11.0, dy + 20.0, 2.8, 2.5, 1.5)
                    if d_amb < 0.6:
                        panel_col = mix_color(panel_col, (255, 175, 30), smoothstep(0.6, -0.4, d_amb))
                    col = mix_color(col, panel_col, smoothstep(0.75, -0.4, d_chest))

                pixels[x, y] = mix_color(pixels[x, y], col, cov)

    draw_sdf_disc(pixels, 131.5, 144.5 + y_off, 3.8, (180, 255, 255), (0, 210, 255), rim_col=(65, 90, 120), glow_col=(0, 215, 255), glow_r=3.0)
    draw_sdf_disc(pixels, 188.5, 144.5 + y_off, 4.2, (255, 205, 80), (240, 130, 10), rim_col=(60, 75, 95), glow_col=(255, 150, 20), glow_r=3.0)

    # Neck
    for y in range(int(127 + y_off), int(137 + y_off)):
        for x in range(132, 188):
            if 0 <= y < H:
                dx = (x - 160.0) / 26.0
                dy = (y - (132.0 + y_off)) / 4.5
                d = math.hypot(dx, dy) - 1.0
                if d < 0.15:
                    cov = smoothstep(0.15, -0.1, d)
                    col = mix_color((30, 42, 58), (72, 90, 114), 1.0 - abs(dx))
                    pixels[x, y] = mix_color(pixels[x, y], col, cov)

    # Antenna (Always visible!)
    ant_x, ant_y = 160.0, 23.0 + y_off
    for r_wave, max_al in [(15.5, 0.28), (10.8, 0.50), (6.5, 0.75)]:
        for y in range(max(0, int(ant_y - r_wave - 2)), min(H - 1, int(ant_y + r_wave + 2))):
            for x in range(int(ant_x - r_wave - 2), int(ant_x + r_wave + 2)):
                d_w = abs(math.hypot(x - ant_x, y - ant_y) - r_wave)
                if d_w < 1.2:
                    pixels[x, y] = add_glow(pixels[x, y], hud_col, (1.0 - d_w / 1.2) * max_al)
    draw_sdf_capsule(pixels, 160, 25 + y_off, 160, 39 + y_off, 1.8, 2.4, "armor")
    draw_sdf_capsule(pixels, 155, 42 + y_off, 165, 42 + y_off, 4.5, 4.5, "armor")
    draw_sdf_disc(pixels, ant_x, ant_y, 4.2, (255, 255, 255), hud_col, glow_col=hud_col, glow_r=6.0)

    # Ear Pods
    for ex, side in [(94.0, -1.0), (226.0, 1.0)]:
        ey = head_cy
        for y in range(max(0, int(ey - 21)), min(H - 1, int(ey + 22))):
            for x in range(int(ex - 9), int(ex + 10)):
                dx = x - ex
                dy = y - ey
                d_ear = sd_round_box(dx, dy, 6.8, 18.5, 5.5)
                if d_ear < 0.75:
                    cov = smoothstep(0.75, -0.55, d_ear)
                    lit = clamp(-dy / 18.0 * 0.4 + 0.5, 0.0, 1.0)
                    col = mix_color((85, 105, 130), (185, 205, 225), lit)
                    d_ring = abs(sd_round_box(dx - side * 1.5, dy, 3.2, 13.0, 2.5))
                    if d_ring < 1.1:
                        col = mix_color(col, hud_col, smoothstep(1.1, 0.1, d_ring))
                    pixels[x, y] = mix_color(pixels[x, y], col, cov)

    # Helmet & Visor
    y_min_h = max(0, int(head_cy - 48))
    y_max_h = min(H - 1, int(head_cy + 48))
    for y in range(y_min_h, y_max_h):
        for x in range(92, 228):
            dx = x - head_cx
            dy = y - head_cy
            top_taper = 1.0 - max(0.0, -dy / 45.0) * 0.06
            d_helmet = sd_round_box(dx / top_taper, dy, 63.0, 44.5, 31.5)
            if d_helmet < 0.75:
                cov = smoothstep(0.75, -0.55, d_helmet)
                nx = clamp(dx / 65.0, -0.96, 0.96)
                ny = clamp(dy / 47.0, -0.96, 0.96)

                d_visor = sd_round_box(dx, dy - 1.0, 51.0, 33.5, 22.0)

                if d_visor < -1.2:
                    edge_glow = clamp((d_visor + 11.0) / 9.8, 0.0, 1.0)
                    vr = int(mix(5, 12, edge_glow))
                    vg = int(mix(12, 46, edge_glow))
                    vb = int(mix(24, 84, edge_glow))

                    if dx > 8 and dy > 6 and (x % 2 == 0) and (y % 2 == 0):
                        vg = min(255, vg + 12)
                        vb = min(255, vb + 24)

                    v_col = (vr, vg, vb)

                    adx = abs(dx)
                    ex_local = adx - 25.0
                    ey_local = dy - 1.5
                    r_eye = math.hypot(ex_local, ey_local)

                    if is_succ:
                        d_arch_out = math.hypot(ex_local, ey_local - 3.0) - 13.5
                        d_arch_in  = math.hypot(ex_local, ey_local - 8.5) - 11.5
                        d_happy_eye = max(d_arch_out, -d_arch_in, ey_local - 4.0)
                        if d_happy_eye < 5.0:
                            v_col = add_glow(v_col, (0, 230, 255), smoothstep(5.0, 0.0, d_happy_eye) * 0.55)
                        if d_happy_eye < 0.7:
                            v_col = mix_color(v_col, (170, 255, 255), smoothstep(0.7, -0.5, d_happy_eye))

                        d_blush = math.hypot((adx - 36.0) / 1.3, dy - 11.0) - 5.5
                        if d_blush < 4.0:
                            v_col = add_glow(v_col, (255, 80, 150), smoothstep(4.0, -2.0, d_blush) * 0.55)

                    elif is_err:
                        d_x1, _ = sd_segment(ex_local, ey_local, -9.0, -9.0, 9.0, 9.0)
                        d_x2, _ = sd_segment(ex_local, ey_local, -9.0, 9.0, 9.0, -9.0)
                        d_x = min(d_x1, d_x2) - 2.2
                        if d_x < 5.0:
                            v_col = add_glow(v_col, (255, 60, 40), smoothstep(5.0, 0.0, d_x) * 0.65)
                        if d_x < 0.7:
                            v_col = mix_color(v_col, (255, 190, 170), smoothstep(0.7, -0.5, d_x))

                    else:
                        eye_glow_col = (255, 200, 30) if is_think else (0, 215, 255)
                        eye_core_col = (255, 245, 160) if is_think else (150, 252, 255)

                        if r_eye < 20.0:
                            bloom = smoothstep(20.0, 11.5, r_eye) * 0.52
                            v_col = add_glow(v_col, eye_glow_col, bloom)

                        d_outer = r_eye - 13.0
                        if d_outer < 0.7:
                            ring_cov = smoothstep(0.7, -0.5, d_outer)
                            v_col = mix_color(v_col, eye_core_col, ring_cov)

                        d_pupil = r_eye - 8.4
                        if d_pupil < 0.7:
                            p_cov = smoothstep(0.7, -0.5, d_pupil)
                            pupil_col = (8, 26, 52)

                            d_cres = abs(r_eye - 6.0)
                            if ey_local > 1.0 and d_cres < 1.8:
                                c_int = smoothstep(1.8, 0.0, d_cres) * smoothstep(1.0, 4.0, ey_local) * 0.75
                                pupil_col = add_glow(pupil_col, eye_glow_col, c_int)

                            real_ex = dx - (-25.0 if dx < 0 else 25.0)
                            d_spec1 = math.hypot(real_ex - 3.2, ey_local + 3.2) - 2.6
                            if d_spec1 < 0.7:
                                pupil_col = mix_color(pupil_col, (255, 255, 255), smoothstep(0.7, -0.4, d_spec1))

                            d_spec2 = math.hypot(real_ex + 3.5, ey_local - 3.2) - 1.2
                            if d_spec2 < 0.7:
                                pupil_col = mix_color(pupil_col, (190, 245, 255), smoothstep(0.7, -0.4, d_spec2))

                            v_col = mix_color(v_col, pupil_col, p_cov)

                    if is_think:
                        d_brow, _ = sd_segment(adx, dy, 16.0, -14.5, 33.0, -17.5)
                        d_brow -= 1.6
                    elif is_err:
                        d_brow, _ = sd_segment(adx, dy, 16.0, -18.0, 33.0, -14.0)
                        d_brow -= 1.6
                    else:
                        if 15.5 <= adx <= 34.5:
                            bx_norm = (adx - 25.0) / 9.5
                            by_curve = -18.0 + 3.2 * bx_norm * bx_norm
                            d_brow = abs(dy - by_curve) - 1.5
                        else:
                            end_x = 15.5 if adx < 15.5 else 34.5
                            d_brow = math.hypot(adx - end_x, dy - (-14.8)) - 1.5

                    brow_glow = (255, 80, 50) if is_err else ((255, 210, 40) if is_think else (0, 215, 255))
                    brow_core = (255, 190, 170) if is_err else ((255, 245, 160) if is_think else (155, 252, 255))
                    if d_brow < 4.0:
                        v_col = add_glow(v_col, brow_glow, smoothstep(4.0, 0.0, d_brow) * 0.45)
                    if d_brow < 0.7:
                        v_col = mix_color(v_col, brow_core, smoothstep(0.7, -0.4, d_brow))

                    if is_think:
                        if abs(dx) < 13.0:
                            wave_y = 12.5 + math.sin(dx * 0.55) * 2.5 * (1.0 - abs(dx) / 14.0)
                            d_mouth = abs(dy - wave_y) - 1.2
                        else:
                            d_mouth = 10.0
                    elif is_err:
                        if abs(dx) <= 8.5:
                            mx_norm = dx / 8.5
                            my_curve = 10.5 + 3.5 * mx_norm * mx_norm
                            d_mouth = abs(dy - my_curve) - 1.5
                        else:
                            end_x = -8.5 if dx < 0 else 8.5
                            d_mouth = math.hypot(dx - end_x, dy - 14.0) - 1.5
                    else:
                        if abs(dx) <= 9.5:
                            mx_norm = dx / 9.5
                            my_curve = 14.2 - 4.2 * mx_norm * mx_norm
                            d_mouth = abs(dy - my_curve) - 1.6
                        else:
                            end_x = -9.5 if dx < 0 else 9.5
                            d_mouth = math.hypot(dx - end_x, dy - 10.0) - 1.6

                    if d_mouth < 4.5:
                        v_col = add_glow(v_col, brow_glow, smoothstep(4.5, 0.0, d_mouth) * 0.50)
                    if d_mouth < 0.7:
                        v_col = mix_color(v_col, brow_core, smoothstep(0.7, -0.4, d_mouth))

                    sheen_coord = dx * 0.72 + dy * 1.05
                    if -38.0 < sheen_coord < -6.0:
                        sheen = (1.0 - abs(sheen_coord + 22.0) / 16.0) ** 1.5
                        v_col = add_glow(v_col, (32, 46, 62), sheen)

                    col = v_col

                elif d_visor < 1.5:
                    t_rim = smoothstep(-1.2, 1.5, d_visor)
                    visor_edge = (18, 56, 92)
                    bezel_col = mix_color((42, 54, 72), (175, 195, 218), max(0.0, -0.5*nx - 0.5*ny + 0.5))
                    col = mix_color(visor_edge, bezel_col, t_rim)
                else:
                    col = armor_3d_color(nx, ny)
                    if dy < -20 and abs(abs(dx) - 34.0) < 1.0:
                        col = mix_color(col, (95, 118, 146), smoothstep(1.0, 0.0, abs(abs(dx) - 34.0)) * 0.75)

                    d_corner = math.hypot(abs(dx) - 48.0, abs(dy - 1.0) - 26.5)
                    if d_corner < 5.5:
                        col = add_glow(col, (255, 145, 10), smoothstep(5.5, 0.0, d_corner) * 0.65)
                    if d_corner < 2.2:
                        col = mix_color(col, (255, 225, 110), smoothstep(2.2, 0.2, d_corner))

                pixels[x, y] = mix_color(pixels[x, y], col, cov)

    try:
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 9)
        font_md = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
        font_lg = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except Exception:
        font_sm = font_md = font_lg = ImageFont.load_default()

    if is_appr:
        # SDF Anti-Aliased Holographic Approval Console & Buttons (y: 136..236)
        for y in range(134, 237):
            for x in range(14, 306):
                d_box = sd_round_box(x - 160.0, y - 185.0, 144.0, 49.0, 12.0)
                if d_box < 0.8:
                    bg_p = pixels[x, y]
                    glass_col = mix_color(bg_p, (6, 18, 34), 0.85)
                    if d_box > -1.4:
                        glass_col = mix_color(glass_col, (0, 220, 255), smoothstep(-1.4, 0.0, d_box))
                    pixels[x, y] = mix_color(bg_p, glass_col, smoothstep(0.8, -0.5, d_box))

                # Button 1: APPROVE (x: 24..152, y: 188..226 -> center (88, 207), half (64, 19))
                d_b1 = sd_round_box(x - 88.0, y - 207.0, 64.0, 19.0, 9.0)
                if d_b1 < 0.8:
                    b1_col = mix_color((0, 140, 70), (20, 205, 110), clamp((226 - y) / 38.0, 0.0, 1.0))
                    if d_b1 > -1.5:
                        b1_col = mix_color(b1_col, (120, 255, 195), smoothstep(-1.5, 0.0, d_b1))
                    pixels[x, y] = mix_color(pixels[x, y], b1_col, smoothstep(0.8, -0.5, d_b1))

                # Button 2: DENY (x: 168..296, y: 188..226 -> center (232, 207), half (64, 19))
                d_b2 = sd_round_box(x - 232.0, y - 207.0, 64.0, 19.0, 9.0)
                if d_b2 < 0.8:
                    b2_col = mix_color((165, 25, 35), (230, 65, 70), clamp((226 - y) / 38.0, 0.0, 1.0))
                    if d_b2 > -1.5:
                        b2_col = mix_color(b2_col, (255, 150, 150), smoothstep(-1.5, 0.0, d_b2))
                    pixels[x, y] = mix_color(pixels[x, y], b2_col, smoothstep(0.8, -0.5, d_b2))

        draw.rounded_rectangle([26, 141, 294, 157], radius=5, fill=(225, 90, 20, 235))
        draw.text((160, 149), "PERMISSION REQUIRED", fill=(255, 255, 255, 255), font=font_sm, anchor="mm")
        draw.text((160, 172), "Deploy to Production?", fill=(255, 235, 90, 255), font=font_lg, anchor="mm")
        draw.text((88, 207), "APPROVE", fill=(255, 255, 255, 255), font=font_md, anchor="mm")
        draw.text((232, 207), "DENY", fill=(255, 255, 255, 255), font=font_md, anchor="mm")
    else:
        draw_sdf_disc(pixels, 17.0, 10.0, 3.0, (150, 255, 190), (0, 230, 90), glow_col=(0, 230, 90), glow_r=3.0)
        draw.text((25, 10), "ANTIGRAVITY BOT", fill=(130, 180, 220, 190), font=font_sm, anchor="lm")
        draw.text((306, 10), "BLE 5.0", fill=(0, 215, 255, 200), font=font_sm, anchor="rm")

        status_map = {
            "idle": "Antigravity Ready",
            "thinking": "Analyzing Codebase...",
            "success": "Task Complete! ^_^",
            "error": "Build Error Detected!",
        }
        label = status_map.get(state, "Antigravity Ready")
        for y in range(213, 237):
            for x in range(62, 258):
                d_pill = sd_round_box(x - 160.0, y - 224.5, 95.0, 10.5, 10.0)
                if d_pill < 0.8:
                    bg_p = pixels[x, y]
                    p_col = mix_color(bg_p, (6, 20, 38), 0.82)
                    if d_pill > -1.2:
                        p_col = mix_color(p_col, hud_col, smoothstep(-1.2, 0.0, d_pill) * 0.55)
                    pixels[x, y] = mix_color(bg_p, p_col, smoothstep(0.8, -0.5, d_pill))
        draw.text((160, 224), label, fill=(225, 245, 255, 255), font=font_md, anchor="mm")

    out_native = os.path.join(OUT_DIR, f"bot_v3_{state}.png")
    img.resize((W * 2, H * 2), Image.LANCZOS).save(out_native)
    return img

def main():
    states = ["idle", "thinking", "approval", "success", "error"]
    imgs = {}
    for st in states:
        imgs[st] = render_bot_state(st)
        print("Rendered V3 state:", st)

    S = 2
    cw, ch = W * S * 2 + 45, H * S * 2 + 110
    comp = Image.new("RGB", (cw, ch), (8, 12, 22))
    cdraw = ImageDraw.Draw(comp)
    try:
        f_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        f_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except Exception:
        f_title = f_sub = ImageFont.load_default()

    cdraw.text((cw // 2, 28), "Antigravity 3D Bot Companion — Multi-State Dynamic Engine (320x240)", fill=(0, 225, 255), font=f_title, anchor="mm")

    positions = [
        ("idle",     15,            55,            "1. IDLE (3D Robot + Waving Hand + Radar HUD + Binary Rain)"),
        ("thinking", W * S + 30,    55,            "2. THINKING (Amber Core + Neural Waveform Mouth + Data Scan)"),
        ("approval", 15,            H * S + 80,    "3. APPROVAL (Robot Projecting Holographic Touch Console)"),
        ("success",  W * S + 30,    H * S + 80,    "4. SUCCESS / TOUCH (Celebration Jump + Happy Arches & Blush)"),
    ]
    for st, px, py, title in positions:
        scaled = imgs[st].resize((W * S, H * S), Image.LANCZOS)
        cdraw.rounded_rectangle([px - 4, py - 4, px + W * S + 4, py + H * S + 4], radius=10, outline=(40, 70, 105), width=2)
        comp.paste(scaled, (px, py))
        cdraw.text((px + (W * S) // 2, py + H * S + 14), title, fill=(190, 220, 245), font=f_sub, anchor="mm")

    comp_path = os.path.join(OUT_DIR, "bot_v3_showcase.png")
    comp.save(comp_path)
    print("Saved V3 showcase:", comp_path)

if __name__ == "__main__":
    main()
