#!/usr/bin/env python3
# Efeitos do RO em quadros: ro_frames(ref) dá os quadros soltos (reskin_vfx encaixa nos sprites do VS) e seq(ref)
# a animação inteira alinhada. Rodado como script, monta o atlas "rofx" do tocador de quadros do hook (main.cpp,
# ProjectileFx): cada entrada de ro_fx (characters_weapons.yaml) vira sprites rofx_<sprite do VS>_NN numa textura
# nova do resources.assets, registrada no ResourceManager sob spritesheets/rofx (o SpriteManager carrega a pasta
# spritesheets inteira e acha sprite pelo nome), e o exl/source/program/rofx_table.inc diz ao hook quantos quadros
# e a que fps. O projétil continua do VS (movimento, hitbox, tempo); só a imagem anima com a do RO.
# uso: python3 -P tools/rofx.py <romfs> <overlay>   (depois do reskin_vfx; lê e grava o data.unity3d do overlay)
import sys, os, glob, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -P tira a pasta do script do path
from paths import RAG
from PIL import Image
from rosprite import retro, compose, effect_sprites, MONSTER, HUMAN
from roact import read_act
from roicons import ro_icon, load_icon

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def effect_frames(name):
    """imagens de sprite/이팩트/<name>.spr (as RGBA já saem com os canais e a orientação certos: tools/rospr.py)"""
    return effect_sprites(name)


def ring(name, n=8, size=64):
    """'ring jong': n cópias das texturas texture/effect/<name>_a.._d.bmp (fundo preto = soma no STR do RO) em
    círculo, num quadro size×size — o escudo do Kyrie (sinos) no lugar do anel do Laurel, que o jogo já gira."""
    import math
    fx = f"{RAG}/texture/effect"
    tex = [Image.open(p).convert("RGB") for p in sorted(glob.glob(f"{fx}/{name}_[a-z].bmp"))]
    out = Image.new("RGBA", (size, size))
    bell = size * 7 // 32
    for i in range(n):
        im = tex[i % len(tex)]
        im = im.crop(im.point(lambda v: 255 if v > 40 else 0).convert("L").getbbox())
        a = im.convert("L").point(lambda v: 255 if v > 40 else 0)
        im = im.convert("RGBA"); im.putalpha(a)
        im = retro(im, bell / max(im.size))
        ang = 2 * math.pi * i / n
        cx = size / 2 + (size / 2 - bell / 2 - 1) * math.cos(ang)
        cy = size / 2 + (size / 2 - bell / 2 - 1) * math.sin(ang)
        out.alpha_composite(im, (round(cx - im.width / 2), round(cy - im.height / 2)))
    return [out]


def ro_frames(ref):
    kind, name = ref.split(None, 1)
    name = name.split("#")[0].strip()
    if kind == "ring":
        return ring(name)
    if kind == "minimap":  # "minimap odin_tem01" = minimapa do RO (texture/유저인터페이스/map/<mapa>.bmp)
        ui = f"{RAG}/texture/" + "유저인터페이스".encode("cp949").decode("latin1")
        im = Image.open(f"{ui}/map/{name}.bmp").convert("RGB")
        im.putdata([(24, 22, 30) if c[0] > 240 and c[1] < 20 and c[2] > 240 else c for c in im.get_flattened_data()])
        return [im.convert("RGBA")]
    if kind == "tex":  # "tex round_sphere" = texture/effect/<nome>.bmp desenhada em modo aditivo: preto = transparente
        im = Image.open(f"{RAG}/texture/effect/{name}.bmp").convert("RGB")
        out = im.convert("RGBA")
        out.putalpha(im.convert("L").point(lambda v: 0 if v < 16 else min(255, v)))
        return [out]
    if kind == "str":  # "str kyrie 22" = quadro 22 do texture/effect/kyrie.str (efeito 3D), quadrado no centro do efeito
        from rostr import render, RAG as _R
        nm, fr, *only = name.split() + ([] if len(name.split()) > 1 else ["30"])
        im = render(f"{_R}/texture/effect/{nm}.str", int(fr), only=only or None)  # "str kyrie 22 ring_b"
        bb = im.getchannel("A").point(lambda v: 255 if v > 96 else 0).getbbox()  # partículas soltas ficam fora
        if not bb:
            return []
        cx, cy, r = (bb[0] + bb[2]) // 2, (bb[1] + bb[3]) // 2, max(bb[2] - bb[0], bb[3] - bb[1]) // 2 + 2
        return [im.crop((cx - r, cy - r, cx + r, cy + r))]
    if kind in ("monster", "npc"):  # "monster snake 1 6" = ação 1 (andar), direção 6 (leste: o VS desenha de lado)
        bits = name.split()
        name, action, d = bits[0], int(bits[1]) if len(bits) > 1 else 0, int(bits[2]) if len(bits) > 2 else 6
        act = f"{MONSTER}/{name}.act" if kind == "monster" else f"{HUMAN}/../npc/{name}.act"
        parts = [act]
        n = len(read_act(act)[1][action * 8 + d])
        fr = [compose(parts, action * 8 + d, m, crop=False, size=512) for m in range(n)]
        boxes = [f.getbbox() for f in fr if f.getbbox()]
        U = (min(x[0] for x in boxes), min(x[1] for x in boxes), max(x[2] for x in boxes), max(x[3] for x in boxes))
        return [f.crop(U) for f in fr]
    if kind == "item":
        p = ro_icon(f"item {name}")
        return [load_icon(p)] if p else []
    return [i.crop(i.getbbox()) for i in effect_frames(name) if i.getbbox()]


def seq(ref, fps):
    """animação inteira, quadros alinhados (recorte pela união): "effect X" (sprite de efeito, quadro a quadro) ou
    "str X" (efeito STR a 60 fps amostrado em fps); o resto cai em ro_frames"""
    kind, name = ref.split(None, 1)
    if kind == "effect":
        frs = effect_frames(name)
    elif kind == "str":
        from rostr import render, read_str, RAG as _R
        p = f"{_R}/texture/effect/{name}.str"
        _, maxkey, _ = read_str(p)
        frs = [render(p, f, size=1024) for f in range(0, maxkey, max(1, round(60 / fps)))]
    else:
        return ro_frames(ref)
    # o STR começa vazio ou quase (o raio ainda não desceu): projétil curto só tocaria o vazio
    mass = [sum(f.getchannel("A").point(lambda v: v > 64 and 255).histogram()[255:]) for f in frs]
    while len(frs) > 1 and mass[0] < 0.15 * max(mass):
        frs, mass = frs[1:], mass[1:]
    boxes = [f.getbbox() for f in frs if f.getbbox()]
    U = (min(x[0] for x in boxes), min(x[1] for x in boxes), max(x[2] for x in boxes), max(x[3] for x in boxes))
    return [f.crop(U) for f in frs]


def pack(ims, width):
    """prateleiras: [(x, y)] de cima pra baixo e a altura usada (1 px de folga entre quadros)"""
    pos, x, y, row = [], 0, 0, 0
    for im in ims:
        if x + im.width > width:
            x, y, row = 0, y + row + 1, 0
        pos.append((x, y))
        x, row = x + im.width + 1, max(row, im.height)
    return pos, y + row


if __name__ == "__main__":
    import yaml
    from unitypatch import Bundle, typetree_bytes
    from rosprite import quad_vertices
    romfs, out = sys.argv[1:3]
    REL = "Data/data.unity3d"
    CAP = 128  # lado maior de um quadro no atlas, em px
    MAXF = 48  # = g_fxFrame[][48] em main.cpp
    FX = yaml.safe_load(open(f"{ROOT}/mapping/characters_weapons.yaml"))["ro_fx"]
    b = Bundle(os.path.join(out, REL) if os.path.exists(os.path.join(out, REL)) else os.path.join(romfs, REL))
    files = dict(b.serialized())
    res, gg = files["resources.assets"], files["globalgamemanagers"]
    objs = list(res.objects.values())
    assert not any(o.type.name == "Texture2D" and o.read().m_Name == "rofx" for o in objs), "rofx já existe"
    vfx = next(o for o in objs if o.type.name == "Texture2D" and o.read().m_Name == "vfx")
    tpl = next(o for o in objs if o.type.name == "Sprite" and o.read().m_Name == "ProjectileFireball")

    frames, table = [], []
    for cls, e in FX.items():
        fps = e.get("fps", 12)
        frs = seq(e["ref"], fps)
        if len(frs) > MAXF:  # o hook guarda MAXF quadros por efeito: pula quadros e baixa o fps junto (mesma duração)
            step = -(-len(frs) // MAXF)
            frs, fps = frs[::step], max(1, round(fps / step))
        if e.get("rot"):
            frs = [f.rotate(e["rot"], Image.BICUBIC, expand=True) for f in frs]
        m = max(max(f.size) for f in frs)
        if m > CAP:  # STR inteiro tem 400-600 px: a densidade não passa de CAP/size
            frs = [f.resize((max(1, round(f.width * CAP / m)), max(1, round(f.height * CAP / m))), Image.LANCZOS)
                   for f in frs]
            m = CAP
        k = e["size"] / m  # px do mundo do VS por px do quadro: a malha leva o quadro ao tamanho do sprite do VS
        pre = f"rofx_{cls}_"
        py = e.get("py", 0.5)  # pivô vertical (0 = embaixo: o raio do RO cai no ponto do impacto)
        frames += [(f"{pre}{i + 1:02d}", f, k, py) for i, f in enumerate(frs)]
        fl = e.get("field", 0x80)
        fl = (list(fl) if isinstance(fl, list) else [fl]) + [0]
        hide = list(e.get("hide", [])) + [0, 0]
        loop = "true" if e.get("loop", True) else "false"
        table.append(f'    {{"{cls}", "{pre}", {len(frs)}, {fps}, {loop}, {hex(fl[0])}, {hex(fl[1])}, '
                     f'{float(e.get("alpha", 0))}f, {hex(hide[0])}, {hex(hide[1])}}},')
        print(f"   {cls}: {len(frs)} quadros {frs[0].size} ×{k:.3f} ← {e['ref']}")
    W = 2048
    pos, h = pack([f for _, f, _, _ in frames], W)
    H = 1 << max(6, (h - 1).bit_length())
    atlas = Image.new("RGBA", (W, H))
    for (_, f, _, _), p in zip(frames, pos):
        atlas.paste(f, p)

    rng_pid = max(o.path_id for o in objs) + 1
    tex_pid = rng_pid
    tt = vfx.read_typetree()
    px = atlas.transpose(Image.FLIP_TOP_BOTTOM).tobytes()
    tt.update({"m_Name": "rofx", "m_Width": W, "m_Height": H, "m_TextureFormat": 4, "m_MipCount": 1,
               "m_IsPreProcessed": False, "m_CompleteImageSize": len(px), "image data": px})
    tt["m_PlatformBlob"] = type(tt["m_PlatformBlob"])()
    tt["m_StreamData"] = {**tt["m_StreamData"], "offset": 0, "size": 0, "path": ""}
    new = [(tex_pid, list(res.types).index(vfx.serialized_type), typetree_bytes(vfx, tt))]
    t0 = tpl.read_typetree()
    for i, ((name, f, k, py), (x, y)) in enumerate(zip(frames, pos)):
        # PPU 100·d+1 = marca do hook SpriteRect (o código do VS vê o rect em 1×) quando o quadro é d≥2 vezes mais
        # denso que o mundo; abaixo disso o rect fica como está (só a malha decide o tamanho desenhado)
        d = round(1 / k)
        ppu = 100 * d + 1 if d >= 2 else 100
        t = copy.deepcopy(t0)
        w, hh = f.size
        r = {"x": float(x), "y": float(H - y - hh), "width": float(w), "height": float(hh)}  # Unity: origem embaixo
        t.update({"m_Name": name, "m_Rect": r, "m_Offset": {"x": 0.0, "y": 0.0}, "m_Pivot": {"x": 0.5, "y": py},
                  "m_PixelsToUnits": float(ppu)})
        rd = t["m_RD"]
        rd["texture"] = {"m_FileID": 0, "m_PathID": tex_pid}
        rd["textureRect"] = dict(r)
        rd["textureRectOffset"] = {"x": 0.0, "y": 0.0}
        rd["uvTransform"] = {"x": float(ppu), "y": x + w / 2, "z": float(ppu), "w": r["y"] + hh / 2}
        vd = rd["m_VertexData"]
        vd["m_DataSize"] = type(vd["m_DataSize"])(quad_vertices(w * k, hh * k, 0.5, py))
        key, _ = t["m_RenderDataKey"]
        t["m_RenderDataKey"] = (key, 0x524F0000 + i)
        new.append((tex_pid + 1 + i, list(res.types).index(tpl.serialized_type), typetree_bytes(tpl, t)))

    # ResourceManager (globalgamemanagers): spritesheets/rofx → textura e sprites; sprite depende da textura
    rm = next(o for o in gg.objects.values() if o.type.name == "ResourceManager")
    rt = rm.read_typetree()
    fid = [e.path.rsplit("/", 1)[-1] for e in gg.externals].index("resources.assets") + 1
    ptr = lambda p: {"m_FileID": fid, "m_PathID": p}
    rt["m_Container"] = sorted(rt["m_Container"] + [("spritesheets/rofx", ptr(p)) for p, _, _ in new],
                               key=lambda kv: kv[0])
    dep = rt["m_DependentAssets"]
    was_sorted = dep == sorted(dep, key=lambda d: (d["m_Object"]["m_FileID"], d["m_Object"]["m_PathID"]))
    dep += [{"m_Object": ptr(p), "m_Dependencies": [ptr(tex_pid)]} for p, _, _ in new[1:]]
    if was_sorted:
        dep.sort(key=lambda d: (d["m_Object"]["m_FileID"], d["m_Object"]["m_PathID"]))
    b.replace_object("globalgamemanagers", rm, typetree_bytes(rm, rt))
    b.add_objects("resources.assets", new)
    os.makedirs(os.path.dirname(os.path.join(out, REL)), exist_ok=True)
    print("ok", REL, b.save(os.path.join(out, REL)), f"atlas rofx {W}x{H}, {len(frames)} quadros, {len(FX)} efeitos")
    inc = os.path.join(ROOT, "exl/source/program/rofx_table.inc")
    open(inc, "w").write("// gerado por tools/rofx.py (ro_fx em mapping/characters_weapons.yaml): não editar\n"
                         + "\n".join(table) + "\n")
    atlas.save(os.path.join(out, "preview_rofx.png"))
