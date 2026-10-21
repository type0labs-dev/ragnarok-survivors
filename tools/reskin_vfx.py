#!/usr/bin/env python3
# Visual das armas (atlas vfx do data.unity3d, ASTC com mips) → efeitos e itens do RO (characters_weapons.yaml
# vfx_families). Cada família do VS (slash1..4, ProjectileKnife…) recebe os quadros do efeito do RO espalhados pela
# animação, encaixados no rect do VS (o jogo gira/escala o projétil; tamanho no mundo = pixels, então não muda).
# "effect X" = imagens de sprite/이팩트/X.spr na ordem; "item N" = ícone do item.
# Roda depois do patch_data.py (lê e grava o data.unity3d do overlay).
# uso: python3 -P tools/reskin_vfx.py <romfs> <overlay>
import sys, os, re, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -P tira a pasta do script do path
from paths import RAG
import yaml
from PIL import Image
from unitypatch import Bundle
from rosprite import retro, compose, MONSTER, HUMAN
from roact import read_act
from roicons import ro_icon, load_icon
from rofx import ro_frames

romfs, out = sys.argv[1:3]
REL = "Data/data.unity3d"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FAM = yaml.safe_load(open(f"{ROOT}/mapping/characters_weapons.yaml"))["vfx_families"]
src_path = os.path.join(out, REL) if os.path.exists(os.path.join(out, REL)) else os.path.join(romfs, REL)


def fill(fr, s):
    """escala do quadro pra família preencher o rect (Zero: esferas eram um ponto, o corte não aparecia): uma escala
    só pra família inteira (sem pulsar), inteira em NEAREST quando dá, senão retro (paleta original, alfa duro)"""
    if s >= 2:
        return fr.resize((fr.width * int(s), fr.height * int(s)), Image.NEAREST)
    return retro(fr, s) if abs(s - 1) > 0.05 else fr


cache, done = {}, {}
b = Bundle(src_path)
for fname, f in b.serialized():
    texs = {o.path_id: o for o in f.objects.values() if o.type.name == "Texture2D" and o.read().m_Name == "vfx"}
    if not texs:
        continue
    fams, owners = {}, {}
    for o in f.objects.values():
        if o.type.name != "Sprite":
            continue
        t = o.read_typetree()
        ref = t["m_RD"]["texture"]
        fam = t["m_Name"] if t["m_Name"] in FAM else re.sub(r"[_\-\d]+$", "", t["m_Name"])  # nome exato vence
        r = t["m_RD"]["textureRect"]
        owners.setdefault((ref["m_PathID"], r["x"], r["y"], r["width"], r["height"]), set()).add(fam)
        if ref["m_FileID"] == 0 and ref["m_PathID"] in texs and fam in FAM:
            fams.setdefault((ref["m_PathID"], fam), []).append(t)
    # o empacotador do VS deduplica quadros iguais: Star_18 (vazio 3×3) = NoDraw = Burst6, e o NoDraw é o pixel que o
    # modal do baú estica na tela inteira — pintar o Star_18 virou a grade de quadrados amarelos. Rect compartilhado
    # com sprite de outra família fica intocado.
    for k in list(fams):
        fams[k] = [t for t in fams[k] if owners[(k[0], *(t["m_RD"]["textureRect"][a] for a in ("x", "y", "width", "height")))] <= {k[1]}]
    for pid, tobj in texs.items():
        atlas = tobj.read().image.convert("RGBA")  # de cima pra baixo
        for (tp, fam), ts in fams.items():
            if tp != pid:
                continue
            ts.sort(key=lambda t: [int(x) for x in re.findall(r"\d+", t["m_Name"])] or [0])
            ref = FAM[fam].split("#")[0].strip()
            # modificadores no fim: "rotN" gira o quadro do RO; "fill" estica até o rect (o raio do Lightning Ring é
            # uma faixa deitada de 480×17 que o jogo gira e rola; o raio do RO é em pé)
            flags = set()
            while ref.split()[-1] in ("fill",) or re.fullmatch(r"rot\d+", ref.split()[-1]):
                flags.add(ref.split()[-1]); ref = ref.rsplit(None, 1)[0]
            if ref not in cache:
                cache[ref] = ro_frames(ref)
            frs = cache[ref]
            for fl in flags:
                if fl.startswith("rot"):
                    frs = [x.rotate(int(fl[3:]), Image.BICUBIC, expand=True) for x in frs]
                    frs = [x.crop(x.getbbox()) for x in frs if x.getbbox()]
            if not frs:
                done[fam] = "sem quadros"
                continue
            mw, mh = max(x.width for x in frs), max(x.height for x in frs)
            for i, t in enumerate(ts):
                r = t["m_RD"]["textureRect"]
                x0, w, h = int(r["x"]), int(r["width"]), int(r["height"])
                y0 = atlas.height - int(r["y"]) - h
                fr = frs[i * len(frs) // len(ts)]
                fr = fr.resize((w, h), Image.LANCZOS) if "fill" in flags else fill(fr, min(w / mw, h / mh))
                atlas.paste((0, 0, 0, 0), (x0, y0, x0 + w, y0 + h))
                atlas.alpha_composite(fr, (x0 + (w - fr.width) // 2, y0 + (h - fr.height) // 2))
            done[fam] = f"{len(ts)}←{ref}"
        b.replace_texture(tobj, atlas)
print("ok", REL, b.save(os.path.join(out, REL)), f"{len(done)} famílias:", "; ".join(f"{k} {v}" for k, v in done.items()))


# bundles weapon_*: todas as famílias de sprite do bundle recebem o efeito do RO da tabela weapon_bundles
WB = yaml.safe_load(open(f"{ROOT}/mapping/characters_weapons.yaml")).get("weapon_bundles") or {}
AA = os.environ.get("VS_AA", "Data/StreamingAssets/aa/Switch")  # DLC: "" (bundles na raiz do romfs)
for bn, ref in WB.items():
    rel = f"{AA}/vs_local_assets_{bn}.bundle"
    if not os.path.exists(f"{romfs}/{rel}"):
        continue
    if ref not in cache:
        cache[ref] = ro_frames(ref)
    frs = cache[ref]
    wb = Bundle(f"{romfs}/{rel}")
    n = 0
    for fname, f in wb.serialized():
        texs = {o.path_id: o for o in f.objects.values() if o.type.name == "Texture2D"}
        fams = {}
        for o in f.objects.values():
            if o.type.name == "Sprite":
                t = o.read_typetree()
                r = t["m_RD"]["texture"]
                if r["m_FileID"] == 0 and r["m_PathID"] in texs:
                    fams.setdefault((r["m_PathID"], re.sub(r"[_\-\d]+$", "", t["m_Name"])), []).append(t)
        for pid, tobj in texs.items():
            atlas = tobj.read().image.convert("RGBA")
            for (tp, fam), ts in fams.items():
                if tp != pid or not frs:
                    continue
                ts.sort(key=lambda t: [int(x) for x in re.findall(r"\d+", t["m_Name"])] or [0])
                for i, t in enumerate(ts):
                    r = t["m_RD"]["textureRect"]
                    x0, w, h = int(r["x"]), int(r["width"]), int(r["height"])
                    y0 = atlas.height - int(r["y"]) - h
                    fr = frs[i * len(frs) // len(ts)]
                    fr = retro(fr, min(1.0, w / fr.width, h / fr.height)) if w and h else fr
                    atlas.paste((0, 0, 0, 0), (x0, y0, x0 + w, y0 + h))
                    if w and h:
                        atlas.alpha_composite(fr, (x0 + (w - fr.width) // 2, y0 + (h - fr.height) // 2))
                    n += 1
            try:
                wb.replace_texture(tobj, atlas)
            except AssertionError:
                wb.set_texture_rgba(tobj, atlas)
    os.makedirs(os.path.dirname(f"{out}/{rel}"), exist_ok=True)
    wb.save(f"{out}/{rel}")
    print(f"   {bn}: {n} sprites ← {ref}")
