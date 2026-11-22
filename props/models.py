"""日本の路上小物 5 点のモデル定義。寸法は実物の一般的な値に合わせている。

各関数は Blender のオブジェクトのリストを返す。企業ロゴや実在の商標は入れない。
"""

from __future__ import annotations

import math

from .common import Builder, mat

# ---- 共通マテリアル ----


def _steel():
    return mat("GalvanizedSteel", (0.55, 0.57, 0.58), metallic=0.9, roughness=0.45)


def _dark():
    return mat("DarkPlastic", (0.04, 0.04, 0.045), roughness=0.6)


# ---- 自動販売機 ----
def vending_machine():
    """幅1.0 × 奥行0.7 × 高さ1.83 m の飲料自販機。"""
    b = Builder()
    body = mat("VM_Body", (0.90, 0.91, 0.92), roughness=0.35)
    door = mat("VM_Door", (0.05, 0.22, 0.55), roughness=0.3)
    window = mat("VM_Window", (0.95, 0.96, 0.98), roughness=0.4,
                 emission=(1.0, 0.98, 0.94), strength=1.6)
    shelf = mat("VM_Shelf", (0.75, 0.76, 0.78), metallic=0.6, roughness=0.4)
    button = mat("VM_Button", (0.1, 0.4, 0.9), roughness=0.3,
                 emission=(0.15, 0.5, 1.0), strength=2.5)
    panel = mat("VM_Panel", (0.72, 0.73, 0.75), metallic=0.7, roughness=0.35)
    drinks = [mat(f"VM_Drink_{n}", c, roughness=0.3) for n, c in (
        ("Red", (0.75, 0.06, 0.05)), ("Green", (0.08, 0.45, 0.15)),
        ("Yellow", (0.92, 0.72, 0.08)), ("Black", (0.05, 0.05, 0.06)),
        ("White", (0.92, 0.92, 0.9)), ("Orange", (0.92, 0.38, 0.05)))]

    front = -0.35
    b.box((1.0, 0.7, 1.78), (0, 0, 0.94), body, bevel=0.012)                  # 筐体
    for x in (-0.44, 0.44):
        for y in (-0.29, 0.29):
            b.box((0.07, 0.07, 0.05), (x, y, 0.025), _dark())                 # 脚
    b.box((0.97, 0.035, 1.72), (0, front - 0.0175, 0.94), door, bevel=0.006)  # 扉
    b.box((0.94, 0.01, 0.06), (0, front - 0.006, 0.065), _dark())             # 巾木

    # 商品見本の窓（3段）
    face = front - 0.035
    b.box((0.88, 0.012, 0.80), (0, face - 0.002, 1.36), window)
    b.box((0.90, 0.02, 0.02), (0, face - 0.01, 1.77), shelf)
    for row in range(3):
        base = 1.02 + row * 0.26
        b.box((0.88, 0.07, 0.035), (0, face - 0.035, base - 0.0175), shelf)   # 棚 兼 ボタン帯
        for i in range(10):
            x = -0.396 + i * 0.088
            tall = (row == 2 and i < 5)                                        # 上段左はペットボトル
            h, r = (0.19, 0.03) if tall else (0.12, 0.028)
            b.cyl(r, h, (x, face - 0.04, base + h / 2), drinks[(i + row * 2) % len(drinks)], verts=8)
            if tall:
                b.cyl(0.013, 0.02, (x, face - 0.04, base + h + 0.01), drinks[4], verts=6)
            b.box((0.045, 0.008, 0.016), (x, face - 0.073, base - 0.018), button)

    # 操作部（右）と広告面（左）
    b.box((0.30, 0.012, 0.30), (0.28, face - 0.004, 0.76), panel, bevel=0.004)
    b.box((0.012, 0.01, 0.05), (0.33, face - 0.012, 0.84), _dark())           # 硬貨投入口
    b.box((0.09, 0.01, 0.014), (0.23, face - 0.012, 0.84), _dark())           # 紙幣挿入口
    b.box((0.12, 0.01, 0.045), (0.25, face - 0.012, 0.76), _dark())           # 金額表示
    b.cyl(0.018, 0.02, (0.36, face - 0.014, 0.75), _dark(), verts=10, rot=(90, 0, 0))  # 返却レバー
    b.box((0.09, 0.03, 0.07), (0.33, face - 0.012, 0.66), _dark(), bevel=0.004)        # 釣り銭口
    b.box((0.52, 0.008, 0.30), (-0.18, face - 0.002, 0.76),
          mat("VM_AdPanel", (0.93, 0.93, 0.9), roughness=0.5))

    # 取り出し口
    b.box((0.72, 0.03, 0.22), (0, face - 0.004, 0.33), _dark(), bevel=0.006)
    b.box((0.66, 0.01, 0.16), (0, face - 0.022, 0.34),
          mat("VM_Flap", (0.25, 0.27, 0.3), roughness=0.15))
    # 鍵とヒンジ
    b.cyl(0.014, 0.012, (0.44, face - 0.004, 1.0), panel, verts=10, rot=(90, 0, 0))
    return [b.finish("vending_machine")]


# ---- 電柱 ----
def utility_pole():
    """地上高 10 m のコンクリート柱。腕金・がいし・柱上変圧器・街路灯付き（電線なし）。"""
    b = Builder()
    concrete = mat("Pole_Concrete", (0.56, 0.55, 0.52), roughness=0.9)
    ceramic = mat("Pole_Insulator", (0.88, 0.88, 0.86), roughness=0.25)
    tank = mat("Pole_Transformer", (0.52, 0.55, 0.56), roughness=0.5, metallic=0.3)
    yellow = mat("Pole_GuardYellow", (0.95, 0.75, 0.05), roughness=0.5)
    black = mat("Pole_GuardBlack", (0.03, 0.03, 0.03), roughness=0.5)
    lamp = mat("Pole_LampLens", (1.0, 1.0, 0.95), roughness=0.3,
               emission=(1.0, 0.97, 0.9), strength=4.0)
    steel = _steel()

    height, r0, r1 = 10.0, 0.16, 0.10

    def radius(z):
        return r0 + (r1 - r0) * z / height

    b.cyl(r0, height, (0, 0, height / 2), concrete, verts=16, r2=r1)
    b.cyl(r1 + 0.008, 0.03, (0, 0, height + 0.015), steel, verts=16)          # 頭部キャップ

    # 黄黒のしま（道路際の柱の根元）
    for i in range(4):
        z = 0.7 + i * 0.2
        b.cyl(radius(z) + 0.004, 0.2, (0, 0, z + 0.1), yellow if i % 2 == 0 else black,
              verts=16, r2=radius(z + 0.2) + 0.004, caps=False)
    b.box((0.09, 0.006, 0.16), (0, -radius(2.0) - 0.003, 2.0),
          mat("Pole_NumberPlate", (0.9, 0.9, 0.88), roughness=0.5))           # 電柱番号札

    # 足場ボルト
    for i in range(16):
        z = 1.9 + i * 0.45
        side = 1 if i % 2 == 0 else -1
        b.cyl(0.009, 0.16, (side * (radius(z) + 0.07), 0, z), steel, verts=6, rot=(0, 90, 0))

    # 高圧の腕金とピンがいし
    def crossarm(z, length, pins):
        y = -radius(z) - 0.04
        b.box((length, 0.075, 0.075), (0, y, z), steel)
        b.box((0.05, 0.2, 0.05), (0, -0.02, z - 0.06), steel)                 # バンド
        for x in pins:
            b.cyl(0.012, 0.1, (x, y, z + 0.085), steel, verts=6)
            b.cyl(0.055, 0.05, (x, y, z + 0.14), ceramic, verts=10, r2=0.04)
            b.cyl(0.04, 0.05, (x, y, z + 0.19), ceramic, verts=10, r2=0.022)

    crossarm(9.6, 1.8, (-0.8, -0.25, 0.8))
    crossarm(8.9, 1.5, (-0.65, 0.65))

    # 低圧のラック（縦並びの引留がいし）
    b.box((0.04, 0.03, 0.9), (0, -radius(7.0) - 0.02, 7.0), steel)
    for i in range(4):
        z = 6.67 + i * 0.22
        b.cyl(0.035, 0.06, (0, -radius(z) - 0.075, z), ceramic, verts=10)

    # 柱上変圧器
    ty, tz = radius(7.9) + 0.33, 7.9
    b.box((0.5, 0.12, 0.06), (0, radius(8.2) + 0.04, 8.2), steel)             # ハンガー
    b.box((0.5, 0.12, 0.06), (0, radius(7.6) + 0.04, 7.6), steel)
    b.cyl(0.27, 0.72, (0, ty, tz), tank, verts=16)
    b.cyl(0.28, 0.04, (0, ty, tz + 0.37), tank, verts=16)                     # ふた
    for x in (-0.12, 0.12):
        b.cyl(0.03, 0.14, (x, ty, tz + 0.46), ceramic, verts=8, r2=0.02)      # ブッシング
    b.box((0.16, 0.05, 0.2), (0, ty + 0.29, tz), tank)                        # 端子箱

    # 通信線のクロージャ
    b.cyl(0.07, 0.5, (0.32, -radius(5.9) - 0.1, 5.9), _dark(), verts=10, rot=(0, 90, 0))
    b.box((0.3, 0.04, 0.03), (0.16, -radius(5.9) - 0.05, 5.98), steel)

    # 街路灯
    arm_len, tilt = 0.95, 12
    az = 5.2
    ay = -radius(az) - arm_len / 2 * math.cos(math.radians(tilt))
    b.cyl(0.021, arm_len, (0, ay, az + arm_len / 2 * math.sin(math.radians(tilt))), steel,
          verts=8, rot=(90 + tilt, 0, 0))
    b.box((0.06, 0.2, 0.05), (0, -0.02, az - 0.03), steel)
    hy = -radius(az) - arm_len * math.cos(math.radians(tilt)) - 0.16
    hz = az + arm_len * math.sin(math.radians(tilt))
    b.box((0.16, 0.46, 0.07), (0, hy, hz), mat("Pole_LampBody", (0.8, 0.8, 0.8), roughness=0.4),
          bevel=0.01)
    b.box((0.12, 0.34, 0.012), (0, hy, hz - 0.04), lamp)
    return [b.finish("utility_pole")]


# ---- カーブミラー ----
def curve_mirror():
    """直径 800 mm の丸形道路反射鏡（一面鏡）。支柱の高さ 3.2 m。"""
    b = Builder()
    orange = mat("Mirror_Orange", (0.93, 0.33, 0.04), roughness=0.4)
    glass = mat("Mirror_Surface", (0.92, 0.94, 0.95), metallic=1.0, roughness=0.04)
    plate = mat("Mirror_Plate", (0.93, 0.93, 0.9), roughness=0.5)
    steel = _steel()

    pole_r, pole_h = 0.038, 3.2
    b.cyl(pole_r, pole_h, (0, 0, pole_h / 2), orange, verts=12)
    b.cyl(pole_r + 0.004, 0.02, (0, 0, pole_h + 0.01), orange, verts=12)      # キャップ
    b.cyl(0.07, 0.012, (0, 0, 0.006), steel, verts=12)                        # 根巻き

    # 鏡体（8 度下向き）。-Y が鏡面。
    cz, cy, tilt = 2.65, -0.17, 8
    rot = (tilt, 0, 0)
    c, s = math.cos(math.radians(tilt)), math.sin(math.radians(tilt))

    def at(dy, dz=0.0):
        """鏡の中心から見たローカル位置（傾きを考慮）。"""
        return (0, cy + dy * c - dz * s, cz + dy * s + dz * c)

    b.cyl(0.425, 0.035, at(0.0), orange, verts=24, rot=(90 + tilt, 0, 0))     # 枠
    b.cyl(0.41, 0.05, at(0.04), orange, verts=24, r2=0.30, rot=(-90 + tilt, 0, 0))  # 背面カバー
    b.dome(0.40, 0.045, at(-0.018), glass, rot=rot)                           # 鏡面
    # 取付金具
    b.box((0.06, 0.1, 0.3), (0, cy / 2 + 0.03, cz), steel)
    for dz in (-0.12, 0.12):
        b.box((0.1, 0.1, 0.03), (0, 0, cz + dz), steel)                       # 支柱バンド
    # 注意板（無地）
    b.box((0.4, 0.004, 0.12), (0, -pole_r - 0.012, 2.08), plate)
    b.box((0.05, 0.01, 0.05), (0, -pole_r - 0.005, 2.08), steel)
    return [b.finish("curve_mirror")]


# ---- ガードレール ----
def guardrail():
    """白い波形ガードレール 4 m 区間（支柱間隔 2 m）。X 方向に 4 m ずつ並べるとつながる。"""
    b = Builder()
    white = mat("Guardrail_White", (0.9, 0.9, 0.88), roughness=0.45, metallic=0.2)
    reflector = mat("Guardrail_Reflector", (0.95, 0.5, 0.05), roughness=0.2,
                    emission=(1.0, 0.45, 0.05), strength=0.6)
    steel = _steel()

    length, beam_z = 4.0, 0.60
    # 波形断面（y, z）。-Y が車道側で、山が 2 つ車道側へ出る。
    half = [(0.0, 0.175), (-0.012, 0.16), (-0.05, 0.135), (-0.07, 0.11), (-0.075, 0.0875),
            (-0.07, 0.065), (-0.05, 0.04), (-0.012, 0.015), (-0.006, 0.0)]
    profile = [(y, -z) for y, z in half] + [(y, z) for y, z in reversed(half[:-1])]
    b.extrude_profile(profile, 0.0, length, 0.004, (0, -0.02, beam_z), white)

    post_r, post_h = 0.057, 0.82
    for x in (1.0, 3.0):
        y = post_r + 0.035
        b.cyl(post_r, post_h, (x, y, post_h / 2), white, verts=12)
        b.cyl(post_r + 0.003, 0.015, (x, y, post_h + 0.0075), white, verts=12)   # キャップ
        b.box((0.1, 0.055, 0.2), (x, 0.01, beam_z), white)                        # ブラケット
        b.cyl(0.014, 0.012, (x, -0.03, beam_z), steel, verts=6, rot=(90, 0, 0))   # ボルト
        b.cyl(0.035, 0.012, (x, y - post_r - 0.004, post_h - 0.07), reflector,
              verts=12, rot=(90, 0, 0))                                           # 反射板
    return [b.finish("guardrail")]


# ---- 看板 ----
def signboard():
    """無地の電飾看板 2 種: ポール付き縦型袖看板（高さ 3.5 m）とスタンド看板（高さ 1.15 m）。

    表示面は SignFace マテリアルの四角形 1 枚（UV 0〜1）なので、画像を貼るだけで使える。
    """
    frame = mat("Sign_Frame", (0.12, 0.12, 0.13), roughness=0.4, metallic=0.5)
    face = mat("SignFace", (0.96, 0.96, 0.93), roughness=0.4,
               emission=(1.0, 0.98, 0.92), strength=1.2)
    steel = _steel()

    # 1) ポール付き袖看板
    b = Builder()
    b.cyl(0.045, 3.5, (0, 0, 1.75), steel, verts=12)
    b.cyl(0.049, 0.02, (0, 0, 3.51), steel, verts=12)
    b.box((0.22, 0.22, 0.012), (0, 0, 0.006), steel)                          # ベースプレート
    w, h, d = 0.6, 1.8, 0.16
    cx, cz = 0.045 + 0.06 + w / 2, 2.5
    b.box((w, d, h), (cx, 0, cz), frame, bevel=0.008)
    for z in (cz - 0.7, cz + 0.7):
        b.box((0.08, 0.05, 0.05), (0.075, 0, z), steel)                       # 取付アーム
    b.quad(w - 0.06, h - 0.06, (cx, -d / 2 - 0.002, cz), face)
    b.quad(w - 0.06, h - 0.06, (cx, d / 2 + 0.002, cz), face, rot=(0, 0, 180))
    pole_sign = b.finish("signboard_pole")

    # 2) スタンド看板（電飾・キャスター付き）
    b = Builder()
    ox = 1.5
    w, h, d = 0.45, 1.0, 0.26
    b.box((w + 0.06, d + 0.14, 0.05), (ox, 0, 0.075), frame, bevel=0.006)     # 台
    for x in (-0.2, 0.2):
        for y in (-0.15, 0.15):
            b.cyl(0.025, 0.03, (ox + x, y, 0.025), _dark(), verts=8, rot=(0, 90, 0))
    b.box((w, d, h), (ox, 0, 0.1 + h / 2), frame, bevel=0.01)
    b.box((0.2, 0.03, 0.03), (ox, 0, 0.1 + h + 0.03), frame)                  # 持ち手
    for x in (-0.09, 0.09):
        b.box((0.02, 0.03, 0.04), (ox + x, 0, 0.1 + h + 0.012), frame)
    fz = 0.1 + h / 2
    b.quad(w - 0.05, h - 0.05, (ox, -d / 2 - 0.002, fz), face)
    b.quad(w - 0.05, h - 0.05, (ox, d / 2 + 0.002, fz), face, rot=(0, 0, 180))
    stand_sign = b.finish("signboard_stand")
    return [pole_sign, stand_sign]


MODELS = {
    "vending_machine": vending_machine,
    "utility_pole": utility_pole,
    "curve_mirror": curve_mirror,
    "guardrail": guardrail,
    "signboard": signboard,
}
