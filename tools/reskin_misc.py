#!/usr/bin/env python3
# Rabo da troca: arte que sobra nos bundles de uma DLC (ou nas cópias delas no romfs do jogo base) e não é personagem,
# inimigo, tileset nem música. Regra por categoria do nome do bundle, as mesmas do jogo base:
#   *menusplash*, *menu*, adv*, album, *sketch*  → telas de loading do RO recortadas pro aspecto de cada sprite
#   map* (mapms, mapfs, eme_map_biome…)          → minimapa do mapa do RO da região da DLC
#   prop*/heroprops                              → objetos do RO (npc) ajustados no rect, quadros espalhados
#   fx/noise/firerect/royalflush/clouds/lightbulb/guideline → efeitos do RO (brilho, fumaça, fogo)
# Bundles já tratados por outra ferramenta (personagem, inimigo, tileset, bgm, persistent) ficam de fora.
# uso: python3 -P tools/reskin_misc.py <romfs> <overlay> <dlc>   (dlc: chave do mapping, ex. moonspell, castlevania)
import sys, os, re, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -P tira a pasta do script do path
import yaml
from PIL import Image
from unitypatch import Bundle
from rosprite import compose, retro, effect_sprites, HUMAN
from roact import read_act

romfs, out, DLC = sys.argv[1:4]
AA = os.environ.get("VS_AA", "")
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mapping")
PREFIX = {"moonspell": "moonspell", "foscari": "foscari", "chalcedony": "chalcedony", "firstblood": "firstblood",
          "emeralds": "emeralds", "lemon": "lemon", "castlevania": "thosepeople"}[DLC]
if DLC == "castlevania":
    stages = yaml.safe_load(open(f"{ROOT}/dlc/castlevania_world.yaml"))["stages"]
else:
    stages = yaml.safe_load(open(f"{ROOT}/dlc/others_characters_world.yaml"))[DLC].get("stages") or []
MAPS = [m for s in stages for m in (s.get("ro_maps") or [])]
from paths import RAG, UI
MINI = [f"{UI}/map/{m}.bmp" for m in MAPS if os.path.exists(f"{UI}/map/{m}.bmp")]
LOADS = [f"{UI}/loading{i:02d}.jpg" for i in range(11) if os.path.exists(f"{UI}/loading{i:02d}.jpg")]
SKIP = re.compile(r"character|enem|bgm|_loop|_intro|persistent|tileset|texturepacked|tmx|support|album_castlevania")


def cover(path, w, h):
    im = Image.open(path).convert("RGB")
    im.putdata([(24, 22, 30) if c[0] > 240 and c[1] < 20 and c[2] > 240 else c for c in im.get_flattened_data()])
    im = im.convert("RGBA")
    r = max(w / im.width, h / im.height)
    im = im.resize((max(1, round(im.width * r)), max(1, round(im.height * r))), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def npc_frames(name):
    act = f"{HUMAN}/../npc/{name}.act"
    parts = [act]
    return [compose(parts, 0, m) for m in range(len(read_act(act)[1][0]))]


def effect_frames(name):
    ims = effect_sprites(name)
    return [i.crop(i.getbbox()) for i in ims if i.getbbox()]


def kind_of(bn):
    b = bn.lower()
    if re.search(r"map", b):
        return "map"
    if re.search(r"prop|heroprops|capsule|seal|barrel|car", b):
        return "prop"
    if re.search(r"fx|noise|firerect|royalflush|cloud|lightbulb|guideline|fire|glow", b):
        return "fx"
    return "art"  # splash, menu, adventure, album, sketch, parallax…


PROPS = [npc_frames(n) for n in ("4_energy", "4_treasure_box", "barricade", "4_steelbox", "4_gargoyle_statue")]
FX = [effect_frames(n) for n in ("particle6", "smoke", "fireball", "cconfine", "축복")]
done = []
for bn in sorted(os.listdir(os.path.join(romfs, AA))):
    if not bn.startswith(PREFIX) or not bn.endswith(".bundle") or SKIP.search(bn):
        continue
    dst = os.path.join(out, AA, bn)
    src = dst if os.path.exists(dst) else os.path.join(romfs, AA, bn)
    try:
        b = Bundle(src)
    except Exception:
        continue
    kind = kind_of(bn)
    n = 0
    for fname, f in b.serialized():
        texs = {o.path_id: o for o in f.objects.values() if o.type.name == "Texture2D"}
        if not texs:
            continue
        spr = {}
        for o in f.objects.values():
            if o.type.name == "Sprite":
                t = o.read_typetree()
                r = t["m_RD"]["texture"]
                if r["m_FileID"] == 0 and r["m_PathID"] in texs:
                    spr.setdefault(r["m_PathID"], []).append(t)
        for pid, tobj in texs.items():
            atlas = tobj.read().image.convert("RGBA")
            ts = sorted(spr.get(pid, []), key=lambda t: t["m_Name"])
            if not ts:  # textura solta (fundo, splash): a imagem inteira
                ts = [{"m_Name": tobj.read().m_Name, "m_RD": {"textureRect": {"x": 0, "y": 0, "width": atlas.width, "height": atlas.height}}}]
            fams = {}
            for t in ts:
                fams.setdefault(re.sub(r"[_\-\d]+$", "", t["m_Name"]), []).append(t)
            for fi, (fam, group) in enumerate(sorted(fams.items())):
                for i, t in enumerate(group):
                    r = t["m_RD"]["textureRect"]
                    x0, w, h = int(r["x"]), int(r["width"]), int(r["height"])
                    if w < 2 or h < 2:
                        continue
                    y0 = atlas.height - int(r["y"]) - h
                    if kind in ("art", "map"):
                        pool = MINI if (kind == "map" and MINI) else LOADS
                        atlas.paste(cover(pool[(fi + i) % len(pool)], w, h), (x0, y0))
                    else:
                        frs = (PROPS if kind == "prop" else FX)[fi % 5] or FX[0]
                        fr = frs[i * len(frs) // len(group)]
                        fr = retro(fr, min(1.0, w / fr.width, h / fr.height))
                        atlas.paste((0, 0, 0, 0), (x0, y0, x0 + w, y0 + h))
                        atlas.alpha_composite(fr, (x0 + (w - fr.width) // 2, y0 + h - fr.height))
                    n += 1
            try:
                b.replace_texture(tobj, atlas)
            except AssertionError:
                b.set_texture_rgba(tobj, atlas)
    if n:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        b.save(dst)
        done.append(f"{bn.replace(PREFIX + '_dynamic_assets_', '')}[{kind}:{n}]")
print(f"ok resto {DLC}: {len(done)} bundles:", " ".join(done)[:600])
