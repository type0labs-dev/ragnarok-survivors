#!/usr/bin/env python3
# Troca os ícones do atlas tps_lossless_icons (data.unity3d/resources.assets, RGBA32 linear 512²) pelos do RO:
# arma → ícone da skill (texture/유저인터페이스/item/<skill>.bmp), passivo/item/relíquia/pickup → ícone do item
# (idnum2itemresnametable: Id → nome do recurso). O atlas vira 2× (unitypatch.upscale_atlas + hook SpriteRect, que
# devolve o tamanho do VS pro jogo) e o ícone do RO (24×24, magenta = transparente) entra 1:1 no rect de 16 → 32.
# Roda depois do patch_data.py (lê e grava o data.unity3d do overlay).
# uso: python3 -P tools/reskin_icons.py <romfs> <overlay>
import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -P tira a pasta do script do path
import yaml
from PIL import Image
from unitypatch import Bundle

romfs, out = sys.argv[1:3]
REL = "Data/data.unity3d"
D = 2  # densidade dos atlas de ícone (RT do mundo 2×; UI na resolução da tela)
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
src_path = os.path.join(out, REL) if os.path.exists(os.path.join(out, REL)) else os.path.join(romfs, REL)
from roicons import ro_icon, load_icon, fit_icon


from paths import work
L = lambda f: json.load(open(work("data", f"{f}.json"), encoding="utf-8-sig"))
first = lambda v: v[0] if isinstance(v, list) else v
frame = {}  # vs_id -> frameName (sem .png)
for f in ("WEAPON_DATA", "ITEM_DATA", "POWERUP_DATA"):
    for k, v in L(f).items():
        e = first(v)
        if e.get("frameName") and e.get("texture", "tps_lossless_icons") == "tps_lossless_icons":
            frame.setdefault(k, e["frameName"].removesuffix(".png"))
cw = yaml.safe_load(open(f"{ROOT}/mapping/characters_weapons.yaml"))
it = yaml.safe_load(open(f"{ROOT}/mapping/items.yaml"))
want, missing = {}, []  # frameName -> bmp
for x in cw["weapons"] + cw["passives"] + cw["powerups"] + it["pickups"] + it["relics"]:
    if x.get("parent") or x.get("scope") == "later" or x.get("icon") == "vs" or x["vs_id"] not in frame:
        continue
    p = ro_icon(x.get("ro_ref"))
    if p:
        want.setdefault(frame[x["vs_id"]], p)
    else:
        missing.append(f"{x['vs_id']}({x.get('ro_ref')})")

for spr, ref in (it.get("sprite_variants") or {}).items():
    p = ro_icon(ref)
    if p:
        want[spr] = p  # variação explícita vence o ícone do registro
    else:
        missing.append(f"{spr}({ref})")

b = Bundle(src_path)
# o mesmo nome de sprite existe em vários atlases: tps_lossless_icons (ícones de UI), vfx (gemas/moedas no chão),
# tps_props, UI_Menu (ASTC). Troca em todos que tiverem o nome, cada atlas inteiro reescrito no formato dele.
done, per = 0, {}
for fname, f in b.serialized():
    texs = {o.path_id: o for o in f.objects.values() if o.type.name == "Texture2D"}
    hits = {}
    for o in f.objects.values():
        if o.type.name != "Sprite":
            continue
        t = o.read_typetree()
        ref = t["m_RD"]["texture"]
        if ref["m_FileID"] == 0 and ref["m_PathID"] in texs and t["m_Name"] in want:
            hits.setdefault(ref["m_PathID"], []).append(t)
    for pid, ts in hits.items():
        tobj = texs[pid]
        # atlas em 2× (hook SpriteRect devolve o tamanho do VS): o ícone do RO (24 px) cabe 1:1 no rect de 16 → 32
        atlas, k = b.upscale_atlas(tobj, D)  # de cima pra baixo
        for t in ts:
            r = {a: v * k for a, v in t["m_RD"]["textureRect"].items()}
            x0, w, h = int(r["x"]), int(r["width"]), int(r["height"])
            y0 = atlas.height - int(r["y"]) - h
            ic = load_icon(want[t["m_Name"]])
            ic = fit_icon(ic, w, h)
            atlas.paste((0, 0, 0, 0), (x0, y0, x0 + w, y0 + h))
            atlas.paste(ic, (x0 + (w - ic.width) // 2, y0 + (h - ic.height) // 2), ic)
        b.set_texture_rgba(tobj, atlas)
        per[tobj.read().m_Name] = len(ts)
        done += len(ts)
dst = os.path.join(out, REL)
os.makedirs(os.path.dirname(dst), exist_ok=True)
print("ok", REL, b.save(dst), f"{done} sprites trocados {per} de {len(want)} ícones; sem ícone RO ({len(missing)}):",
      ", ".join(missing[:40]))
