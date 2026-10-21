#!/usr/bin/env python3
# Roleta (vs_local_assets_wheeloffortune3: roda 350² com ícones de item/inimigo do VS pintados nas fatias). Os ícones
# somem copiando, pra cada pixel da faixa externa, a textura da mesma fatia (mesmo ângulo) perto do centro, onde não há
# ícone; a diferença entre a roda original e a limpa dá os blocos de ícone (componentes compactos; as linhas douradas
# são compridas e finas e ficam fora), e cada bloco recebe um ícone de item do RO no mesmo tamanho.
# uso: python3 -P tools/reskin_wheel.py <romfs> <overlay>
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -P tira a pasta do script do path
from PIL import Image, ImageChops, ImageFilter
from unitypatch import Bundle
from roicons import ro_icon, load_icon, fit_icon

romfs, out = sys.argv[1:3]
REL = "Data/StreamingAssets/aa/Switch/vs_local_assets_wheeloffortune3.bundle"
ICONS = [671, 706, 969, 12142, 517, 2608, 7228, 610, 12210, 512, 607, 717, 716, 715]  # zeny, trevo, ouro, livro, carne…


def components(mask):
    w, h = mask.size
    m = mask.load()
    seen, comps = set(), []
    for y in range(h):
        for x in range(w):
            if m[x, y] and (x, y) not in seen:
                st, pts = [(x, y)], []
                seen.add((x, y))
                while st:
                    p = st.pop()
                    pts.append(p)
                    for q in ((p[0] + 1, p[1]), (p[0] - 1, p[1]), (p[0], p[1] + 1), (p[0], p[1] - 1)):
                        if 0 <= q[0] < w and 0 <= q[1] < h and m[q] and q not in seen:
                            seen.add(q)
                            st.append(q)
                xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                bb = (min(xs), min(ys), max(xs) + 1, max(ys) + 1)
                comps.append((bb, len(pts)))
    return comps


b = Bundle(f"{romfs}/{REL}")
tex = next(o for _, f in b.serialized() for o in f.objects.values() if o.type.name == "Texture2D")
im = tex.read().image.convert("RGBA")
W = im.width
c = W / 2
clean = im.copy()
px, cp = im.load(), clean.load()
for y in range(W):
    for x in range(W):
        dx, dy = x - c, y - c
        r = math.hypot(dx, dy)
        if r >= 70 and px[x, y][3] > 0:
            rs = 30 + (r - 70) * 0.3
            s = px[int(c + dx / r * rs), int(c + dy / r * rs)]
            cp[x, y] = s[:3] + (px[x, y][3],)
diff = ImageChops.difference(im.convert("RGB"), clean.convert("RGB")).convert("L").point(lambda v: 255 if v > 60 else 0)
diff = diff.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(7))  # abertura: linhas de 2 px somem
icons = []
for (x0, y0, x1, y1), n in components(diff):
    w, h = x1 - x0, y1 - y0
    if n < 300 or max(w, h) / max(1, min(w, h)) > 4:  # sobra de linha dourada: comprida e fina
        continue
    icons.append((x0, y0, x1, y1))
# um ícone por direção: blocos a menos de 18° um do outro são o mesmo ícone (fica o maior)
ang = lambda bb: math.degrees(math.atan2((bb[1] + bb[3]) / 2 - c, (bb[0] + bb[2]) / 2 - c))
keep = []
for bb in sorted(icons, key=lambda bb: -(bb[2] - bb[0]) * (bb[3] - bb[1])):
    if all(abs((ang(bb) - ang(k) + 180) % 360 - 180) >= 18 for k in keep):
        keep.append(bb)
icons = sorted(keep, key=ang)
out_im = clean.copy()
for i, (x0, y0, x1, y1) in enumerate(icons):
    side = min(56, max(x1 - x0, y1 - y0))
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    x0, y0, x1, y1 = cx - side // 2, cy - side // 2, cx + side // 2, cy + side // 2
    ic = fit_icon(load_icon(ro_icon(f"item {ICONS[i % len(ICONS)]}")), x1 - x0, y1 - y0)
    out_im.alpha_composite(ic, (x0 + (x1 - x0 - ic.width) // 2, y0 + (y1 - y0 - ic.height) // 2))
b.replace_texture(tex, out_im)
os.makedirs(os.path.dirname(f"{out}/{REL}"), exist_ok=True)
b.save(f"{out}/{REL}")
out_im.save(os.path.join(out, "..", "wheel_preview.png")) if os.environ.get("WHEEL_PREVIEW") else None
print(f"ok roleta: {len(icons)} ícones trocados")
