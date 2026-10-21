#!/usr/bin/env python3
# Conjuntos avulsos de sprites (mapping/items.yaml spritesets): bundles character_* com animações que não são de
# personagem jogável (seguidores, corrida do Trouser, pato/coelho lunares, Tarantella, Xanthia). Cada prefixo recebe os
# quadros do andar (monstro) ou parado (NPC) do RO, espelhados, encaixados no rect de cada sprite do VS, no lugar.
# uso: python3 -P tools/reskin_spritesets.py <romfs> <overlay>
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -P tira a pasta do script do path
import yaml
from PIL import Image
from unitypatch import Bundle
from rosprite import compose, retro, HUMAN, MONSTER
from roact import read_act

romfs, out = sys.argv[1:3]
AA = "Data/StreamingAssets/aa/Switch"
SETS = yaml.safe_load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mapping", "items.yaml")))["spritesets"]


def frames(ref):
    kind, name = ref.split()[:2]
    act = f"{MONSTER}/{name}.act" if kind == "monster" else f"{HUMAN}/../npc/{name}.act"
    acts = read_act(act)[1]
    a = 1 if kind == "monster" and len(acts) > 8 + 6 and acts[8 + 6] else 0
    fr = [compose([act], a * 8 + 6, m, crop=False, size=512) for m in range(len(acts[a * 8 + 6]))]
    boxes = [f.getbbox() for f in fr if f.getbbox()]
    U = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    return [f.crop(U).transpose(Image.FLIP_LEFT_RIGHT) for f in fr]


done = []
for bn, fams in SETS.items():
    rel = f"{AA}/vs_local_assets_{bn}.bundle"
    b = Bundle(f"{romfs}/{rel}")
    for fname, f in b.serialized():
        tex = next(o for o in f.objects.values() if o.type.name == "Texture2D")
        atlas = tex.read().image.convert("RGBA")
        sprites = [o.read_typetree() for o in f.objects.values() if o.type.name == "Sprite"]
        n = 0
        for pre, ref in fams.items():
            group = sorted((t for t in sprites if t["m_Name"].startswith(pre)), key=lambda t: t["m_Name"])
            frs = frames(ref)
            mw, mh = max(x.width for x in frs), max(x.height for x in frs)
            for i, t in enumerate(group):
                r = t["m_RD"]["textureRect"]
                x0, w, h = int(r["x"]), int(r["width"]), int(r["height"])
                y0 = atlas.height - int(r["y"]) - h
                fr = retro(frs[i * len(frs) // len(group)], min(1.0, w / mw, h / mh))
                atlas.paste((0, 0, 0, 0), (x0, y0, x0 + w, y0 + h))
                atlas.alpha_composite(fr, (x0 + (w - fr.width) // 2, y0 + h - fr.height))
                n += 1
        b.replace_texture(tex, atlas)
    os.makedirs(os.path.dirname(f"{out}/{rel}"), exist_ok=True)
    b.save(f"{out}/{rel}")
    done.append(f"{bn}:{n}")
print("ok conjuntos avulsos:", " ".join(done))
