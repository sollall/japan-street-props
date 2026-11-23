"""小物モデル生成の共通部品（Blender の Python モジュール bpy を使う）。

向きの約束: 正面は -Y、上は +Z、原点は地面の中心。単位はメートル（実寸）。
"""

from __future__ import annotations

import math
from pathlib import Path

import bpy  # isort: skip（bmesh / mathutils より先に読み込む必要がある）
import bmesh
from mathutils import Euler, Matrix, Vector


def reset() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0


def mat(name: str, color, metallic: float = 0.0, roughness: float = 0.5,
        emission=None, strength: float = 1.0) -> bpy.types.Material:
    """名前でキャッシュされる Principled BSDF マテリアル。"""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    rgba = (*color, 1.0)
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission is not None:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
        bsdf.inputs["Emission Strength"].default_value = strength
    m.diffuse_color = rgba
    return m


class Builder:
    """部品を足していき、最後に1つのメッシュへまとめる。"""

    def __init__(self) -> None:
        self.parts: list[bpy.types.Object] = []

    # ---- 内部 ----
    def _emit(self, bm: bmesh.types.BMesh, material, loc, rot, smooth: bool) -> bpy.types.Object:
        if smooth:
            for f in bm.faces:
                f.smooth = True
        mesh = bpy.data.meshes.new("part")
        bm.to_mesh(mesh)
        bm.free()
        mesh.materials.append(material)
        obj = bpy.data.objects.new("part", mesh)
        obj.location = Vector(loc)
        if rot:
            obj.rotation_euler = Euler([math.radians(a) for a in rot])
        bpy.context.scene.collection.objects.link(obj)
        self.parts.append(obj)
        return obj

    # ---- 部品 ----
    def box(self, size, loc, material, bevel: float = 0.0, rot=None):
        """size=(幅X, 奥行Y, 高さZ)、loc は箱の中心。"""
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0, calc_uvs=True)
        bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
        if bevel > 0:
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=1,
                            affect="EDGES", profile=0.5)
        return self._emit(bm, material, loc, rot, smooth=False)

    def cyl(self, r: float, depth: float, loc, material, verts: int = 16,
            r2: float | None = None, rot=None, caps: bool = True):
        """Z 軸方向の円柱（r2 を渡すと上端の半径が変わる）。loc は中心。"""
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=caps, cap_tris=False, segments=verts,
                              radius1=r, radius2=r if r2 is None else r2,
                              depth=depth, calc_uvs=True)
        return self._emit(bm, material, loc, rot, smooth=True)

    def quad(self, w: float, h: float, loc, material, rot=None):
        """XZ 平面の板（-Y 向き）。UV は 0〜1 の全面。看板の表示面など。"""
        bm = bmesh.new()
        vs = [bm.verts.new(p) for p in ((-w / 2, 0, -h / 2), (w / 2, 0, -h / 2),
                                        (w / 2, 0, h / 2), (-w / 2, 0, h / 2))]
        face = bm.faces.new(vs)
        uv = bm.loops.layers.uv.new("UVMap")
        for loop, co in zip(face.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
            loop[uv].uv = co
        return self._emit(bm, material, loc, rot, smooth=False)

    def dome(self, r: float, bulge: float, loc, material, rot=None,
             segments: int = 24, rings: int = 4):
        """-Y 側へ膨らんだ円形の凸面（カーブミラーの鏡面）。"""
        bm = bmesh.new()
        curv = (r * r + bulge * bulge) / (2 * bulge)   # 球面の曲率半径
        center = bm.verts.new((0, -bulge, 0))
        prev = None
        for i in range(1, rings + 1):
            rr = r * i / rings
            y = -(math.sqrt(curv * curv - rr * rr) - (curv - bulge))
            ring = [bm.verts.new((rr * math.cos(2 * math.pi * s / segments), y,
                                  rr * math.sin(2 * math.pi * s / segments)))
                    for s in range(segments)]
            for s in range(segments):
                a, b = ring[s], ring[(s + 1) % segments]
                if prev is None:
                    bm.faces.new((center, a, b))
                else:
                    bm.faces.new((prev[s], a, b, prev[(s + 1) % segments]))
            prev = ring
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        return self._emit(bm, material, loc, rot, smooth=True)

    def extrude_profile(self, profile, x0: float, x1: float, thickness: float,
                        loc, material):
        """(y, z) の折れ線を X 方向へ押し出した板（厚みは +Y 側に付く）。"""
        bm = bmesh.new()
        n = len(profile)
        rows = []
        for x in (x0, x1):
            front = [bm.verts.new((x, y, z)) for y, z in profile]
            back = [bm.verts.new((x, y + thickness, z)) for y, z in profile]
            rows.append((front, back))
        (f0, b0), (f1, b1) = rows
        for i in range(n - 1):
            bm.faces.new((f0[i], f1[i], f1[i + 1], f0[i + 1]))        # 表
            bm.faces.new((b0[i + 1], b1[i + 1], b1[i], b0[i]))        # 裏
            bm.faces.new((f0[i + 1], b0[i + 1], b0[i], f0[i]))        # 端 x0
            bm.faces.new((f1[i], b1[i], b1[i + 1], f1[i + 1]))        # 端 x1
        bm.faces.new((f0[0], b0[0], b1[0], f1[0]))                    # 下の縁
        bm.faces.new((f1[-1], b1[-1], b0[-1], f0[-1]))                # 上の縁
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        return self._emit(bm, material, loc, None, smooth=True)

    # ---- 仕上げ ----
    def finish(self, name: str) -> bpy.types.Object:
        """全部品を1オブジェクトに結合する。原点はワールド原点（地面の中心）。"""
        bpy.context.view_layer.update()
        target = self.parts[0]
        with bpy.context.temp_override(active_object=target, object=target,
                                       selected_objects=self.parts,
                                       selected_editable_objects=self.parts):
            bpy.ops.object.join()
        mesh = target.data
        mesh.transform(target.matrix_world)
        target.matrix_world = Matrix.Identity(4)
        mesh.set_sharp_from_angle(angle=math.radians(35))
        mesh.update()
        target.name = name
        mesh.name = name
        self.parts = []
        return target


def triangle_count(objects) -> int:
    return sum(len(p.vertices) - 2 for o in objects for p in o.data.polygons)


def bounds(objects) -> tuple[Vector, Vector]:
    pts = [o.matrix_world @ Vector(c) for o in objects for c in o.bound_box]
    lo = Vector(min(p[i] for p in pts) for i in range(3))
    hi = Vector(max(p[i] for p in pts) for i in range(3))
    return lo, hi


# ---- 書き出し ----
def export_all(objects, out_dir: Path, stem: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out_dir / f"{stem}.blend"), compress=True,
                                check_existing=False)
    for stale in out_dir.glob("*.blend1"):
        stale.unlink()
    bpy.ops.export_scene.fbx(filepath=str(out_dir / f"{stem}.fbx"), object_types={"MESH"},
                             apply_scale_options="FBX_SCALE_UNITS", mesh_smooth_type="EDGE",
                             bake_anim=False)
    bpy.ops.export_scene.gltf(filepath=str(out_dir / f"{stem}.glb"), export_format="GLB",
                              export_apply=True, export_yup=True)


# ---- プレビュー画像 ----
VIEWS = {
    #  名前: (カメラの方向, 平行投影か)
    "front": (Vector((0, -1, 0)), True),
    "side": (Vector((1, 0, 0)), True),
    "top": (Vector((0, 0, 1)), True),
    "perspective": (Vector((0.62, -1.0, 0.42)), False),
}


def render_previews(objects, out_dir: Path, size: int = 1024, samples: int = 48) -> None:
    """正面・側面・上面・斜めの4枚を描く。保存・書き出しの後に呼ぶこと（床や照明を足すため）。"""
    import addon_utils

    addon_utils.enable("cycles")
    out_dir.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x = scene.render.resolution_y = size
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.compression = 100
    scene.view_settings.view_transform = "Standard"

    # 背景は明るく見せつつ、モデルを照らす環境光は白飛びしない強さに抑える
    world = bpy.data.worlds.new("PreviewWorld")
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    bg.inputs["Color"].default_value = (0.80, 0.84, 0.90, 1)
    path = nt.nodes.new("ShaderNodeLightPath")
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.inputs["To Min"].default_value = 0.45     # 照明としての強さ
    ramp.inputs["To Max"].default_value = 1.0      # カメラから直接見える背景の強さ
    nt.links.new(path.outputs["Is Camera Ray"], ramp.inputs["Value"])
    nt.links.new(ramp.outputs["Result"], bg.inputs["Strength"])
    scene.world = world

    sun = bpy.data.objects.new("PreviewSun", bpy.data.lights.new("PreviewSun", "SUN"))
    sun.data.energy = 2.0
    sun.data.angle = math.radians(4)
    sun.rotation_euler = Euler((math.radians(52), 0, math.radians(28)))
    scene.collection.objects.link(sun)

    lo, hi = bounds(objects)
    center = (lo + hi) / 2
    dims = hi - lo
    radius = dims.length / 2

    floor_mesh = bpy.data.meshes.new("PreviewFloor")
    s = max(60.0, radius * 30)
    floor_mesh.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    floor_mesh.materials.append(mat("PreviewFloor", (0.80, 0.81, 0.83), roughness=0.9))
    floor = bpy.data.objects.new("PreviewFloor", floor_mesh)
    scene.collection.objects.link(floor)

    cam_data = bpy.data.cameras.new("PreviewCam")
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam_data.clip_end = 500

    for name, (direction, ortho) in VIEWS.items():
        d = direction.normalized()
        if ortho:
            cam_data.type = "ORTHO"
            if name == "front":
                extent = max(dims.x, dims.z)
            elif name == "side":
                extent = max(dims.y, dims.z)
            else:
                extent = max(dims.x, dims.y)
            cam_data.ortho_scale = extent * 1.18
            dist = radius * 4 + 5
        else:
            cam_data.type = "PERSP"
            cam_data.lens = 70
            fov = 2 * math.atan(cam_data.sensor_width / 2 / cam_data.lens)
            dist = radius / math.sin(fov / 2) * 1.08
        cam.location = center + d * dist
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = str(out_dir / f"{name}.png")
        bpy.ops.render.render(write_still=True)
