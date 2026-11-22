#!/usr/bin/env python3
"""
The Commit Tower: Dynamic Pixel-Art Skyscraper & Demolition Engine for GitHub Profiles.
Builds automatically after your commits; demolishes floor-by-floor when inactive!
"""

import os
import sys
import math
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from PIL import Image, ImageDraw

WIDTH = 380
HEIGHT = 250
SCALE = 2  # 760 x 500 High-Definition Retro Pixel Art
TOTAL_FRAMES = 8
MAX_FLOORS = 12

# Custom 3x5 Bitmap Pixel Font (100% portable, zero system font dependencies)
FONT_3x5 = {
    '0': ['111','101','101','101','111'], '1': ['010','110','010','010','111'],
    '2': ['111','001','111','100','111'], '3': ['111','001','111','001','111'],
    '4': ['101','101','111','001','001'], '5': ['111','100','111','001','111'],
    '6': ['111','100','111','101','111'], '7': ['111','001','010','010','010'],
    '8': ['111','101','111','101','111'], '9': ['111','101','111','001','111'],
    ' ': ['000','000','000','000','000'], 'A': ['010','101','111','101','101'],
    'B': ['110','101','110','101','110'], 'C': ['011','100','100','100','011'],
    'D': ['110','101','101','101','110'], 'E': ['111','100','110','100','111'],
    'F': ['111','100','110','100','100'], 'G': ['011','100','101','101','011'],
    'H': ['101','101','111','101','101'], 'I': ['111','010','010','010','111'],
    'J': ['001','001','001','101','010'], 'K': ['101','110','100','110','101'],
    'L': ['100','100','100','100','111'], 'M': ['101','111','101','101','101'],
    'N': ['101','111','111','101','101'], 'O': ['010','101','101','101','010'],
    'P': ['110','101','110','100','100'], 'Q': ['010','101','101','111','011'],
    'R': ['110','101','110','110','101'], 'S': ['011','100','010','001','110'],
    'T': ['111','010','010','010','010'], 'U': ['101','101','101','101','111'],
    'V': ['101','101','101','101','010'], 'W': ['101','101','101','111','101'],
    'X': ['101','101','010','101','101'], 'Y': ['101','101','010','010','010'],
    'Z': ['111','001','010','100','111'], '-': ['000','000','111','000','000'],
    '+': ['000','010','111','010','000'], ':': ['000','010','000','010','000'],
    '!': ['010','010','010','000','010'], '/': ['001','001','010','100','100'],
    '[': ['110','100','100','100','110'], ']': ['011','001','001','001','011'],
    '.': ['000','000','000','000','010'], '*': ['000','101','010','101','000'],
    '#': ['010','111','010','111','010'], '<': ['001','010','100','010','001'],
    '>': ['100','010','001','010','100'], ',': ['000','000','000','010','100'],
    '(': ['010','100','100','100','010'], ')': ['010','001','001','001','010'],
}

def draw_pixel_text(draw, text, x, y, color=(255, 255, 255), scale=1):
    cx = x
    for ch in str(text).upper():
        glyph = FONT_3x5.get(ch, FONT_3x5[' '])
        for r, row in enumerate(glyph):
            for c, bit in enumerate(row):
                if bit == '1':
                    if scale == 1:
                        draw.point((cx + c, y + r), fill=color)
                    else:
                        draw.rectangle(
                            [cx + c * scale, y + r * scale, cx + (c + 1) * scale - 1, y + (r + 1) * scale - 1],
                            fill=color
                        )
        cx += (3 + 1) * scale
    return cx


def fetch_github_contributions(username, token=None):
    """Fetch user's contribution history using GraphQL API."""
    if not token:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """
    headers = {
        "User-Agent": "commit-tower",
        "Content-Type": "application/json"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": {"login": username}}).encode("utf-8"),
        headers=headers
    )

    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.load(resp)
            if "errors" in data:
                print("GraphQL errors:", data["errors"], file=sys.stderr)
                return None
            cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
            days = []
            for w in cal["weeks"]:
                for d in w["contributionDays"]:
                    days.append(d)
            return days
    except Exception as e:
        print("Failed to fetch contributions via GraphQL:", e, file=sys.stderr)
        return None


def calculate_building_state(days_list):
    """
    Simulate building construction and demolition from daily contributions.
    Rule:
      Active day (>0 commits): +1 floor (or +2 if >=4 commits). Max 12 floors.
      Inactive day (0 commits): -1 floor. Min 1 floor (foundation lobby).
    """
    if not days_list:
        return {
            "floors": 4,
            "status": "CONSTRUCTING",
            "current_streak": 2,
            "inactive_days": 0,
            "today_commits": 1,
            "total_recent_commits": 10
        }

    # Simulate past 30 days
    recent = days_list[-30:]
    floors = 1
    for d in recent:
        count = d["contributionCount"]
        if count > 0:
            floors = min(MAX_FLOORS, floors + (2 if count >= 4 else 1))
        else:
            floors = max(1, floors - 1)

    reversed_days = list(reversed(days_list))
    today_commits = reversed_days[0]["contributionCount"] if reversed_days else 0

    streak = 0
    inactive_days = 0

    if today_commits > 0:
        for d in reversed_days:
            if d["contributionCount"] > 0:
                streak += 1
            else:
                break
        inactive_days = 0
        status = "CONSTRUCTING"
    else:
        for d in reversed_days:
            if d["contributionCount"] == 0:
                inactive_days += 1
            else:
                break
        streak = 0
        status = "DEMOLISHING"

    total_recent = sum(d["contributionCount"] for d in recent)

    return {
        "floors": floors,
        "status": status,
        "current_streak": streak,
        "inactive_days": inactive_days,
        "today_commits": today_commits,
        "total_recent_commits": total_recent
    }


def render_tower_frame(state, frame_idx):
    floors = max(1, min(MAX_FLOORS, state["floors"]))
    mode = state["status"]
    streak = state["current_streak"]
    inactive_days = state["inactive_days"]

    im = Image.new("RGB", (WIDTH, HEIGHT), (15, 18, 30))
    draw = ImageDraw.Draw(im)

    # 1. Sunset / Twilight Sky Gradient
    y_ground = 195
    for y in range(y_ground):
        t = y / y_ground
        if t < 0.35:
            p = t / 0.35
            r = int(18 * (1 - p) + 38 * p)
            g = int(20 * (1 - p) + 26 * p)
            b = int(45 * (1 - p) + 68 * p)
        elif t < 0.7:
            p = (t - 0.35) / 0.35
            r = int(38 * (1 - p) + 98 * p)
            g = int(26 * (1 - p) + 38 * p)
            b = int(68 * (1 - p) + 78 * p)
        else:
            p = (t - 0.7) / 0.3
            r = int(98 * (1 - p) + 185 * p)
            g = int(38 * (1 - p) + 85 * p)
            b = int(78 * (1 - p) + 68 * p)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    # Stars in upper sky
    stars = [
        (18, 22), (45, 15), (82, 35), (145, 20), (210, 25), (280, 18), (340, 28),
        (30, 48), (95, 55), (175, 42), (255, 48), (320, 52), (355, 38)
    ]
    for sx, sy in stars:
        tw = math.sin((frame_idx / TOTAL_FRAMES * 2 * math.pi) + (sx * 0.1))
        if tw > 0.3:
            draw.point((sx, sy), fill=(255, 255, 255))
        elif tw > -0.3:
            draw.point((sx, sy), fill=(255, 240, 200))
        else:
            draw.point((sx, sy), fill=(120, 100, 140))

    # Glowing Crescent Moon
    mx, my = 320, 32
    draw.ellipse([mx, my, mx + 16, my + 16], fill=(255, 245, 215))
    draw.ellipse([mx + 5, my - 2, mx + 20, my + 14], fill=(30, 24, 52))

    # Distant Silhouette Cityline at Horizon
    far_skyline = [
        (0, 155, 35), (25, 145, 40), (55, 160, 30), (75, 150, 45),
        (260, 152, 38), (288, 142, 45), (322, 158, 35), (348, 148, 40)
    ]
    for fx, fy, fw in far_skyline:
        draw.rectangle([fx, fy, fx + fw, y_ground], fill=(42, 22, 50))
        for r_y in range(fy + 6, y_ground - 8, 10):
            for r_x in range(fx + 4, fx + fw - 4, 6):
                if (r_x + r_y) % 5 == 0:
                    draw.point((r_x, r_y), fill=(140, 65, 75))

    # 2. Ground & Construction Site
    # Soil/Gravel lot
    draw.rectangle([0, y_ground, WIDTH, y_ground + 22], fill=(48, 38, 42))
    # Concrete pavement slab under building
    draw.rectangle([80, y_ground, 260, y_ground + 10], fill=(70, 72, 82))
    draw.line([(80, y_ground), (260, y_ground)], fill=(95, 98, 110), width=1)

    # Road curb & Asphalt
    draw.rectangle([0, y_ground + 22, WIDTH, HEIGHT], fill=(26, 28, 34))
    draw.line([(0, y_ground + 22), (WIDTH, y_ground + 22)], fill=(55, 58, 68), width=1)
    for rx in range(15, WIDTH, 36):
        draw.line([(rx, y_ground + 38), (rx + 18, y_ground + 38)], fill=(230, 175, 45), width=2)

    # Left: Construction Office Trailer
    draw.rectangle([18, y_ground - 26, 68, y_ground], fill=(52, 60, 75), outline=(35, 42, 54))
    draw.rectangle([16, y_ground - 28, 70, y_ground - 25], fill=(85, 95, 115))
    draw.rectangle([24, y_ground - 18, 34, y_ground], fill=(75, 85, 105))
    draw.rectangle([42, y_ground - 22, 60, y_ground - 8], fill=(255, 215, 120))
    draw.line([(51, y_ground - 22), (51, y_ground - 8)], fill=(52, 60, 75), width=1)
    draw.line([(62, y_ground - 38), (62, y_ground - 28)], fill=(120, 125, 135), width=1)
    draw.point((62, y_ground - 39), fill=(255, 80, 80) if (frame_idx % 2 == 0) else (100, 30, 30))

    # Pallet of Red Bricks
    draw.rectangle([75, y_ground - 8, 92, y_ground], fill=(165, 62, 50))
    for by in range(y_ground - 7, y_ground, 3):
        draw.line([(75, by), (92, by)], fill=(130, 45, 35), width=1)

    # Right: Generator & Traffic Cones
    draw.rectangle([270, y_ground - 14, 292, y_ground], fill=(230, 160, 40), outline=(160, 105, 20))
    draw.rectangle([274, y_ground - 11, 282, y_ground - 5], fill=(30, 30, 35))
    for cx in [98, 255, 305]:
        draw.polygon([(cx + 4, y_ground - 12), (cx + 1, y_ground), (cx + 7, y_ground)], fill=(245, 105, 55))
        draw.line([(cx + 2, y_ground - 6), (cx + 6, y_ground - 6)], fill=(255, 255, 255), width=1)
        draw.line([(cx, y_ground), (cx + 8, y_ground)], fill=(245, 105, 55), width=1)

    # Street Lamp on right
    lx = 345
    draw.line([(lx, y_ground - 55), (lx, y_ground)], fill=(80, 85, 95), width=2)
    draw.line([(lx - 12, y_ground - 55), (lx, y_ground - 55)], fill=(80, 85, 95), width=2)
    draw.rectangle([lx - 14, y_ground - 54, lx - 8, y_ground - 50], fill=(255, 235, 140))
    draw.point((lx - 11, y_ground - 52), fill=(255, 255, 255))

    # 3. THE TOWER (Centered at X = 110 to 235, width = 125px)
    b_x1 = 110
    b_x2 = 235

    # --- LOBBY (Tier 1: Always Present) ---
    lobby_top = 150
    draw.rectangle([b_x1, lobby_top, b_x2, y_ground], fill=(38, 44, 58), outline=(58, 66, 84))
    draw.rectangle([b_x1, lobby_top, b_x1 + 8, y_ground], fill=(48, 55, 72))
    draw.rectangle([b_x2 - 8, lobby_top, b_x2, y_ground], fill=(48, 55, 72))
    # Grand Glass Entrance
    draw.rectangle([b_x1 + 42, lobby_top + 16, b_x2 - 42, y_ground], fill=(255, 225, 130))
    draw.line([((b_x1 + b_x2) // 2, lobby_top + 16), ((b_x1 + b_x2) // 2, y_ground)], fill=(65, 50, 30), width=1)
    # Golden Awning above entrance
    draw.rectangle([b_x1 + 36, lobby_top + 12, b_x2 - 36, lobby_top + 16], fill=(235, 180, 50))
    # Glowing Sign
    draw.rectangle([b_x1 + 25, lobby_top + 4, b_x2 - 25, lobby_top + 11], fill=(22, 26, 36), outline=(235, 180, 50))
    draw_pixel_text(draw, "DINESH TOWER", b_x1 + 29, lobby_top + 5, color=(255, 220, 100), scale=1)

    # Windows with interior silhouettes
    draw.rectangle([b_x1 + 14, lobby_top + 14, b_x1 + 34, y_ground - 6], fill=(75, 115, 150))
    draw.rectangle([b_x2 - 34, lobby_top + 14, b_x2 - 14, y_ground - 6], fill=(75, 115, 150))

    # Cute Little Worker outside the lobby door
    wx, wy = b_x1 + 32, y_ground - 14
    draw.rectangle([wx, wy, wx + 6, wy + 2], fill=(255, 210, 50))
    draw.line([(wx - 1, wy + 2), (wx + 7, wy + 2)], fill=(235, 180, 30), width=1)
    draw.rectangle([wx + 1, wy + 3, wx + 5, wy + 5], fill=(255, 205, 175))
    draw.rectangle([wx, wy + 6, wx + 6, wy + 10], fill=(245, 105, 30))
    draw.line([(wx + 2, wy + 7), (wx + 4, wy + 7)], fill=(255, 255, 255), width=1)
    draw.rectangle([wx + 1, wy + 11, wx + 5, wy + 14], fill=(45, 65, 95))

    curr_top = lobby_top

    # --- FLOOR 2: DEV SUITE (If floors >= 2) ---
    if floors >= 2:
        f2_top = 115
        draw.rectangle([b_x1 + 4, f2_top, b_x2 - 4, curr_top], fill=(34, 40, 52), outline=(52, 60, 76))
        draw.line([(b_x1 + 2, curr_top), (b_x2 - 2, curr_top)], fill=(85, 95, 115), width=2)
        for wx1 in [b_x1 + 12, b_x1 + 42, b_x1 + 72, b_x1 + 98]:
            wx2 = wx1 + 18
            draw.rectangle([wx1, f2_top + 6, wx2, curr_top - 6], fill=(255, 220, 110))
            draw.line([((wx1 + wx2) // 2, f2_top + 6), ((wx1 + wx2) // 2, curr_top - 6)], fill=(65, 55, 35))
        draw.rectangle([b_x1 + 6, curr_top - 4, b_x1 + 12, curr_top], fill=(40, 140, 70))
        curr_top = f2_top

    # --- FLOOR 3: CLOUD LAB (If floors >= 3) ---
    if floors >= 3:
        f3_top = 80
        draw.rectangle([b_x1 + 8, f3_top, b_x2 - 8, curr_top], fill=(28, 34, 45), outline=(48, 56, 70))
        draw.line([(b_x1 + 6, curr_top), (b_x2 - 6, curr_top)], fill=(85, 95, 115), width=2)
        for wx1 in [b_x1 + 18, b_x1 + 46, b_x1 + 74]:
            wx2 = wx1 + 18
            draw.rectangle([wx1, f3_top + 6, wx2, curr_top - 6], fill=(0, 210, 210))
            if (frame_idx + wx1) % 2 == 0:
                draw.point((wx1 + 4, curr_top - 10), fill=(255, 255, 255))
        curr_top = f3_top

    # --- FLOOR 4+: SKY PENTHOUSE (If floors >= 4) ---
    if floors >= 4:
        f4_top = 48
        draw.rectangle([b_x1 + 14, f4_top, b_x2 - 14, curr_top], fill=(24, 30, 40), outline=(42, 50, 64))
        draw.line([(b_x1 + 12, curr_top), (b_x2 - 12, curr_top)], fill=(85, 95, 115), width=2)
        draw.rectangle([b_x1 + 22, f4_top + 5, b_x2 - 22, curr_top - 5], fill=(255, 230, 140))
        curr_top = f4_top

    roof_y = curr_top

    # 4. ROOF MACHINERY: TOWER CRANE vs WRECKING BALL
    if mode == "CONSTRUCTING":
        crane_x = b_x1 + 35
        crane_mast_h = 42
        crane_top = roof_y - crane_mast_h

        draw.line([(crane_x, roof_y), (crane_x, crane_top)], fill=(255, 185, 30), width=3)
        for my in range(crane_top + 4, roof_y, 6):
            draw.line([(crane_x - 3, my), (crane_x + 3, my)], fill=(185, 125, 15), width=1)

        jib_y = crane_top + 5
        draw.line([(crane_x - 22, jib_y), (crane_x + 65, jib_y)], fill=(255, 185, 30), width=3)
        draw.rectangle([crane_x + 4, jib_y + 1, crane_x + 12, jib_y + 8], fill=(240, 140, 20))
        draw.point((crane_x + 8, jib_y + 4), fill=(120, 220, 255))
        draw.rectangle([crane_x - 26, jib_y - 2, crane_x - 16, jib_y + 7], fill=(65, 70, 80))

        # Beacon
        draw.polygon([(crane_x, crane_top), (crane_x + 10, jib_y), (crane_x - 8, jib_y)], fill=(185, 125, 15))
        beacon_color = (255, 50, 50) if (frame_idx < 4) else (80, 15, 15)
        draw.rectangle([crane_x - 1, crane_top - 4, crane_x + 2, crane_top], fill=beacon_color)
        if frame_idx < 4:
            draw.point((crane_x, crane_top - 5), fill=(255, 200, 200))

        # Swaying Girder
        sway = int(round(math.sin(frame_idx / TOTAL_FRAMES * 2 * math.pi) * 4))
        cable_x = crane_x + 40 + sway
        hook_y = jib_y + 20
        draw.line([(crane_x + 40, jib_y), (cable_x, hook_y)], fill=(120, 125, 135), width=1)
        draw.rectangle([cable_x - 14, hook_y, cable_x + 14, hook_y + 4], fill=(255, 185, 30))
        draw.line([(cable_x - 14, hook_y + 2), (cable_x + 14, hook_y + 2)], fill=(180, 120, 10), width=1)

        # Scaffolding & Welder on roof
        draw.rectangle([b_x2 - 35, roof_y - 12, b_x2 - 10, roof_y], fill=(30, 36, 46), outline=(255, 185, 30))
        draw.line([(b_x2 - 35, roof_y - 12), (b_x2 - 10, roof_y)], fill=(180, 120, 10), width=1)
        wx, wy = b_x2 - 28, roof_y - 8
        draw.rectangle([wx, wy, wx + 4, wy + 2], fill=(255, 210, 50))
        draw.rectangle([wx, wy + 3, wx + 4, wy + 7], fill=(245, 105, 30))

        # Welding sparks
        spark_x = b_x2 - 20
        spark_y = roof_y - 4
        if frame_idx in [1, 2, 4, 5, 7]:
            draw.point((spark_x, spark_y), fill=(255, 255, 255))
            draw.point((spark_x - 1, spark_y - 2), fill=(255, 235, 120))
            draw.point((spark_x + 2, spark_y - 3), fill=(255, 160, 40))
            draw.point((spark_x + 3, spark_y + 1), fill=(255, 255, 180))
            if frame_idx in [2, 5]:
                draw.point((spark_x - 3, spark_y - 1), fill=(255, 255, 255))
                draw.point((spark_x + 4, spark_y - 2), fill=(255, 200, 80))
    else:
        # DEMOLITION: Wrecking Ball
        crane_x = b_x1 - 15
        boom_start = (crane_x, y_ground - 20)
        boom_end = (crane_x + 45, roof_y - 15)

        draw.line([boom_start, boom_end], fill=(245, 130, 25), width=4)
        draw.line([(boom_start[0], boom_start[1] - 10), (boom_end[0] - 8, boom_end[1] + 8)], fill=(160, 80, 10), width=1)

        swing_angle = math.sin(frame_idx / TOTAL_FRAMES * 2 * math.pi) * 0.55
        cable_len = 38
        ball_x = int(boom_end[0] + math.sin(swing_angle) * cable_len)
        ball_y = int(boom_end[1] + math.cos(swing_angle) * cable_len)

        draw.line([boom_end, (ball_x, ball_y)], fill=(100, 105, 115), width=2)
        draw.ellipse([ball_x - 6, ball_y - 6, ball_x + 6, ball_y + 6], fill=(55, 60, 70), outline=(85, 90, 100))
        draw.point((ball_x - 2, ball_y - 2), fill=(185, 190, 200))

        # Crumbled corner
        draw.polygon([
            (b_x2 - 25, roof_y),
            (b_x2 - 18, roof_y + 8),
            (b_x2 - 10, roof_y + 4),
            (b_x2 - 6, roof_y + 15),
            (b_x2 - 28, roof_y + 12)
        ], fill=(22, 26, 34))
        draw.line([(b_x2 - 18, roof_y + 2), (b_x2 - 10, roof_y - 5)], fill=(120, 125, 135), width=1)
        draw.line([(b_x2 - 12, roof_y + 4), (b_x2 - 4, roof_y - 2)], fill=(120, 125, 135), width=1)

        # Debris
        debris_drop = (frame_idx * 5) % 30
        draw.rectangle([b_x2 - 16, roof_y + debris_drop, b_x2 - 12, roof_y + debris_drop + 3], fill=(85, 90, 100))
        draw.point((b_x2 - 8, roof_y + 6 + debris_drop), fill=(150, 155, 165))

        if frame_idx in [2, 3, 4, 5]:
            draw.ellipse([b_x2 - 28, roof_y - 8, b_x2 - 6, roof_y + 12], fill=(75, 80, 92))
            draw.point((b_x2 - 16, roof_y), fill=(120, 125, 135))

        for hx in range(b_x1 + 10, b_x2 - 30, 12):
            draw.line([(hx, roof_y - 2), (hx + 6, roof_y - 7)], fill=(245, 190, 40), width=2)
            draw.line([(hx + 6, roof_y - 2), (hx + 12, roof_y - 7)], fill=(20, 20, 20), width=2)

        amber_on = (frame_idx % 2 == 0)
        draw.rectangle([boom_end[0] - 2, boom_end[1] - 5, boom_end[0] + 2, boom_end[1]], fill=(255, 185, 30) if amber_on else (90, 60, 10))

    # 5. RETRO ARCADE HUD OVERLAY
    draw.rectangle([10, 8, WIDTH - 10, 36], fill=(18, 22, 32), outline=(50, 60, 80))
    draw_pixel_text(draw, f"FLOOR {floors}", 18, 12, color=(255, 255, 255), scale=2)
    streak_str = f"🔥 {streak}D STREAK" if streak > 0 else f"💤 {inactive_days}D INACTIVE"
    streak_col = (255, 190, 40) if streak > 0 else (255, 90, 80)
    draw_pixel_text(draw, streak_str, 18, 25, color=streak_col, scale=1)

    if mode == "CONSTRUCTING":
        badge_bg = (35, 145, 65)
        badge_txt = "🔨 UNDER CONSTRUCTION (+1)"
    else:
        badge_bg = (215, 50, 45)
        badge_txt = "⚠️ DEMOLITION ALERT (-1)"
    draw.rectangle([WIDTH - 150, 12, WIDTH - 16, 32], fill=badge_bg)
    draw_pixel_text(draw, badge_txt, WIDTH - 144, 18, color=(255, 255, 255), scale=1)

    # Bottom Ticker
    draw.rectangle([10, HEIGHT - 18, WIDTH - 10, HEIGHT - 6], fill=(18, 22, 32), outline=(50, 60, 80))
    if mode == "CONSTRUCTING":
        msg = "ACTIVE TODAY • CRANE ERECTING NEXT TIER • KEEP THE STREAK!"
        col = (100, 210, 255)
    else:
        msg = f"INACTIVE {inactive_days} DAYS • WRECKING BALL SWINGING • COMMIT TO REBUILD!"
        col = (255, 130, 100)
    draw_pixel_text(draw, msg, 14, HEIGHT - 14, color=col, scale=1)

    return im.resize((WIDTH * SCALE, HEIGHT * SCALE), resample=Image.Resampling.NEAREST)


def generate_tower(output_dir="tower", username="dineshdev-21"):
    os.makedirs(output_dir, exist_ok=True)
    print(f"Fetching contribution data for {username}...")
    days = fetch_github_contributions(username)

    state = calculate_building_state(days)
    state["username"] = username
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    print("Building State:", json.dumps(state, indent=2))

    state_path = os.path.join(output_dir, "state.json")
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)

    print(f"Rendering {TOTAL_FRAMES} frames ({state['status']}, Floor {state['floors']})...")
    frames = [render_tower_frame(state, i) for i in range(TOTAL_FRAMES)]

    gif_path = os.path.join(output_dir, "tower.gif")
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=120,
        loop=0,
        optimize=True
    )

    png_path = os.path.join(output_dir, "tower.png")
    frames[0].save(png_path)

    print(f"Generated: {gif_path} and {png_path}")
    return state


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate commit-tower profile graphic")
    parser.add_argument("--output-dir", default="tower", help="Directory to save outputs")
    parser.add_argument("--username", default="dineshdev-21", help="GitHub username")
    args = parser.parse_args()

    generate_tower(output_dir=args.output_dir, username=args.username)
