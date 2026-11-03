"""Renders assets/render/<palette>/tars.png: a TARS-style robot in Cycles (run once; committed).

    blender -b --factory-startup -P scripts/render_tars.py -- [gargantua|purple] [output.png]

Four brushed-aluminium slabs, each split at the hip, with bevelled edges, screws,
panel seams and a small display, lit by area lights on a transparent background.
"""
import math
import os
import sys

import bpy

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
PALETTE = ARGS[0] if ARGS else "gargantua"
# key and rim light colours per palette
LIGHTS = {
    "gargantua": {"key": (1.0, 0.84, 0.66), "rim": (1.0, 0.6, 0.28)},
    "purple": {"key": (0.86, 0.8, 1.0), "rim": (0.85, 0.3, 1.0)},
}[PALETTE]
OUT = ARGS[1] if len(ARGS) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "render",
                                                   PALETTE, "tars.png")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def material(name, color, metallic=1.0, roughness=0.3, aniso=0.0, brushed=False, emission=None, strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if aniso:
        bsdf.inputs["Anisotropic"].default_value = aniso
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1)
        bsdf.inputs["Emission Strength"].default_value = strength
    if brushed:
        # fine vertical streaks for a brushed-metal look, plus per-slab variation
        coord = nt.nodes.new("ShaderNodeTexCoord")
        mapping = nt.nodes.new("ShaderNodeMapping")
        mapping.inputs["Scale"].default_value = (260, 260, 2.5)
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 3.0
        noise.inputs["Detail"].default_value = 8
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.06
        nt.links.new(coord.outputs["Object"], mapping.inputs["Vector"])
        nt.links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
        nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        info = nt.nodes.new("ShaderNodeObjectInfo")
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (color[0] * 0.86, color[1] * 0.86, color[2] * 0.86, 1)
        ramp.color_ramp.elements[1].color = (*color, 1)
        nt.links.new(info.outputs["Random"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
        rough = nt.nodes.new("ShaderNodeMapRange")
        rough.inputs["To Min"].default_value = roughness - 0.06
        rough.inputs["To Max"].default_value = roughness + 0.08
        nt.links.new(noise.outputs["Fac"], rough.inputs["Value"])
        nt.links.new(rough.outputs["Result"], bsdf.inputs["Roughness"])
    return m


METAL = material("brushed aluminium", (0.40, 0.40, 0.42), roughness=0.36, aniso=0.6, brushed=True)
DARK = material("joint", (0.02, 0.02, 0.022), roughness=0.5)
SCREW = material("screw", (0.35, 0.35, 0.36), roughness=0.25)
GLASS = material("display glass", (0.005, 0.005, 0.006), metallic=0.0, roughness=0.05)
GLOW = material("display text", (1, 1, 1), metallic=0.0, emission=(1.0, 0.86, 0.66), strength=6.0)


def box(name, size, loc, mat, bevel=0.008):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    if bevel:
        mod = o.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 3
        mod.limit_method = "ANGLE"
    o.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    if hasattr(o.data, "set_sharp_from_angle"):
        o.data.set_sharp_from_angle(angle=math.radians(40))
    return o


SLAB_W, SLAB_D, GAP = 0.16, 0.30, 0.006
LOWER_H, UPPER_H, HIP_GAP = 0.66, 0.88, 0.012
parts = []
# slight walking pose: outer slabs shifted back and down a touch
offsets = [(0.018, 0.0), (-0.012, 0.012), (0.006, -0.006), (0.024, 0.004)]
for i in range(4):
    x = (i - 1.5) * (SLAB_W + GAP)
    dy, dz = offsets[i]
    lower = box(f"slab{i}_lower", (SLAB_W, SLAB_D, LOWER_H), (x, dy, LOWER_H / 2 + dz), METAL)
    upper = box(f"slab{i}_upper", (SLAB_W, SLAB_D, UPPER_H),
                (x, dy, LOWER_H + HIP_GAP + UPPER_H / 2 + dz), METAL)
    # dark hip joint between the two blocks
    box(f"slab{i}_joint", (SLAB_W * 0.7, SLAB_D * 0.7, HIP_GAP * 1.6), (x, dy, LOWER_H + HIP_GAP / 2 + dz), DARK, bevel=0)
    front = dy - SLAB_D / 2
    # screws in the corners of the upper block
    for sx in (-1, 1):
        for sz in (LOWER_H + HIP_GAP + 0.05, LOWER_H + HIP_GAP + UPPER_H - 0.05):
            bpy.ops.mesh.primitive_cylinder_add(radius=0.0085, depth=0.006, vertices=24,
                                                location=(x + sx * (SLAB_W / 2 - 0.03), front - 0.001, sz + dz),
                                                rotation=(math.pi / 2, 0, 0))
            bpy.context.object.data.materials.append(SCREW)
    # thin panel seams on the front faces
    for z in (0.22, LOWER_H + HIP_GAP + 0.30):
        box(f"slab{i}_seam{z}", (SLAB_W * 0.86, 0.002, 0.003), (x, front - 0.0005, z + dz), DARK, bevel=0)

# display on the second slab: recessed glass with glowing lines
dx = (1 - 1.5) * (SLAB_W + GAP)
dy, dz = offsets[1]
screen_z = LOWER_H + HIP_GAP + UPPER_H - 0.17 + dz
box("display", (0.13, 0.006, 0.08), (dx, dy - SLAB_D / 2 - 0.001, screen_z), GLASS, bevel=0.002)
for k, w in enumerate((0.08, 0.06, 0.095)):
    box(f"line{k}", (w, 0.002, 0.007), (dx - (0.095 - w) / 2, dy - SLAB_D / 2 - 0.005, screen_z + 0.025 - k * 0.022), GLOW, bevel=0)

# ground that only catches shadows, so the PNG stays transparent
bpy.ops.mesh.primitive_plane_add(size=8, location=(0, 0, 0))
bpy.context.object.is_shadow_catcher = True

# lighting: warm key from front-left, amber rim from behind-right, faint fill
def area(name, loc, rot, power, color, size):
    bpy.ops.object.light_add(type="AREA", location=loc, rotation=rot)
    l = bpy.context.object
    l.name = name
    l.data.energy = power
    l.data.color = color
    l.data.size = size
    return l


area("key", (-2.2, -2.4, 2.6), (math.radians(55), 0, math.radians(-42)), 380, LIGHTS["key"], 1.6)
area("rim", (2.4, 1.8, 2.2), (math.radians(-60), 0, math.radians(130)), 1800, LIGHTS["rim"], 1.0)
area("fill", (1.8, -3.0, 0.6), (math.radians(85), 0, math.radians(30)), 45, (0.85, 0.85, 0.95), 3.0)

world = bpy.data.worlds.new("space")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.012, 0.008, 0.006, 1)
scene.world = world

bpy.ops.object.camera_add(location=(2.2, -3.0, 1.15))
cam = bpy.context.object
cam.data.lens = 72
target = bpy.data.objects.new("target", None)
target.location = (0, 0, 0.77)
scene.collection.objects.link(target)
track = cam.constraints.new("TRACK_TO")
track.target = target
scene.camera = cam

scene.render.engine = "CYCLES"
scene.cycles.samples = 192
scene.cycles.use_denoising = True
scene.render.film_transparent = True
scene.render.resolution_x, scene.render.resolution_y = 560, 900
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("rendered", OUT)
