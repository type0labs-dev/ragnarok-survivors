#!/usr/bin/env python3
# Props e pickups animados do atlas tps_props (data.unity3d/resources.assets, ASTC) → RO (items.yaml sprite_families).
# Cada família do VS (Brazier1..N, Lantern1..4, Coffin…) recebe os quadros do RO espalhados pela animação:
#   "npc X" / "monster X" → .act da pasta npc/몬스터, ação 0 (parado), direção 0;  "item N" → ícone do item.
# O quadro do RO cabe no rect do sprite do VS, pé no fundo: no mundo o tamanho é o nº de pixels, então não muda.
# Roda depois do patch_data.py (lê e grava o data.unity3d do overlay).
# uso: python3 -P tools/reskin_props.py <romfs> <overlay>
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -P tira a pasta do script do path
import yaml
from PIL import Image
from unitypatch import Bundle
from rosprite import compose, retro, MONSTER, HUMAN
from roact import read_act
from roicons import ro_icon, load_icon

romfs, out = sys.argv[1:3]
REL = "Data/data.unity3d"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FAM = yaml.safe_load(open(f"{ROOT}/mapping/items.yaml"))["sprite_families"]
src_path = os.path.join(out, REL) if os.path.exists(os.path.join(out, REL)) else os.path.join(romfs, REL)


def ro_frames(ref):
    bits = ref.split("#")[0].split()
    kind, name = bits[:2]
    action = int(bits[2]) if len(bits) > 2 else 0  # "monster treasure_mimic 2" = ação 2 (abrir)
    if kind == "item":
        p = ro_icon(f"item {name}")
        return [load_icon(p)] if p else []
    act = f"{MONSTER}/{name}.act" if kind == "monster" else f"{HUMAN}/../npc/{name}.act"
    parts = [act]
    n = len(read_act(act)[1][action * 8])
    fr = [compose(parts, action * 8, m, crop=False, size=512) for m in range(n)]
    boxes = [f.getbbox() for f in fr if f.getbbox()]
    U = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    return [f.crop(U) for f in fr]


ATLASES = ("tps_props", "UI_Menu", "UI", "tps_stageHero_BaseGame")  # stageHero: chegada do minigame do carrinho
cache = {}
b = Bundle(src_path)
done = {}
for fname, f in b.serialized():
    texs = {o.path_id: o for o in f.objects.values() if o.type.name == "Texture2D" and o.read().m_Name in ATLASES}
    if not texs:
        continue
    fams = {}
    for o in f.objects.values():
        if o.type.name != "Sprite":
            continue
        t = o.read_typetree()
        ref = t["m_RD"]["texture"]
        fam = re.sub(r"[_\d]+$", "", t["m_Name"])
        if ref["m_FileID"] == 0 and ref["m_PathID"] in texs and fam in FAM:
            fams.setdefault((ref["m_PathID"], fam), []).append(t)
    for pid, tobj in texs.items():
        atlas = tobj.read().image.convert("RGBA")  # de cima pra baixo
        for (tp, fam), ts in fams.items():
            if tp != pid:
                continue
            ts.sort(key=lambda t: [int(x) for x in re.findall(r"\d+", t["m_Name"])] or [0])
            if FAM[fam] not in cache:
                cache[FAM[fam]] = ro_frames(FAM[fam])
            frs = cache[FAM[fam]]
            if not frs:
                continue
            for i, t in enumerate(ts):
                r = t["m_RD"]["textureRect"]
                x0, w, h = int(r["x"]), int(r["width"]), int(r["height"])
                y0 = atlas.height - int(r["y"]) - h
                fr = frs[i * len(frs) // len(ts)]
                fr = retro(fr, min(1.0, w / fr.width, h / fr.height))
                atlas.paste((0, 0, 0, 0), (x0, y0, x0 + w, y0 + h))
                atlas.alpha_composite(fr, (x0 + (w - fr.width) // 2, y0 + h - fr.height))
            done[fam] = f"{len(ts)}←{FAM[fam]}"
        b.replace_texture(tobj, atlas)
print("ok", REL, b.save(os.path.join(out, REL)), f"{len(done)} famílias:", "; ".join(f"{k} {v}" for k, v in done.items()))
