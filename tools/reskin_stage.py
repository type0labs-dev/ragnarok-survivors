#!/usr/bin/env python3
# Troca o tileset de uma fase do VS pelo chão e cenário de um mapa do RO (texturas do .gnd e dos modelos do .rsw).
#   chão (componentes opacos grandes do atlas): as cores do VS viram até K classes (k-means); cada classe recebe a
#     textura de chão do mapa do RO de cor média mais próxima, ladrilhada com período de 32 px alinhado ao atlas
#     (o tile do VS é 32 px: qualquer vizinho no tilemap emenda sem costura). O desenho das manchas (terra no meio
#     da grama, bordas) fica, só que pintado com o chão do RO.
#   decoração (componentes com transparência: árvores, plantas, lápides): troca por uma textura de modelo do mapa
#     com fundo magenta (copas, arbustos, cogumelos, cipós), da proporção mais parecida, encaixada na mesma caixa.
# O tilemap e a colisão não mudam (ficam em outros objetos); só os pixels do atlas.
# uso: python3 -P tools/reskin_stage.py <romfs> <overlay> <TextureName> <mapa_ro>[,<mapa_ro>...]
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -P tira a pasta do script do path
from paths import work
from collections import deque
import numpy as np
from PIL import Image
from unitypatch import Bundle
from romap import gnd_textures, rsw_models, rsm_textures
from rosprite import retro

romfs, out, TEXNAME, maps = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4].split(",")
AA = os.environ.get("VS_AA", "Data/StreamingAssets/aa/Switch")  # DLC: "" (bundles na raiz do romfs)
PERIOD, K = 32, 5


def keyed(p):
    im = Image.open(p).convert("RGBA")
    a = np.asarray(im).copy()
    a[(a[..., 0] > 240) & (a[..., 1] < 20) & (a[..., 2] > 240), 3] = 0  # magenta = transparente no RO
    return Image.fromarray(a)


ground_tex, props, _prop_paths = [], [], []
for m in maps:
    # paredes e penhascos do .gnd são as laterais dos degraus do terreno 3D: no chão de cima viram textura repetida
    bad = ("backside", "wall", "절벽".encode("cp949").decode("latin1"), "cliff")
    ground_tex += [p for p in gnd_textures(m) if not any(k in p.lower() for k in bad)]
    for x in rsw_models(m):
        for p in rsm_textures(x):
            im = keyed(p)
            a = np.asarray(im)[..., 3]
            if 0.1 < (a == 0).mean() < 0.9 and im.getbbox():
                props.append(im.crop(im.getbbox()))
                _prop_paths.append(p)
assert ground_tex, f"{maps}: sem textura de chão"
NATURE = "나무잡초꽃".encode("cp949").decode("latin1")
if sum(NATURE in p for p in _prop_paths) >= 3:  # mapa de campo: só vegetação (placas e construções ficam de fora)
    props = [im for im, p in zip(props, _prop_paths) if NATURE in p]
tiles = []
for p in ground_tex:
    t = Image.open(p).convert("RGB").resize((PERIOD, PERIOD), Image.LANCZOS)
    arr = np.asarray(t, dtype=np.float32)
    lum = arr.mean(-1)
    busy = np.abs(np.diff(lum, axis=0)).mean() + np.abs(np.diff(lum, axis=1)).mean()  # detalhe que denuncia repetição
    tiles.append((arr, arr.reshape(-1, 3).mean(0), busy))


def components(mask):
    """componentes 4-conexos de um bool HxW: lista de (ys, xs)"""
    h, w = mask.shape
    seen = np.zeros_like(mask)
    out = []
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        q = deque([(y0, x0)])
        seen[y0, x0] = True
        ys, xs = [], []
        while q:
            y, x = q.popleft()
            ys.append(y)
            xs.append(x)
            for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not seen[yy, xx]:
                    seen[yy, xx] = True
                    q.append((yy, xx))
        out.append((np.array(ys), np.array(xs)))
    return out


def kmeans(X, k, it=12, seed=0):
    rng = np.random.default_rng(seed)
    C = X[rng.choice(len(X), size=min(k, len(X)), replace=False)]
    for _ in range(it):
        lab = ((X[:, None, :] - C[None]) ** 2).sum(-1).argmin(1)
        C = np.array([X[lab == i].mean(0) if (lab == i).any() else C[i] for i in range(len(C))])
    return C, lab


def restyle(img, cells):
    """cells = [(x0, y0)] cantos de cima-esquerda (imagem de cima pra baixo) das células 32x32 que o tilemap usa"""
    a = np.asarray(img.convert("RGBA")).astype(np.float32)
    outa = a.copy()
    C32 = lambda c: a[c[1]:c[1] + PERIOD, c[0]:c[0] + PERIOD]
    ground = [c for c in cells if (C32(c)[..., 3] > 0).mean() >= 0.5]
    deco = [c for c in cells if c not in ground and (C32(c)[..., 3] > 0).any()]
    if ground:  # classes de cor do chão do VS → textura de chão do RO mais parecida, coordenada relativa à célula
        # mesma quantidade de pixels por célula: o caminho de terra (poucas células) não some dentro do verde
        rng_s = np.random.default_rng(1)
        per = [C32(c)[C32(c)[..., 3] > 0][:, :3] for c in ground]
        sample = np.concatenate([p[rng_s.choice(len(p), size=min(64, len(p)), replace=False)] for p in per if len(p)])
        Cc, _ = kmeans(sample, K)
        # cor parecida e pouco detalhe: ladrilhada a cada 32 px, textura com pedra/folha marcada vira padrão visível
        # classes diferentes ficam com texturas diferentes (o caminho de terra não pode virar grama)
        score = lambda j, c: np.sqrt(((tiles[j][1] - c) ** 2).sum()) + 1.5 * tiles[j][2]
        pick, used = [None] * len(Cc), set()
        for i in sorted(range(len(Cc)), key=lambda i: -Cc[i].sum()):
            free = [j for j in range(len(tiles)) if j not in used] or list(range(len(tiles)))
            pick[i] = min(free, key=lambda j: score(j, Cc[i]))
            used.add(pick[i])
        for c in ground:
            blk = C32(c)
            lab = ((blk[..., :3][..., None, :] - Cc[None, None]) ** 2).sum(-1).argmin(-1)
            op = blk[..., 3] > 0
            if op.any():  # célula quase toda de uma classe vira uma textura só: pixel a pixel fazia manchas repetidas
                cnt = np.bincount(lab[op], minlength=len(Cc))
                if cnt.max() >= 0.8 * op.sum():
                    lab[:] = cnt.argmax()
            new = blk.copy()
            for i in range(len(Cc)):
                m = (lab == i) & (blk[..., 3] > 0)
                new[m, :3] = tiles[pick[i]][0][m]
            outa[c[1]:c[1] + PERIOD, c[0]:c[0] + PERIOD] = new
    # decoração: células vizinhas no grid de 34 px formam um objeto; monta sem o padding, troca, devolve
    pitch = PERIOD + 2
    gx = {c: round((c[0] - min(x for x, _ in cells)) / pitch) for c in deco}
    gy = {c: round((c[1] - min(y for _, y in cells)) / pitch) for c in deco}
    left, groups = set(deco), []
    while left:
        st = [left.pop()]
        g = []
        while st:
            c = st.pop()
            g.append(c)
            for o in list(left):
                if abs(gx[o] - gx[c]) <= 1 and abs(gy[o] - gy[c]) <= 1:
                    left.remove(o)
                    st.append(o)
        groups.append(g)
    rng = random.Random(TEXNAME)
    nprops = 0
    for g in groups:
        mx, my = min(gx[c] for c in g), min(gy[c] for c in g)
        cw, ch = max(gx[c] for c in g) - mx + 1, max(gy[c] for c in g) - my + 1
        canv = np.zeros((ch * PERIOD, cw * PERIOD, 4), np.float32)
        for c in g:
            canv[(gy[c] - my) * PERIOD:(gy[c] - my + 1) * PERIOD, (gx[c] - mx) * PERIOD:(gx[c] - mx + 1) * PERIOD] = C32(c)
        newc = np.zeros_like(canv)
        for ys, xs in components(canv[..., 3] > 0):
            if len(ys) < 12 or not props:
                continue
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            asp = (y1 - y0) / (x1 - x0)
            pr = rng.choice(sorted(props, key=lambda p: abs(p.height / p.width - asp))[:3])
            sc = min((x1 - x0) / pr.width, (y1 - y0) / pr.height)
            pr = retro(pr, sc) if sc < 1 else pr.resize((max(1, round(pr.width * sc)), max(1, round(pr.height * sc))), Image.NEAREST)
            pa = np.asarray(pr).astype(np.float32)
            px, py = x0 + ((x1 - x0) - pr.width) // 2, y1 - pr.height
            reg = newc[py:py + pr.height, px:px + pr.width]
            reg[:] = np.where(pa[..., 3:4] > 0, pa, reg)
            nprops += 1
        for c in g:
            outa[c[1]:c[1] + PERIOD, c[0]:c[0] + PERIOD] = newc[(gy[c] - my) * PERIOD:(gy[c] - my + 1) * PERIOD,
                                                                (gx[c] - mx) * PERIOD:(gx[c] - mx + 1) * PERIOD]
    for c in cells:  # padding de 1 px em volta de cada célula = borda estendida (sem sangrar o vizinho no filtro)
        x0, y0 = c
        H, W = outa.shape[:2]
        if y0 > 0: outa[y0 - 1, x0:x0 + PERIOD] = outa[y0, x0:x0 + PERIOD]
        if y0 + PERIOD < H: outa[y0 + PERIOD, x0:x0 + PERIOD] = outa[y0 + PERIOD - 1, x0:x0 + PERIOD]
        if x0 > 0: outa[max(0, y0 - 1):y0 + PERIOD + 1, x0 - 1] = outa[max(0, y0 - 1):y0 + PERIOD + 1, x0]
        if x0 + PERIOD < W: outa[max(0, y0 - 1):y0 + PERIOD + 1, x0 + PERIOD] = outa[max(0, y0 - 1):y0 + PERIOD + 1, x0 + PERIOD - 1]
    return Image.fromarray(outa.clip(0, 255).astype(np.uint8)), len(ground), nprops


def cells_of(b, tex_obj, H):
    """células do tilemap: sprites deste atlas com nome st2u_x<X>y<Y>-w32h32 (canto de baixo-esquerda, Unity)"""
    import re
    out = set()
    for _, f in b.serialized():
        for o in f.objects.values():
            if o.type.name != "Sprite":
                continue
            t = o.read_typetree()
            if t["m_RD"]["texture"]["m_PathID"] != tex_obj.path_id:
                continue
            m = re.search(r"x(\d+)y(\d+)-w(\d+)h(\d+)", t["m_Name"])
            if m and int(m.group(3)) == PERIOD:
                x, y = int(m.group(1)), int(m.group(2))
                out.add((x, H - y - PERIOD))
            else:  # sprite sem o padrão: só conta como célula se tiver o tamanho de um tile
                r = t["m_Rect"]
                if abs(r["width"] - PERIOD) <= 2 and abs(r["height"] - PERIOD) <= 2:
                    out.add((int(r["x"]), H - int(r["y"]) - PERIOD))
    return sorted(out)


def texture_index():
    """{nome da textura: [bundles]} do romfs, calculado uma vez (varrer os 1166 bundles leva minutos)"""
    import json
    cache = work("texture_index.json")
    if os.path.exists(cache):
        return json.load(open(cache))
    idx = {}
    import UnityPy
    for bn in sorted(os.listdir(f"{romfs}/{AA}")):
        if not bn.endswith(".bundle") or bn.startswith(("vs_local_assets_bgm", "vs_local_assets_thosepeople")):
            continue
        try:
            for o in UnityPy.load(f"{romfs}/{AA}/{bn}").objects:
                if o.type.name == "Texture2D":
                    idx.setdefault(o.read().m_Name, []).append(bn)
        except Exception:
            pass
    json.dump(idx, open(cache, "w"))
    return idx


done = []
from mapping import texture_index as _tidx
for bn in _tidx(romfs, AA).get(TEXNAME, []):
    src = f"{out}/{AA}/{bn}" if os.path.exists(f"{out}/{AA}/{bn}") else f"{romfs}/{AA}/{bn}"
    try:
        b = Bundle(src)
    except Exception:
        continue
    hits = [o for _, f in b.serialized() for o in f.objects.values()
            if o.type.name == "Texture2D" and o.read().m_Name == TEXNAME]
    for o in hits:
        im = o.read().image
        cells = cells_of(b, o, im.height)
        if not cells:  # fundo inteiro (bg_molise, bg_water…), sem tiles: grade de 32 px sobre a imagem toda
            cells = [(x, y) for y in range(0, im.height - PERIOD + 1, PERIOD) for x in range(0, im.width - PERIOD + 1, PERIOD)]
        new, g, d = restyle(im, cells)
        b.replace_texture(o, new)
        done.append(f"{bn.replace('vs_local_assets_', '')}({g} células de chão, {d} props)")
    if hits:
        os.makedirs(f"{out}/{AA}", exist_ok=True)
        b.save(f"{out}/{AA}/{bn}")
print("ok", TEXNAME, "←", ",".join(maps), f"({len(ground_tex)} chãos, {len(props)} props):", "; ".join(done) or "nada")
