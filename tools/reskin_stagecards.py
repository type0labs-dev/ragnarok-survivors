#!/usr/bin/env python3
# Cards e ícones da seleção de fase e fundos do bestiário (STAGE_DATA uiFrame/frameName nos atlases UI_StageIcons/UI_Menu) → minimapa do
# 1º mapa do RO da região da fase (texture/유저인터페이스/map/<mapa>.bmp), recortado pro aspecto do card.
# Vale pra todas as cópias: bundle ui_stageicons e os atlases dentro do data.unity3d.
# Roda depois do patch_data.py (data.unity3d do overlay).
# uso: python3 -P tools/reskin_stagecards.py <romfs> <overlay>
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -P tira a pasta do script do path
import yaml
from PIL import Image
from unitypatch import Bundle

romfs, out = sys.argv[1:3]
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
from paths import UI, work
MAPS = UI + "/map"
AA = os.environ.get("VS_AA", "Data/StreamingAssets/aa/Switch")  # DLC: "" (bundles na raiz do romfs)
st = {x["vs_id"]: x for x in yaml.safe_load(open(f"{ROOT}/mapping/stages_music_ui_story.yaml"))["stages"]}
SD = json.load(open(work("data", "STAGE_DATA.json"), encoding="utf-8-sig"))
want = {}  # nome do sprite -> minimapa
for vid, v in SD.items():
    maps = (st.get(vid) or {}).get("ro_maps") or []
    p = next((f"{MAPS}/{m}.bmp" for m in maps if os.path.exists(f"{MAPS}/{m}.bmp")), None)
    if p:
        for k in ("uiFrame", "frameName", "frameNameUnlock"):
            if v[0].get(k):
                want[v[0][k].removesuffix(".png")] = p
        if v[0].get("bestiaryBG"):  # fundo do bestiário: o 1º estágio que usa define a região
            want.setdefault(v[0]["bestiaryBG"].removesuffix(".png"), p)


# variações dos cards (stage_forest_A/_B/_icon/_unlock…) herdam o minimapa do card base
for spr in list(want):
    for suf in ("_A", "_B", "_icon", "_unlock", "_hyper_icon", "_boss_icon"):
        want.setdefault(spr + suf, want[spr])


def cover(im, w, h):
    r = max(w / im.width, h / im.height)
    im = im.resize((max(1, round(im.width * r)), max(1, round(im.height * r))), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def apply(path, dst):
    b = Bundle(path)
    n = 0
    for fname, f in b.serialized():
        texs = {o.path_id: o for o in f.objects.values() if o.type.name == "Texture2D"}
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
                mm = Image.open(want[t["m_Name"]]).convert("RGB")
                mm.putdata([(24, 22, 30) if c[0] > 240 and c[1] < 20 and c[2] > 240 else c for c in mm.get_flattened_data()])
                mm = mm.convert("RGBA")  # magenta (fora do mapa no BMP do RO) vira fundo escuro
                atlas.paste(cover(mm, w, h), (x0, y0))
                n += 1
            try:
                b.replace_texture(texs[pid], atlas)
            except AssertionError:
                b.set_texture_rgba(texs[pid], atlas)
    if n:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        b.save(dst)
    return n


done = []
rel = f"{AA}/vs_local_assets_ui_stageicons.bundle"
done.append(f"ui_stageicons {apply(f'{romfs}/{rel}', f'{out}/{rel}')}")
rel = f"{AA}/vs_local_assets_ui_bestiary.bundle"
done.append(f"ui_bestiary {apply(f'{romfs}/{rel}', f'{out}/{rel}')}")
rel = "Data/data.unity3d"
done.append(f"data.unity3d {apply(f'{out}/{rel}' if os.path.exists(f'{out}/{rel}') else f'{romfs}/{rel}', f'{out}/{rel}')}")
print("ok cards de fase:", ", ".join(done), f"({len(want)} sprites pedidos)")
