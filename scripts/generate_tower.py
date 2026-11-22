#!/usr/bin/env python3
"""
commit-tower: A dynamic pixel-art building visualization for GitHub profiles.
Builds automatically after your commits; demolishes floor-by-floor when inactive!
"""

import os
import sys
import math
import json
import random
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw

# Canvas dimensions
WIDTH = 260
HEIGHT = 320
SCALE = 2  # Scaled output: 520x640
TOTAL_FRAMES = 8
MAX_FLOORS = 12

# Color Palette
C_SKY_TOP = (10, 14, 26)
C_SKY_BOT = (22, 27, 46)
C_STARS = [(220, 235, 255), (170, 200, 255), (255, 245, 210)]
C_DISTANT_BLDGS = (18, 22, 38)
C_DISTANT_WIN = (35, 45, 70)

C_ROAD = (28, 33, 40)
C_ROAD_LINE = (210, 153, 34)
C_SIDEWALK = (45, 51, 59)
C_SIDEWALK_LINE = (55, 62, 71)

C_CONE_ORANGE = (247, 129, 102)
C_CONE_WHITE = (240, 246, 252)

C_BLDG_WALL = (31, 36, 44)
C_BLDG_EDGE = (48, 54, 61)
C_BLDG_LOBBY = (40, 46, 54)
C_CRANE_STEEL = (227, 179, 65)
C_CRANE_DARK = (150, 115, 30)
C_CABLE = (110, 118, 129)

# 3x5 Pixel Font
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
        # Graceful defaults
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

    # Check streak & inactivity
    reversed_days = list(reversed(days_list))
    today_commits = reversed_days[0]["contributionCount"] if reversed_days else 0

    streak = 0
    inactive_days = 0

    # If committed today or yesterday
    if today_commits > 0:
        for d in reversed_days:
            if d["contributionCount"] > 0:
                streak += 1
            else:
                break
        inactive_days = 0
        status = "CONSTRUCTING"
    else:
        # Inactive today; count how many consecutive days inactive
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


def draw_background(draw, frame_idx):
    # Twilight sky gradient
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        r = int(C_SKY_TOP[0] * (1 - ratio) + C_SKY_BOT[0] * ratio)
        g = int(C_SKY_TOP[1] * (1 - ratio) + C_SKY_BOT[1] * ratio)
        b = int(C_SKY_TOP[2] * (1 - ratio) + C_SKY_BOT[2] * ratio)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    # Stars with gentle twinkling
    star_positions = [
        (20, 48, 0), (55, 30, 1), (105, 52, 2), (185, 35, 0), (235, 50, 1),
        (35, 85, 2), (215, 95, 0), (75, 110, 1), (155, 125, 2), (18, 145, 0),
        (242, 135, 1), (92, 38, 2), (175, 75, 0), (28, 120, 1), (228, 110, 2)
    ]
    for x, y, color_idx in star_positions:
        twinkle = math.sin((frame_idx / TOTAL_FRAMES * 2 * math.pi) + (x * 0.15))
        if twinkle > 0.4:
            draw.point((x, y), fill=(255, 255, 255))
        elif twinkle > -0.3:
            draw.point((x, y), fill=C_STARS[color_idx])
        else:
            draw.point((x, y), fill=(60, 75, 110))

    # Crescent Moon in upper left
    mx, my = 28, 62
    draw.ellipse([mx, my, mx + 14, my + 14], fill=(255, 248, 220))
    draw.ellipse([mx + 4, my - 2, mx + 18, my + 12], fill=C_SKY_TOP)

    # Distant city skyline silhouettes
    bldgs = [
        (10, 175, 45, 260),
        (40, 195, 68, 260),
        (178, 185, 215, 260),
        (210, 165, 250, 260)
    ]
    for x1, y1, x2, y2 in bldgs:
        draw.rectangle([x1, y1, x2, y2], fill=C_DISTANT_BLDGS)
        for wy in range(y1 + 8, y2 - 10, 12):
            for wx in range(x1 + 6, x2 - 6, 8):
                if (wx + wy) % 7 == 0:
                    draw.point((wx, wy), fill=C_DISTANT_WIN)


def draw_ground(draw, frame_idx):
    y_ground = 260

    # Sidewalk with slab joints
    draw.rectangle([0, y_ground, WIDTH, y_ground + 14], fill=C_SIDEWALK)
    for x in range(0, WIDTH, 24):
        draw.line([(x, y_ground), (x, y_ground + 14)], fill=C_SIDEWALK_LINE, width=1)

    # Curb edge
    draw.line([(0, y_ground + 14), (WIDTH, y_ground + 14)], fill=(20, 24, 30), width=1)

    # Asphalt street
    draw.rectangle([0, y_ground + 15, WIDTH, HEIGHT], fill=C_ROAD)
    # Dashed road centerline
    dash_y = y_ground + 35
    for x in range(12, WIDTH, 32):
        draw.line([(x, dash_y), (x + 16, dash_y)], fill=C_ROAD_LINE, width=2)

    # Construction cones
    for cx in [52, 202]:
        draw.polygon([(cx + 4, y_ground + 2), (cx + 1, y_ground + 12), (cx + 7, y_ground + 12)], fill=C_CONE_ORANGE)
        draw.line([(cx + 2, y_ground + 7), (cx + 6, y_ground + 7)], fill=C_CONE_WHITE, width=1)
        draw.line([(cx, y_ground + 12), (cx + 8, y_ground + 12)], fill=C_CONE_ORANGE, width=1)

    # Street lamp at x=28
    lx = 28
    draw.line([(lx, y_ground - 45), (lx, y_ground + 2)], fill=(70, 75, 85), width=2)
    draw.line([(lx, y_ground - 45), (lx + 8, y_ground - 45)], fill=(70, 75, 85), width=2)
    draw.rectangle([lx + 6, y_ground - 44, lx + 12, y_ground - 40], fill=(255, 230, 130))
    draw.point((lx + 9, y_ground - 42), fill=(255, 255, 255))


def render_tower_frame(state, frame_idx):
    floors = max(1, min(MAX_FLOORS, state["floors"]))
    mode = state["status"]
    streak = state["current_streak"]
    inactive_days = state["inactive_days"]

    im = Image.new("RGB", (WIDTH, HEIGHT), C_SKY_TOP)
    draw = ImageDraw.Draw(im)

    draw_background(draw, frame_idx)

    # Building bounds
    bldg_w = 96
    bldg_x1 = (WIDTH - bldg_w) // 2
    bldg_x2 = bldg_x1 + bldg_w
    y_base = 260
    lobby_h = 24
    floor_h = 15

    # 1. Lobby Floor (Floor 1)
    y_lobby_top = y_base - lobby_h
    draw.rectangle([bldg_x1, y_lobby_top, bldg_x2, y_base], fill=C_BLDG_LOBBY, outline=C_BLDG_EDGE)
    # Marquee awning
    draw.rectangle([bldg_x1 + 24, y_lobby_top + 8, bldg_x2 - 24, y_lobby_top + 11], fill=(227, 179, 65))
    # Glass entrance doors
    draw.rectangle([bldg_x1 + 32, y_lobby_top + 12, bldg_x2 - 32, y_base], fill=(255, 215, 120))
    draw.line([(bldg_x1 + 48, y_lobby_top + 12), (bldg_x1 + 48, y_base)], fill=(60, 50, 30), width=1)
    # Lobby side windows
    draw.rectangle([bldg_x1 + 8, y_lobby_top + 6, bldg_x1 + 22, y_base - 4], fill=(70, 100, 130))
    draw.rectangle([bldg_x2 - 22, y_lobby_top + 6, bldg_x2 - 8, y_base - 4], fill=(70, 100, 130))
    # Marquee plaque
    draw.line([(bldg_x1 + 34, y_lobby_top + 4), (bldg_x2 - 34, y_lobby_top + 4)], fill=(227, 179, 65), width=2)

    # 2. Standard Floors (Floor 2 to N)
    curr_y = y_lobby_top
    for f in range(2, floors + 1):
        f_top = curr_y - floor_h
        f_bot = curr_y
        is_top_active = (f == floors)

        if is_top_active and mode == "DEMOLISHING":
            # Demolition top floor: cracked concrete, exposed rebar
            draw.rectangle([bldg_x1, f_top + 3, bldg_x2 - 14, f_bot], fill=(45, 40, 42), outline=C_BLDG_EDGE)
            # Jagged crumbled corner
            draw.polygon([
                (bldg_x2 - 14, f_bot),
                (bldg_x2 - 18, f_top + 5),
                (bldg_x2 - 8, f_top + 11),
                (bldg_x2 - 4, f_bot)
            ], fill=(35, 30, 32))
            # Structural rebar sticking out
            draw.line([(bldg_x2 - 12, f_top + 4), (bldg_x2 - 6, f_top - 2)], fill=(110, 115, 125), width=1)
            draw.line([(bldg_x2 - 16, f_top + 2), (bldg_x2 - 12, f_top - 4)], fill=(110, 115, 125), width=1)
            # Wall cracks
            draw.line([(bldg_x1 + 22, f_top + 3), (bldg_x1 + 34, f_bot - 2)], fill=(15, 15, 18), width=1)
            draw.line([(bldg_x1 + 52, f_top + 1), (bldg_x1 + 62, f_bot - 4)], fill=(15, 15, 18), width=1)
            # Hazard stripes
            for hx in range(bldg_x1 + 4, bldg_x2 - 24, 12):
                draw.line([(hx, f_bot - 2), (hx + 6, f_bot - 7)], fill=(240, 180, 40), width=2)
                draw.line([(hx + 6, f_bot - 2), (hx + 12, f_bot - 7)], fill=(20, 20, 20), width=2)
        elif is_top_active and mode == "CONSTRUCTING":
            # Construction top floor: steel I-beam frame & scaffolding
            draw.rectangle([bldg_x1, f_top, bldg_x2, f_bot], fill=(22, 27, 34), outline=C_BLDG_EDGE)
            draw.line([(bldg_x1, f_top), (bldg_x2, f_top)], fill=C_CRANE_STEEL, width=2)
            for gx in range(bldg_x1 + 12, bldg_x2, 18):
                draw.line([(gx, f_top), (gx, f_bot)], fill=C_CRANE_STEEL, width=2)
                draw.line([(gx - 12, f_top), (gx, f_bot)], fill=C_CRANE_DARK, width=1)
            # Scaffolding planks
            draw.rectangle([bldg_x1 + 14, f_bot - 3, bldg_x2 - 14, f_bot - 1], fill=(150, 105, 65))
        else:
            # Completed floor
            draw.rectangle([bldg_x1, f_top, bldg_x2, f_bot], fill=C_BLDG_WALL, outline=C_BLDG_EDGE)
            draw.line([(bldg_x1 - 2, f_top), (bldg_x2 + 2, f_top)], fill=(65, 72, 83), width=1)

            # 4 windows
            win_y1 = f_top + 3
            win_y2 = f_bot - 3
            wins = [
                (bldg_x1 + 8, bldg_x1 + 22),
                (bldg_x1 + 30, bldg_x1 + 44),
                (bldg_x1 + 52, bldg_x1 + 66),
                (bldg_x1 + 74, bldg_x1 + 88),
            ]
            for w_idx, (wx1, wx2) in enumerate(wins):
                seed = (f * 7 + w_idx * 13) % 10
                if seed in [0, 1, 2]:
                    # Warm office light
                    draw.rectangle([wx1, win_y1, wx2, win_y2], fill=(255, 224, 130))
                    draw.line([((wx1 + wx2) // 2, win_y1), ((wx1 + wx2) // 2, win_y2)], fill=(70, 60, 40))
                elif seed in [3, 4]:
                    # Dev screen / Server glow
                    draw.rectangle([wx1, win_y1, wx2, win_y2], fill=(88, 166, 255))
                    if (frame_idx + w_idx) % 2 == 0:
                        draw.line([(wx1 + 2, win_y2 - 2), (wx2 - 2, win_y2 - 2)], fill=(255, 255, 255))
                else:
                    # Dark night window
                    draw.rectangle([wx1, win_y1, wx2, win_y2], fill=(20, 24, 33))
                    draw.line([(wx1 + 2, win_y1 + 2), (wx1 + 6, win_y2 - 2)], fill=(35, 42, 55))

        curr_y = f_top

    roof_y = curr_y

    # 3. Machinery: Tower Crane OR Demolition Wrecking Ball
    if mode == "CONSTRUCTING":
        crane_x = bldg_x1 + 24
        crane_mast_h = 36
        crane_top_y = roof_y - crane_mast_h

        # Crane vertical mast
        draw.line([(crane_x, roof_y), (crane_x, crane_top_y)], fill=C_CRANE_STEEL, width=3)
        for my in range(crane_top_y + 4, roof_y, 6):
            draw.line([(crane_x - 3, my), (crane_x + 3, my)], fill=C_CRANE_DARK, width=1)

        # Horizontal jib arm
        jib_y = crane_top_y + 4
        draw.line([(crane_x - 18, jib_y), (crane_x + 48, jib_y)], fill=C_CRANE_STEEL, width=3)
        # Counterweight block
        draw.rectangle([crane_x - 22, jib_y - 2, crane_x - 14, jib_y + 6], fill=(70, 75, 85))

        # Peak & blinking aircraft hazard light
        draw.polygon([(crane_x, crane_top_y), (crane_x + 10, jib_y), (crane_x - 6, jib_y)], fill=C_CRANE_DARK)
        beacon_color = (248, 81, 73) if (frame_idx < 3) else (80, 25, 25)
        draw.rectangle([crane_x - 1, crane_top_y - 3, crane_x + 2, crane_top_y], fill=beacon_color)
        if frame_idx < 3:
            draw.point((crane_x, crane_top_y - 4), fill=(255, 180, 180))

        # Cable & swaying girder
        sway = int(round(math.sin(frame_idx / TOTAL_FRAMES * 2 * math.pi) * 3))
        hook_x = crane_x + 30 + sway
        hook_y = jib_y + 16
        draw.line([(crane_x + 30, jib_y), (hook_x, hook_y)], fill=C_CABLE, width=1)
        draw.rectangle([hook_x - 10, hook_y, hook_x + 10, hook_y + 3], fill=C_CRANE_STEEL)

        # Welding sparks bursting on roof
        spark_x = bldg_x2 - 18
        spark_y = roof_y
        if frame_idx in [1, 2, 4, 5]:
            draw.point((spark_x, spark_y), fill=(255, 255, 255))
            draw.point((spark_x - 1, spark_y - 2), fill=(255, 230, 80))
            draw.point((spark_x + 2, spark_y - 3), fill=(255, 160, 40))
            draw.point((spark_x + (frame_idx % 3), spark_y + 2), fill=(255, 240, 150))
            if frame_idx in [2, 5]:
                draw.point((spark_x - 3, spark_y - 1), fill=(255, 255, 200))
                draw.point((spark_x + 4, spark_y - 1), fill=(255, 200, 60))
    else:
        # DEMOLITION: Crane & Wrecking Ball
        crane_x = bldg_x1 - 10
        crane_top_y = roof_y - 10
        boom_start = (crane_x, roof_y + 20)
        boom_end = (crane_x + 26, crane_top_y)
        draw.line([boom_start, boom_end], fill=(180, 140, 40), width=3)
        draw.line([(boom_start[0], boom_start[1] - 8), (boom_end[0] - 6, boom_end[1] + 6)], fill=(120, 90, 25), width=1)

        # Pendulum swing
        swing_angle = math.sin(frame_idx / TOTAL_FRAMES * 2 * math.pi) * 0.45
        cable_len = 34
        ball_x = int(boom_end[0] + math.sin(swing_angle) * cable_len)
        ball_y = int(boom_end[1] + math.cos(swing_angle) * cable_len)
        draw.line([boom_end, (ball_x, ball_y)], fill=(100, 105, 115), width=1)

        # Wrecking ball
        draw.ellipse([ball_x - 5, ball_y - 5, ball_x + 5, ball_y + 5], fill=(65, 70, 80), outline=(90, 95, 105))
        draw.point((ball_x - 2, ball_y - 2), fill=(160, 165, 175))

        # Falling debris
        debris_y_offset = (frame_idx * 4) % 24
        draw.rectangle([bldg_x2 - 14, roof_y + debris_y_offset, bldg_x2 - 11, roof_y + debris_y_offset + 3], fill=(80, 85, 95))
        draw.point((bldg_x2 - 8, roof_y + 4 + debris_y_offset), fill=(140, 145, 155))

        # Dust puff
        if frame_idx in [3, 4, 5]:
            draw.ellipse([bldg_x2 - 20, roof_y - 6, bldg_x2 - 4, roof_y + 6], fill=(70, 75, 85))
            draw.point((bldg_x2 - 12, roof_y), fill=(110, 115, 125))

        # Amber caution beacon
        amber_on = (frame_idx % 2 == 0)
        beacon_color = (240, 180, 40) if amber_on else (90, 65, 15)
        draw.rectangle([boom_end[0] - 2, boom_end[1] - 4, boom_end[0] + 2, boom_end[1]], fill=beacon_color)

    # 4. Draw Ground
    draw_ground(draw, frame_idx)

    # 5. Retro HUD Header & Footer
    # Top HUD Bar
    draw.rectangle([8, 8, WIDTH - 8, 38], fill=(13, 17, 23), outline=(48, 54, 61))
    draw_pixel_text(draw, f"FLOOR {floors}", 16, 12, color=(255, 255, 255), scale=2)

    if streak > 0:
        streak_str = f"STREAK: {streak}D"
        streak_col = (210, 153, 34)
    else:
        streak_str = f"INACTIVE: {inactive_days}D"
        streak_col = (248, 81, 73)
    draw_pixel_text(draw, streak_str, 16, 26, color=streak_col, scale=1)

    # Status Pill on Right
    if mode == "CONSTRUCTING":
        badge_bg = (35, 134, 54)
        badge_txt = "[+1 BLD]"
    else:
        badge_bg = (218, 54, 51)
        badge_txt = "[-1 DEM]"

    draw.rectangle([WIDTH - 66, 14, WIDTH - 16, 32], fill=badge_bg)
    draw_pixel_text(draw, badge_txt, WIDTH - 60, 20, color=(255, 255, 255), scale=1)

    # Bottom Ticker
    draw.rectangle([8, HEIGHT - 20, WIDTH - 8, HEIGHT - 6], fill=(13, 17, 23), outline=(48, 54, 61))
    if mode == "CONSTRUCTING":
        ticker_msg = "COMMITS BUILD FLOORS * ACTIVE TODAY!"
        ticker_col = (88, 166, 255)
    else:
        ticker_msg = "INACTIVITY DEMOLISHES * COMMIT TO REBUILD"
        ticker_col = (247, 129, 102)
    draw_pixel_text(draw, ticker_msg, 14, HEIGHT - 16, color=ticker_col, scale=1)

    # Scale to high resolution using nearest neighbor for crisp pixel art
    return im.resize((WIDTH * SCALE, HEIGHT * SCALE), resample=Image.Resampling.NEAREST)


def generate_tower(output_dir="tower", username="dineshdev-21"):
    os.makedirs(output_dir, exist_ok=True)
    print(f"Fetching contribution data for {username}...")
    days = fetch_github_contributions(username)

    state = calculate_building_state(days)
    state["username"] = username
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    print("Building State:", json.dumps(state, indent=2))

    # Save state.json
    state_path = os.path.join(output_dir, "state.json")
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)

    # Render animated GIF frames
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

    # Save still PNG preview
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
