#!/usr/bin/env python3
# Troca todos os inimigos de um atlas do VS pelos monstros do RO de mapping/enemies.yaml.
# Por família (prefixo do VS): <p>/<p>_0/<p>_iNN = andar do RO (ação 1, direção 6 = leste: o VS desenha olhando pra
# direita e espelha); <p>_1.._N = morte do RO (ação 4) e depois um "esfarelar" que tira pixels do último quadro, como
# a dissolução do VS. Os quadros únicos vão numa faixa nova em cima do atlas (rects do Unity são medidos de baixo,
# os antigos continuam valendo) e vários sprites do VS podem apontar pro mesmo quadro.
# Tamanho: o raio do hitbox do inimigo sai da largura do sprite inicial × escala (medido: Familiar 46 px × 0,5 →
# 0,092 = 0,4 × 23). A arte do RO entra com até 2× a densidade do VS (RT 2×) e o ENEMY_DATA.scale é multiplicado
# pra largura na tela voltar à do sprite do VS: mesmo hitbox, monstro do RO.
# Saída extra: <overlay>/enemy_scales.json {ENEMY_ID: multiplicador}, que o patch_data.py aplica.
# uso: python3 -P tools/reskin_enemies.py <romfs> <overlay> <bundle> [família ...]
import sys, os, re, json, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -P tira a pasta do script do path
import yaml
from PIL import Image
from unitypatch import Bundle, typetree_bytes
from rosprite import compose, retro, quad_vertices, MONSTER, effect_sprites
from roact import read_act

romfs, out, bundle_name = sys.argv[1:4]
ONLY = set(sys.argv[4:])
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
AA = os.environ.get("VS_AA", "Data/StreamingAssets/aa/Switch")  # DLC: "" (bundles na raiz do romfs)
REL = os.path.join(AA, bundle_name)
from mapping import vs_data, section, dict_section
WALK, DIE, EAST = 1, 4, 6
DENSITY = 2          # RT do mundo 2× (hook HIRES): até 2 pixels do RO por pixel do VS
MAX_W = 96           # memória: monstro grande/chefe fica com a largura do VS (≥1×) ou até 96 px de arte
DISSOLVE = (0.35, 0.65, 0.9)  # fração de pixels removidos nos quadros finais da morte
DIE_FRAMES = 4                # quadros da morte do RO amostrados (o resto do tempo é o esfarelar)
PAD = 2

b = Bundle(os.path.join(romfs, REL))
fname, f, tex = next((n, ff, o) for n, ff in b.serialized() for o in ff.objects.values()
                     if o.type.name == "Texture2D")
TEXNAME = tex.read().m_Name.lower()
sprites = {o.read_typetree()["m_Name"]: o for o in f.objects.values() if o.type.name == "Sprite"
           and o.read_typetree()["m_RD"]["texture"]["m_PathID"] == tex.path_id}
enemy_data = vs_data("ENEMY")
# família entra em todo atlas que tem os sprites dela (Bat3, Bat2… têm cópias em mais de um atlas); se o mapping
# repetir a família, vence a linha cujo vs_texture é este atlas, senão a 1ª
fams, seen = [], {}
for x in section("enemies"):
    P = x["vs_family"]
    if (not x.get("ro_sprite") or x.get("role") == "projectile" or (ONLY and P not in ONLY)
            or not (f"{P}_0" in sprites or P in sprites)):
        continue
    if P in seen and (seen[P].get("vs_texture") or "").lower() == TEXNAME:
        continue
    if P in seen:
        fams.remove(seen[P])
    seen[P] = x
    fams.append(x)
# variantes: o jogo sorteia um dos frameNames a cada spawn (SKELETON = Skeleton1..6, ZOMBIE = Ghoul1..3). Cada variante
# sem linha própria no mapping recebe o monstro da família; sem vs_ids = sem escala própria (a do inimigo vem da principal)
POOLS = dict_section("ro_variant_pools")
OVERRIDES = dict_section("ro_variant_overrides")  # variante com monstro fixo (Flower2 = planta)
# todas as famílias do mapping, não só as presentes neste atlas: o "enemies" tem Skeleton2..6 sem o Skeleton1
# (a mesma família pode ter várias linhas: Skeleton1 = SKETAMARI e SKELETON)
for x in [y for y in section("enemies") if y.get("ro_sprite") and y.get("role") != "projectile"]:
    k = 0
    for vid in x.get("vs_ids") or []:
        for fn in (enemy_data.get(vid) or [{}])[0].get("frameNames") or []:
            V = re.sub(r"_0\.png$", "", fn)
            if V not in seen and (f"{V}_0" in sprites or V in sprites) and not (ONLY and x["vs_family"] not in ONLY):
                pool = POOLS.get(x["ro_sprite"]) or [x["ro_sprite"]]
                sp = OVERRIDES.get(V) or pool[k % len(pool)]
                seen[V] = {**x, "vs_family": V, "vs_ids": [], "ro_sprite": sp, "_main": x["vs_family"]}
                fams.append(seen[V])
                k += 1


def sample(xs, n):
    """n quadros espalhados de xs (sempre inclui o último quando n > 1)"""
    if n >= len(xs):
        return xs
    return [xs[round(i * (len(xs) - 1) / max(1, n - 1))] for i in range(n)]


_cache = {}


def ro_frames(mob, action):
    parts = [f"{MONSTER}/{mob}.act"]
    acts = read_act(parts[0])[1]
    a = action if action * 8 + EAST < len(acts) and acts[action * 8 + EAST] else 0
    n = len(acts[a * 8 + EAST])
    canv = [compose(parts, a * 8 + EAST, m, crop=False, size=512) for m in range(n)]
    boxes = [c.getbbox() for c in canv if c.getbbox()]
    U = (min(x[0] for x in boxes), min(x[1] for x in boxes), max(x[2] for x in boxes), max(x[3] for x in boxes))
    # o sprite do VS olha pra esquerda (o jogo espelha quando o inimigo anda pra direita); o RO leste olha pra direita
    # (Zero, 16/10: "eles vem de costas pra minha direção") → espelhado
    return [c.crop(U).transpose(Image.FLIP_LEFT_RIGHT) for c in canv]


def dissolve(im, frac, seed):
    rng = random.Random(seed)
    a = im.getchannel("A")
    a.putdata([0 if rng.random() < frac else v for v in a.get_flattened_data()])
    out = im.copy()
    out.putalpha(a)
    return out


uniq, assign, scales, report, main_ww = [], {}, {}, [], {}  # uniq = quadros únicos; assign = nome do sprite VS -> índice
for fam in fams:
    P = fam["vs_family"]
    # o SpriteManager do jogo não diferencia caixa (JoyaTauro_Y_0 + JOYATAURO_Y_i01 = o mesmo inimigo)
    names = [n for n in sprites if n.lower() == P.lower() or re.fullmatch(re.escape(P) + r"_(\d+|i\d+|d\d+)", n, re.I)]
    first = sprites.get(f"{P}_0") or sprites.get(P)
    if not first:
        report.append(f"{P}: sem {P}_0 no atlas, pulado")
        continue
    w0 = first.read_typetree()["m_Rect"]["width"]
    idle = sorted(n for n in names if re.fullmatch(re.escape(P) + r"_i\d+", n, re.I))
    key = (fam["ro_sprite"], w0, len(idle), fam.get("_main"), fam.get("ro_art_scale"))
    if key not in _cache:  # mesmo monstro do RO em duas famílias do mesmo tamanho: quadros compartilhados
        walk = sample(ro_frames(fam["ro_sprite"], WALK), max(1, len(idle)))
        die = sample(ro_frames(fam["ro_sprite"], DIE), DIE_FRAMES)
        r = min(1.0, DENSITY * w0 / walk[0].width, max(w0, MAX_W) / walk[0].width)
        if fam.get("_main") in main_ww:  # variante: mesma largura de arte da principal (a escala é do inimigo, uma só)
            r = main_ww[fam["_main"]] / walk[0].width
        walk = [retro(x, r) for x in walk]
        die = [retro(x, r) for x in die]
        f = float(fam.get("ro_art_scale") or 1)
        if f != 1 and fam.get("ro_art_min"):  # tamanho mínimo na tela (largura do VS × f): morcego pequeno = poring minúsculo
            f = min(1.0, max(f, float(fam["ro_art_min"]) / w0))
        if f != 1:  # arte menor dentro do mesmo quadro: a escala do inimigo (e o hitbox) segue a do VS
            def shrink(x):
                y = retro(x, f)
                c = Image.new("RGBA", x.size)
                c.paste(y, ((x.width - y.width) // 2, x.height - y.height), y)
                return c
            walk, die = [shrink(x) for x in walk], [shrink(x) for x in die]
        tail = [dissolve(die[-1], q, i) for i, q in enumerate(DISSOLVE)]
        base = len(uniq)
        uniq += walk + die + tail
        _cache[key] = (range(base, base + len(walk)), range(base + len(walk), len(uniq)), walk[0].width)
    W, D, ww = _cache[key]
    main_ww.setdefault(P, ww)
    death = sorted((n for n in names if re.fullmatch(re.escape(P) + r"_\d+", n, re.I) and n.lower() != f"{P}_0".lower()),
                   key=lambda n: int(n.rsplit("_", 1)[1]))
    for n in (P, f"{P}_0"):
        if n in sprites:
            assign[n] = W[0]
    for i, n in enumerate(idle):
        assign[n] = W[i * len(W) // len(idle)]
    for i, n in enumerate(death):  # morte esticada no tempo do VS: quadros do RO, depois o esfarelar
        assign[n] = D[min(len(D) - 1, i * len(D) // max(1, len(death)))]
    dalt = sorted(n for n in names if re.fullmatch(re.escape(P) + r"_d\d+", n, re.I))  # 2ª morte do VS (_d00..): a mesma
    for i, n in enumerate(dalt):
        assign[n] = D[min(len(D) - 1, i * len(D) // max(1, len(dalt)))]
    s = w0 / ww
    for vid in fam.get("vs_ids") or []:  # escala só de quem desenha deste atlas (a família pode estar em vários)
        if vid in enemy_data and (enemy_data[vid][0].get("textureName") or "").lower() == TEXNAME:
            scales[vid] = round(s, 4)
    report.append(f"{P} -> {fam['ro_sprite']}: {len(W)} andar, {len(D)} morte+esfarelar, densidade {ww / w0:.2f}, "
                  f"escala ×{s:.3f}, sprites {len([n for n in assign if n == P or n.startswith(P + '_')])}")

# projéteis de inimigo (ro_effect no mapping): ficam no lugar, só trocam os pixels
PROJ = {x["vs_family"]: x["ro_effect"] for x in section("enemies")
        if x.get("ro_effect")}
_pcache = {}


def proj_frames(ref):
    if ref not in _pcache:
        import glob
        from roicons import ro_icon, load_icon
        kind, name = ref.split(None, 1)
        if kind == "item":
            p = ro_icon(f"item {name}")
            _pcache[ref] = [load_icon(p)] if p else []
        else:
            ims = effect_sprites(name)
            _pcache[ref] = [i.crop(i.getbbox()) for i in ims if i.getbbox()]
    return _pcache[ref]


# atlas refeito do zero: só os quadros novos + os sprites do VS que não foram trocados (projéteis, extras). A arte
# antiga dos inimigos trocados não é mais desenhada; mantê-la custava ~+130 MB de textura somando os 7 atlases.
src = tex.read().image.convert("RGBA")  # de cima pra baixo
keep, keep_im = {}, []  # textureRect (Unity, de baixo) -> índice em keep_im; vários sprites podem dividir o rect
for n, o in sprites.items():
    if n in assign:
        continue
    tr = o.read_typetree()["m_RD"]["textureRect"]
    k = tuple(round(tr[a]) for a in ("x", "y", "width", "height"))
    if k not in keep and k[2] > 0 and k[3] > 0:
        keep[k] = len(keep_im)
        im = src.crop((k[0], src.height - k[1] - k[3], k[0] + k[2], src.height - k[1]))
        pf = next((P for P in PROJ if n == P or re.fullmatch(re.escape(P) + r"_?(i)?\d+", n)), None)
        if pf:  # projétil de inimigo: mesmo rect, pixels do efeito/item do RO
            frs = proj_frames(PROJ[pf])
            fr = frs[int((re.findall(r"\d+", n) or ["0"])[-1]) % len(frs)] if frs else None
            if fr is not None:
                fr = retro(fr, min(1.0, im.width / fr.width, im.height / fr.height))
                im = Image.new("RGBA", im.size)
                im.alpha_composite(fr, ((im.width - fr.width) // 2, (im.height - fr.height) // 2))
        keep_im.append(im)
allim = uniq + keep_im
x = y = shelf = 0
pos = [None] * len(allim)
for i in sorted(range(len(allim)), key=lambda i: -allim[i].height):  # prateleiras por altura: menos sobra
    im = allim[i]
    if x + im.width + PAD > src.width:
        x, y, shelf = 0, y + shelf + PAD, 0
    pos[i] = (x, y)
    x += im.width + PAD
    shelf = max(shelf, im.height)
atlas = Image.new("RGBA", (src.width, (y + shelf + PAD + 3) // 4 * 4))
for im, (px, py) in zip(allim, pos):
    atlas.paste(im, (px, py))
add_h = atlas.height - src.height

for n, i in assign.items():  # sprites trocados: apontam pro quadro do RO, pivô no centro
    o = sprites[n]
    t = o.read_typetree()
    im, (px, py) = uniq[i], pos[i]
    rect = {"x": float(px), "y": float(atlas.height - py - im.height), "width": float(im.width), "height": float(im.height)}
    t["m_Rect"] = dict(rect)
    t["m_RD"]["textureRect"] = dict(rect)
    t["m_Pivot"] = {"x": 0.5, "y": 0.5}
    t["m_Offset"] = {"x": 0.0, "y": 0.0}
    t["m_RD"]["textureRectOffset"] = {"x": 0.0, "y": 0.0}
    t["m_RD"]["uvTransform"] = {"x": 100.0, "y": rect["x"] + im.width / 2, "z": 100.0, "w": rect["y"] + im.height / 2}
    t["m_RD"]["m_VertexData"]["m_DataSize"] = quad_vertices(im.width, im.height)
    b.replace_object(fname, o, typetree_bytes(o, t))

for n, o in sprites.items():  # sprites mantidos: mesmo desenho, só desloca rect/textureRect/uv
    if n in assign:
        continue
    t = o.read_typetree()
    tr = t["m_RD"]["textureRect"]
    k = tuple(round(tr[a]) for a in ("x", "y", "width", "height"))
    if k not in keep:
        continue
    px, py = pos[len(uniq) + keep[k]]
    dx, dy = px - tr["x"], (atlas.height - py - k[3]) - tr["y"]
    t["m_Rect"] = {**t["m_Rect"], "x": t["m_Rect"]["x"] + dx, "y": t["m_Rect"]["y"] + dy}
    t["m_RD"]["textureRect"] = {**tr, "x": tr["x"] + dx, "y": tr["y"] + dy}
    uv = t["m_RD"]["uvTransform"]
    t["m_RD"]["uvTransform"] = {**uv, "y": uv["y"] + dx, "w": uv["w"] + dy}
    b.replace_object(fname, o, typetree_bytes(o, t))

tt = tex.read_typetree()
res = tt["m_StreamData"]["path"].rsplit("/", 1)[-1]
assert tt["m_StreamData"]["offset"] == 0 and len(b.raw[res]) == tt["m_StreamData"]["size"], "resS com mais coisa"
if tt["m_TextureFormat"] != 4 or tt.get("m_PlatformBlob"):  # enemies3/enemies2023 vêm ASTC swizzled: vira RGBA32 linear
    tt["m_TextureFormat"], tt["m_IsPreProcessed"], tt["m_PlatformBlob"] = 4, False, type(tt["m_PlatformBlob"])()
px = atlas.transpose(Image.FLIP_TOP_BOTTOM).tobytes()
tt["m_Height"] = atlas.height
tt["m_CompleteImageSize"] = tt["m_StreamData"]["size"] = len(px)
b.raw[res] = bytearray(px)
b.replace_object(fname, tex, typetree_bytes(tex, tt))

dst = os.path.join(out, REL)
os.makedirs(os.path.dirname(dst), exist_ok=True)
size = b.save(dst)
sp = os.path.join(out, "enemy_scales.json")
allsc = json.load(open(sp)) if os.path.exists(sp) else {}
allsc.update(scales)
json.dump(allsc, open(sp, "w"), indent=0, sort_keys=True)
print("\n".join(report))
print(f"ok {REL} {size} B, atlas {atlas.size} (+{add_h} linhas), {len(fams)} famílias, {len(uniq)} quadros, "
      f"{len(assign)} sprites, {len(keep)} rects do VS mantidos, {len(scales)} escalas")
