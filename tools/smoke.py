#!/usr/bin/env python3
# Fase 0: prova que o repack boota. Muda JSON (Whip/Antonio) e pinta o atlas do Antonio de magenta.
# uso: python3 -P tools/smoke.py <romfs-original> <saida-overlay>
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -P tira a pasta do script do path
from unitypatch import Bundle, I2Terms, text_asset_bytes

src, out = sys.argv[1], sys.argv[2]
DATA = "Data/data.unity3d"
ANT = "Data/StreamingAssets/aa/Switch/vs_local_assets_character_antonio.bundle"


def dest(rel):
    p = os.path.join(out, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


b = Bundle(os.path.join(src, DATA))
for n, f in b.serialized():
    for o in list(f.objects.values()):
        if o.type.name != "TextAsset":
            continue
        d = o.read()
        if d.m_Name == "WEAPON_DATA":
            w = json.loads(d.m_Script)
            w["WHIP"][0].update(name="Bash", description="Golpe do Espadachim. [smoke]", power=50)
        elif d.m_Name == "CHARACTER_DATA":
            w = json.loads(d.m_Script)
            w["ANTONIO"][0].update(charName="Espadachim", surname="de Prontera")
        else:
            continue
        b.replace_object(n, o, text_asset_bytes(d.m_Name, json.dumps(w, ensure_ascii=False).encode()))
    # nomes que aparecem na tela vêm do I2Languages (MonoBehaviour sem typetree), não do JSON
    for o in list(f.objects.values()):
        if o.type.name == "MonoBehaviour" and b"I2Languages" in o.get_raw_data()[:64]:
            t = I2Terms(o.get_raw_data())
            for key, val in {"characterLang/{ANTONIO}charName": "Espadachim",
                             "characterLang/{ANTONIO}surname": "de Prontera",
                             "weaponLang/{WHIP}name": "Bash"}.items():
                t.index[key][2] = [val] * len(t.index[key][2])
            b.replace_object(n, o, t.save())
print("ok", DATA, b.save(dest(DATA)))

b = Bundle(os.path.join(src, ANT))
for n, f in b.serialized():
    for o in f.objects.values():
        if o.type.name == "Texture2D":
            img = o.read().image.convert("RGBA")
            px = img.load()
            for y in range(img.height):
                for x in range(img.width):
                    if px[x, y][3]:
                        px[x, y] = (255, 0, 255, px[x, y][3])
            b.replace_texture(o, img)
print("ok", ANT, b.save(dest(ANT)))
