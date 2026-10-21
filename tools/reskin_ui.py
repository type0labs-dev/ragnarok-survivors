#!/usr/bin/env python3
# Tela de título e marcas do VS → Ragnarok Survivors (data.unity3d/sharedassets1):
#   title (332x133, logo "VAMPIRE SURVIVORS")  → "RAGNAROK / SURVIVORS" no mesmo tratamento: dourado em degradê,
#     contorno marrom e sombra. As letras grandes do VS só existem prontas e faltam N e K, então desenha com fonte.
#   titleSurvivaton (319x37, subtítulo)        → "RUNE-MIDGARD" no mesmo estilo
#   introBG (400x300, lua vermelha do título)   → tela de loading do RO com o elenco de classes (loading03.jpg)
# Roda depois do patch_data.py/reskin_icons.py (lê e grava o data.unity3d do overlay).
# uso: python3 -P tools/reskin_ui.py <romfs> <overlay>
import sys, os, re, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -P tira a pasta do script do path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from unitypatch import Bundle
from rosprite import retro

romfs, out = sys.argv[1:3]
REL = "Data/data.unity3d"
from paths import UI, work, font
FONT = font()
src_path = os.path.join(out, REL) if os.path.exists(os.path.join(out, REL)) else os.path.join(romfs, REL)


def gold_text(lines, W, H):
    """[(texto, tamanho, y)] em dourado com contorno e sombra, centralizado numa tela WxH transparente"""
    canvas = Image.new("RGBA", (W, H))
    for txt, size, y in lines:
        f = ImageFont.truetype(FONT, size)
        bb = f.getbbox(txt)
        m = Image.new("L", (bb[2] - bb[0] + 8, bb[3] - bb[1] + 8))
        ImageDraw.Draw(m).text((4 - bb[0], 4 - bb[1]), txt, font=f, fill=255)
        if m.width > W - 8:
            m = m.resize((W - 8, m.height), Image.LANCZOS)
        x = (W - m.width) // 2
        ring = m.filter(ImageFilter.MaxFilter(5))
        shadow = Image.new("RGBA", m.size)
        shadow.putalpha(ring.point(lambda v: int(v * 0.7)))
        canvas.alpha_composite(shadow, (x + 2, y + 3))
        edge = Image.new("RGBA", m.size, (70, 25, 5, 255))
        edge.putalpha(ring)
        canvas.alpha_composite(edge, (x, y))
        grad = Image.new("RGBA", m.size)
        d = ImageDraw.Draw(grad)
        for yy in range(m.height):
            t = yy / max(1, m.height - 1)
            d.line([(0, yy), (m.width, yy)], fill=(int(255 - 25 * t), int(236 - 130 * t), int(140 - 120 * t), 255))
        fill = Image.new("RGBA", m.size)
        fill.paste(grad, (0, 0), m)
        canvas.alpha_composite(fill, (x, y))
    return canvas


def cover(im, W, H):
    """recorta pro aspecto WxH (centro) e redimensiona"""
    r = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
    x, y = (im.width - W) // 2, (im.height - H) // 2
    return im.crop((x, y, x + W, y + H))


def put(b, obj, img):
    """mesmo formato quando o encoder reproduz o tamanho; senão (swizzle com padding) vira RGBA32 linear"""
    try:
        b.replace_texture(obj, img)
    except AssertionError:
        b.set_texture_rgba(obj, img)


b = Bundle(src_path)
tex = {o.read().m_Name: o for n, f in b.serialized() for o in f.objects.values() if o.type.name == "Texture2D"}
done = []
t = tex["title"].read()
put(b, tex["title"], gold_text([("RAGNAROK", 54, 4), ("SURVIVORS", 50, 66)], t.m_Width, t.m_Height))
done.append("title")
t = tex["titleSurvivaton"].read()
put(b, tex["titleSurvivaton"], gold_text([("RUNE-MIDGARD", 26, 1)], t.m_Width, t.m_Height))
done.append("titleSurvivaton")
t = tex["introBG"].read()
b.set_texture_rgba(tex["introBG"], cover(Image.open(f"{UI}/loading03.jpg").convert("RGBA"), t.m_Width, t.m_Height))
done.append("introBG")
dst = os.path.join(out, REL)
os.makedirs(os.path.dirname(dst), exist_ok=True)
print("ok", REL, b.save(dst), "trocados:", ", ".join(done))

# Telas de menu (título): cada bundle *menusplash tem sua cópia do introBG e uma arte de personagem. Fundo → tela de
# loading do RO; arte → sprite da classe do RO de frente (do atlas que o reskin_char gerou no overlay), ampliado
# em pixels inteiros como as artes em pixel do VS.
import json
CD = json.load(open(work("data", "CHARACTER_DATA.json"), encoding="utf-8-sig"))
SPLASH = {"imeldamenusplash": ("Imeldat", "IMELDA", "loading03.jpg"),
          "garlicparadisemenusplash": ("Poet", "CAMILLO", "loading00.jpg"),
          "shemoonmenusplash": ("Shemoont", "SHEMOONITA", "loading07.jpg")}
AA = os.environ.get("VS_AA", "Data/StreamingAssets/aa/Switch")  # DLC: "" (bundles na raiz do romfs)


def ro_front(vs_id):
    e = CD[vs_id][0]
    pre = e["spriteName"].replace("01.png", "")
    p = f"{out}/{AA}/vs_local_assets_{e['textureName'].lower()}.bundle"
    cb = Bundle(p if os.path.exists(p) else f"{romfs}/{AA}/vs_local_assets_{e['textureName'].lower()}.bundle")
    for _, f in cb.serialized():
        for o in f.objects.values():
            if o.type.name == "Sprite" and o.read().m_Name == f"{pre}d0_01":
                im = o.read().image.convert("RGBA")
                return im.crop(im.getbbox())
    return None


for bn, (art, vs_id, loading) in SPLASH.items():
    rel = f"{AA}/vs_local_assets_{bn}.bundle"
    sb = Bundle(f"{romfs}/{rel}")
    st = {o.read().m_Name: o for _, f in sb.serialized() for o in f.objects.values() if o.type.name == "Texture2D"}
    t = st["introBG"].read()
    sb.set_texture_rgba(st["introBG"], cover(Image.open(f"{UI}/{loading}").convert("RGBA"), t.m_Width, t.m_Height))
    fr = ro_front(vs_id)
    if fr is not None:
        t = st[art].read()
        k = max(1, min(t.m_Width // fr.width, t.m_Height // fr.height))
        big = fr.resize((fr.width * k, fr.height * k), Image.NEAREST)
        canvas = Image.new("RGBA", (t.m_Width, t.m_Height))
        canvas.alpha_composite(big, ((t.m_Width - big.width) // 2, t.m_Height - big.height))
        put(sb, st[art], canvas)
    os.makedirs(os.path.dirname(f"{out}/{rel}"), exist_ok=True)
    print("ok", rel, sb.save(f"{out}/{rel}"), f"fundo {loading}, {art} ← {vs_id}" + ("" if fr is not None else " (sem sprite)"))


# Arte do título dentro do data.unity3d: atlas "illustrations" (Antonio de chicote, o vampiro, a Imelda) → sprites
# do RO ampliados em pixels: Aprendiz, Lorde das Trevas (vilão), Maga
ILLU = {"illustrations_0": "ANTONIO", "illustrations_1": "VERANDA", "illustrations_2": "IMELDA"}
b = Bundle(os.path.join(out, REL))
for fname, f in b.serialized():
    texs = {o.path_id: o for o in f.objects.values() if o.type.name == "Texture2D"}
    hits = {}
    for o in f.objects.values():
        if o.type.name == "Sprite":
            t = o.read_typetree()
            ref = t["m_RD"]["texture"]
            if t["m_Name"] in ILLU and ref["m_FileID"] == 0 and ref["m_PathID"] in texs:
                hits.setdefault(ref["m_PathID"], []).append(t)
    for pid, ts in hits.items():  # um atlas por vez: reler o objeto devolve os bytes originais
        tobj = texs[pid]
        atlas = tobj.read().image.convert("RGBA")
        for t in ts:
            r = t["m_RD"]["textureRect"]
            x0, w, h = int(r["x"]), int(r["width"]), int(r["height"])
            y0 = atlas.height - int(r["y"]) - h
            fr = ro_front(ILLU[t["m_Name"]])
            atlas.paste((0, 0, 0, 0), (x0, y0, x0 + w, y0 + h))
            if fr is not None:
                k = max(1, min(w // fr.width, h // fr.height))
                big = fr.resize((fr.width * k, fr.height * k), Image.NEAREST)
                atlas.alpha_composite(big, (x0 + (w - big.width) // 2, y0 + h - big.height))
            print("  ", t["m_Name"], "←", ILLU[t["m_Name"]])
        put(b, tobj, atlas)
print("ok", REL, b.save(os.path.join(out, REL)), "ilustrações do título")

# Números de dano: ficam os do VS (Zero, 2026-10-16: os dígitos do RO em 5x8 perderam muita qualidade)

# Retratos dos personagens nos menus (UI_Menu "p_<nome>" e "merc<Nome>") → sprite RO de frente do personagem,
# ampliado em pixels inteiros. Nome casa com o textureName (character_antonio → antonio), charName ou surname.
alias = {}
for vid, v in CD.items():
    e = v[0]
    for n in (e.get("textureName", "").replace("character_", ""), e.get("charName", ""), e.get("surname", "")):
        if n:
            alias.setdefault(re.sub(r"[^a-z0-9]", "", n.lower()), vid)
b = Bundle(os.path.join(out, REL))
portraits = 0
for fname, f in b.serialized():
    texs = {o.path_id: o for o in f.objects.values() if o.type.name == "Texture2D" and o.read().m_Name == "UI_Menu"}
    hits = {}
    for o in f.objects.values():
        if o.type.name == "Sprite":
            t = o.read_typetree()
            ref = t["m_RD"]["texture"]
            m = re.match(r"(?:p_|merc)([A-Za-z]+)$", t["m_Name"])
            if m and ref["m_FileID"] == 0 and ref["m_PathID"] in texs and m.group(1).lower() in alias:
                hits.setdefault(ref["m_PathID"], []).append((alias[m.group(1).lower()], t))
    for pid, ts in hits.items():
        atlas = texs[pid].read().image.convert("RGBA")
        for vid, t in ts:
            fr = ro_front(vid)
            if fr is None:
                continue
            r = t["m_RD"]["textureRect"]
            x0, w, h = int(r["x"]), int(r["width"]), int(r["height"])
            y0 = atlas.height - int(r["y"]) - h
            k = max(1, min(w // fr.width, h // fr.height)) if fr.width <= w and fr.height <= h else 0
            g = fr.resize((fr.width * k, fr.height * k), Image.NEAREST) if k else retro(fr, min(w / fr.width, h / fr.height))
            atlas.paste((0, 0, 0, 0), (x0, y0, x0 + w, y0 + h))
            atlas.alpha_composite(g, (x0 + (w - g.width) // 2, y0 + h - g.height))
            portraits += 1
        put(b, texs[pid], atlas)
print("ok", REL, b.save(os.path.join(out, REL)), f"{portraits} retratos")

# Capas do álbum (vs_ingame_album_*: base e Friends) e cards de aventura (adventuresui, 44) → telas de loading do RO
# recortadas pro aspecto de cada sprite (uma imagem diferente por sprite, em rodízio)
LOADS = [Image.open(f"{UI}/loading{i:02d}.jpg").convert("RGBA") for i in range(11) if os.path.exists(f"{UI}/loading{i:02d}.jpg")]


def fill_bundle(bn, start):
    rel = f"{AA}/vs_local_assets_{bn}.bundle"
    if not os.path.exists(f"{romfs}/{rel}"):
        return 0
    fb = Bundle(f"{romfs}/{rel}")
    n = 0
    for _, f in fb.serialized():
        texs = {o.path_id: o for o in f.objects.values() if o.type.name == "Texture2D"}
        spr = {}
        for o in f.objects.values():
            if o.type.name == "Sprite":
                t = o.read_typetree()
                if t["m_RD"]["texture"]["m_FileID"] == 0 and t["m_RD"]["texture"]["m_PathID"] in texs:
                    spr.setdefault(t["m_RD"]["texture"]["m_PathID"], []).append(t)
        for pid, ts in spr.items():
            atlas = texs[pid].read().image.convert("RGBA")
            for i, t in enumerate(sorted(ts, key=lambda t: t["m_Name"])):
                r = t["m_RD"]["textureRect"]
                x0, w, h = int(r["x"]), int(r["width"]), int(r["height"])
                y0 = atlas.height - int(r["y"]) - h
                atlas.paste(cover(LOADS[(start + i) % len(LOADS)], w, h), (x0, y0))
                n += 1
            put(fb, texs[pid], atlas)
    os.makedirs(os.path.dirname(f"{out}/{rel}"), exist_ok=True)
    fb.save(f"{out}/{rel}")
    return n


got = {bn: fill_bundle(bn, i) for i, bn in enumerate(("vs_ingame_album_vs_sidea", "vs_ingame_album_vs_sideb",
                                                       "vs_ingame_album_vs_sidec", "vs_ingame_album_friends",
                                                       "adventuresui"))}
print("ok álbum/aventuras:", got)

# Molduras e botões do VS (borda dourada) → azul-aço das janelas do RO, mantendo a luminância. Só nos sprites de
# moldura/botão/seleção/slot (UI_Menu e UI); conteúdo (sol, ícones) fica como está.
import numpy as np
FRAME = re.compile(r"^(frame|button_|selectionSquare|arrow|sliderrail|menu_checkbox|menu_slider|weaponSlots|"
                   r"weaponLevel|weaponBG|passiveBG|9slice)")


def ro_steel(img):
    a = np.asarray(img).astype(np.float32) / 255
    r, g, b_ = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a[..., :3].max(-1), a[..., :3].min(-1)
    d = np.where(mx - mn > 1e-6, mx - mn, 1)
    h = np.where(mx == r, ((g - b_) / d) % 6, np.where(mx == g, (b_ - r) / d + 2, (r - g) / d + 4)) * 60
    s = np.where(mx > 0, (mx - mn) / np.where(mx > 0, mx, 1), 0)
    gold = (h >= 25) & (h <= 65) & (s > 0.3) & (mx > 0.35)
    lum = 0.3 * r + 0.59 * g + 0.11 * b_
    steel = np.stack([0.55 * lum + 0.10, 0.75 * lum + 0.12, 1.05 * lum + 0.18], -1).clip(0, 1)
    a[..., :3] = np.where(gold[..., None], steel, a[..., :3])
    return Image.fromarray((a * 255).astype(np.uint8))


b = Bundle(os.path.join(out, REL))
framed = 0
for fname, f in b.serialized():
    texs = {o.path_id: o for o in f.objects.values() if o.type.name == "Texture2D" and o.read().m_Name in ("UI_Menu", "UI")}
    hits = {}
    for o in f.objects.values():
        if o.type.name == "Sprite":
            t = o.read_typetree()
            ref = t["m_RD"]["texture"]
            if FRAME.match(t["m_Name"]) and ref["m_FileID"] == 0 and ref["m_PathID"] in texs:
                hits.setdefault(ref["m_PathID"], []).append(t)
    for pid, ts in hits.items():
        atlas = texs[pid].read().image.convert("RGBA")
        for t in ts:
            r = t["m_RD"]["textureRect"]
            x0, w, h = int(r["x"]), int(r["width"]), int(r["height"])
            y0 = atlas.height - int(r["y"]) - h
            atlas.paste(ro_steel(atlas.crop((x0, y0, x0 + w, y0 + h))), (x0, y0))
            framed += 1
        put(b, texs[pid], atlas)
print("ok", REL, b.save(os.path.join(out, REL)), f"{framed} molduras/botões em azul-aço")
