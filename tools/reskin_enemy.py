#!/usr/bin/env python3
# Troca um inimigo do VS por um monstro do RO em resolução nativa, sem mexer nos outros 2000+ sprites do atlas:
# a textura cresce pra cima (rect do Unity é medido de baixo, os existentes continuam valendo) e só os sprites do
# inimigo apontam pra área nova. O tamanho na tela volta pelo ENEMY_DATA.scale (tools/patch_data.py).
# uso: python3 -P tools/reskin_enemy.py <romfs> <overlay> <bundle> <prefixo VS> <monstro RO> [ação RO] [direção]
#   ex.: ... vs_local_assets_enemies_universal.bundle Bat1 farmiliar 1 6
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -P tira a pasta do script do path
from PIL import Image
from unitypatch import Bundle, typetree_bytes
from rosprite import compose, quad_vertices, MONSTER

romfs, out, bundle_name, prefix, mob = sys.argv[1:6]
action = int(sys.argv[6]) if len(sys.argv) > 6 else 1     # 1 = andar
direction = int(sys.argv[7]) if len(sys.argv) > 7 else 6  # 6 = leste
REL = f"Data/StreamingAssets/aa/Switch/{bundle_name}"

parts = [f"{MONSTER}/{mob}.act"]
from roact import read_act
n_mot = len(read_act(parts[0])[1][action * 8 + direction])
idle = [compose(parts, action * 8 + direction, m) for m in range(n_mot)]
# o VS usa: <prefixo> e <prefixo>_0 como sprite parado (frameNames[0]), <prefixo>_i01.. como idle animado
targets = {prefix: idle[0], f"{prefix}_0": idle[0]}

b = Bundle(os.path.join(romfs, REL))
(fname, f), = b.serialized()
tex = next(o for o in f.objects.values() if o.type.name == "Texture2D")
sprites = {o.read_typetree()["m_Name"]: o for o in f.objects.values() if o.type.name == "Sprite"}
n_idle = sum(1 for k in sprites if k.startswith(f"{prefix}_i"))
for i in range(n_idle):  # distribui os quadros do RO pelos slots de idle que o VS tem
    targets[f"{prefix}_i{i + 1:02d}"] = idle[i * n_mot // n_idle]
targets = {k: v for k, v in targets.items() if k in sprites}  # nem todo inimigo tem o sprite sem sufixo

# área nova no topo da textura, quadros lado a lado
pad = 2
add_h = max(fr.height for fr in targets.values()) + 2 * pad
src = tex.read().image.convert("RGBA")  # de cima pra baixo
atlas = Image.new("RGBA", (src.width, src.height + add_h)); atlas.paste(src, (0, add_h))
x = pad
for name, fr in targets.items():
    o = sprites[name]
    t = o.read_typetree()
    top = pad + (add_h - 2 * pad - fr.height)          # pé alinhado embaixo da faixa
    atlas.paste(fr, (x, top))
    rect = {"x": float(x), "y": float(atlas.height - top - fr.height), "width": float(fr.width), "height": float(fr.height)}
    t["m_Rect"] = dict(rect); t["m_RD"]["textureRect"] = dict(rect)
    t["m_Pivot"] = {"x": 0.5, "y": 0.5}; t["m_Offset"] = {"x": 0.0, "y": 0.0}
    t["m_RD"]["textureRectOffset"] = {"x": 0.0, "y": 0.0}
    t["m_RD"]["uvTransform"] = {"x": 100.0, "y": rect["x"] + fr.width / 2, "z": 100.0, "w": rect["y"] + fr.height / 2}
    t["m_RD"]["m_VertexData"]["m_DataSize"] = quad_vertices(fr.width, fr.height)
    b.replace_object(fname, o, typetree_bytes(o, t))
    x += fr.width + pad
assert x <= atlas.width, "faixa nova não coube na largura"

tt = tex.read_typetree()
res = tt["m_StreamData"]["path"].rsplit("/", 1)[-1]
assert tt["m_StreamData"]["offset"] == 0 and len(b.raw[res]) == tt["m_StreamData"]["size"], "resS com mais coisa"
px = atlas.transpose(Image.FLIP_TOP_BOTTOM).tobytes()
tt["m_Height"] = atlas.height
tt["m_CompleteImageSize"] = tt["m_StreamData"]["size"] = len(px)
b.raw[res] = bytearray(px)
b.replace_object(fname, tex, typetree_bytes(tex, tt))

dst = os.path.join(out, REL)
os.makedirs(os.path.dirname(dst), exist_ok=True)
print("ok", REL, b.save(dst), f"atlas {atlas.size}, {mob}: {n_mot} quadros RO → {len(targets)} sprites, "
      f"altura máx {max(fr.height for fr in targets.values())}px")
