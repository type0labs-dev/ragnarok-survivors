#!/usr/bin/env python3
# Arcanas (atlas randomazzo do data.unity3d: sprites "00".."43" = ARCANA_DATA frameName) → cartas do RO
# (items.yaml arcanas). As 14 cartas do Tarô do Destino (skill da Odalisca/Cigana) usam a arte delas
# (texture/effect/tarotNN.tga); as outras arcanas usam a ilustração da carta de monstro do mapping
# (num2cardillustnametable: Id → nome → texture/유저인터페이스/cardbmp/<nome>.bmp). Arte recortada pro aspecto do sprite.
# Roda depois do patch_data.py (data.unity3d do overlay).
# uso: python3 -P tools/reskin_arcana.py <romfs> <overlay>
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -P tira a pasta do script do path
import yaml
from PIL import Image
from unitypatch import Bundle

romfs, out = sys.argv[1:3]
REL = "Data/data.unity3d"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
k = lambda t: t.encode("cp949").decode("latin1")
from paths import RAG, work
CARDS = f"{RAG}/texture/{k('유저인터페이스')}/cardbmp"
TAROT = ["The Fool", "The Magician", "The High Priestess", "The Chariot", "Strength", "The Lovers",
         "Wheel of Fortune", "The Hanged Man", "Death", "Temperance", "The Devil", "The Tower", "The Star", "The Sun"]
illust = {}
for line in open(f"{RAG}/num2cardillustnametable.txt", "rb").read().decode("cp949", "replace").splitlines():
    p = line.split("#")
    if len(p) >= 2 and p[0].strip().isdigit():
        illust[int(p[0])] = p[1]
raw = open(work("data", "ARCANA_DATA.json"), encoding="utf-8-sig").read()
frame_of = {}
for a, b_, c, d in re.findall(r'"name"\s*:\s*"([^"]+)"[^{}]*?"frameName"\s*:\s*"([^"]+)"|'
                              r'"frameName"\s*:\s*"([^"]+)"[^{}]*?"name"\s*:\s*"([^"]+)"', raw):
    frame_of.setdefault(a or d, (b_ or c).removesuffix(".png"))


def art(ref):
    ref = str(ref)
    for i, n in enumerate(TAROT):
        if ref.endswith(n):
            return Image.open(f"{RAG}/texture/effect/tarot{i + 1:02d}.tga").convert("RGBA")
    m = re.match(r"\s*(\d+)", ref)
    if m and int(m.group(1)) in illust:
        p = f"{CARDS}/{k(illust[int(m.group(1))])}.bmp"
        if os.path.exists(p):
            return Image.open(p).convert("RGBA")
    return None


def cover(im, w, h):
    r = max(w / im.width, h / im.height)
    im = im.resize((max(1, round(im.width * r)), max(1, round(im.height * r))), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


want, miss = {}, []
for x in yaml.safe_load(open(f"{ROOT}/mapping/items.yaml"))["arcanas"]:
    fr = frame_of.get(x["vs_name"].replace(" (Darkana)", ""))
    im = art(x["ro_ref"]) if fr else None
    if im is not None:
        want[fr] = im
    else:
        miss.append(f"{x['vs_name']}({x['ro_ref']})")

src = os.path.join(out, REL) if os.path.exists(os.path.join(out, REL)) else os.path.join(romfs, REL)
b = Bundle(src)
n = 0
for fname, f in b.serialized():
    texs = {o.path_id: o for o in f.objects.values() if o.type.name == "Texture2D" and o.read().m_Name == "randomazzo"}
    hits = {}
    for o in f.objects.values():
        if o.type.name == "Sprite":
            t = o.read_typetree()
            ref = t["m_RD"]["texture"]
            if t["m_Name"] in want and ref["m_FileID"] == 0 and ref["m_PathID"] in texs:
                hits.setdefault(ref["m_PathID"], []).append(t)
    for pid, ts in hits.items():
        atlas = texs[pid].read().image.convert("RGBA")
        for t in ts:
            r = t["m_RD"]["textureRect"]
            x0, w, h = int(r["x"]), int(r["width"]), int(r["height"])
            y0 = atlas.height - int(r["y"]) - h
            atlas.paste(cover(want[t["m_Name"]], w, h), (x0, y0))
            n += 1
        b.replace_texture(texs[pid], atlas)
print("ok", REL, b.save(os.path.join(out, REL)), f"{n} arcanas trocadas; sem arte ({len(miss)}):", ", ".join(miss))
