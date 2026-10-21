#!/usr/bin/env python3
# Composição de quadros do RO (.spr + .act crus, lidos do data.grf extraído) e tratamento retro.
import struct
from PIL import Image, ImageDraw
from roact import read_act
from rospr import read_spr, read_spr_typed

from paths import RAG
RAW = f"{RAG}/sprite"           # nomes cp949 lidos como latin1
HUMAN, MONSTER = f"{RAW}/ÀÎ°£Á·", f"{RAW}/¸ó½ºÅÍ"                   # 인간족, 몬스터


def effect_sprites(name):
    """imagens de sprite/이팩트/<name>.spr na ordem do arquivo"""
    k = lambda t: t.encode("cp949").decode("latin1")
    return read_spr(f"{RAW}/{k('이팩트')}/{k(name)}.spr")


def _layer(act, lay):
    im = read_spr_typed(act[:-4] + ".spr")[lay.get("type", 0) == 1][lay["spr"]]
    return im.transpose(Image.FLIP_LEFT_RIGHT) if lay["mirror"] else im


def compose(parts, act_index, motion, shadow=False, crop=True, size=256):
    """parts = [act_path, ...] (o .spr fica ao lado); a 1ª é o corpo, as outras encaixam pelos attach points.
    Devolve o quadro recortado no conteúdo (crop=False: tela size² inteira, origem do RO fixa em (size/2, size-40))."""
    acts = [read_act(a)[1] for a in parts]
    base = acts[0][act_index][motion]
    W = H = size; ox, oy = W // 2, H - 40
    c = Image.new("RGBA", (W, H))
    if shadow:  # o VS desenha a sombra do jogador no próprio sprite
        ImageDraw.Draw(c).ellipse((ox - 14, oy - 4, ox + 14, oy + 4), fill=(0, 0, 0, 255))
    for path, act in zip(parts, acts):
        m = act[act_index][motion % len(act[act_index])]
        dx = dy = 0
        if m is not base and m["attach"] and base["attach"]:
            dx = base["attach"][0][0] - m["attach"][0][0]
            dy = base["attach"][0][1] - m["attach"][0][1]
        for lay in m["layers"]:
            if lay["spr"] < 0:
                continue
            im = _layer(path, lay)
            c.alpha_composite(im, (ox + lay["x"] + dx - im.width // 2, oy + lay["y"] + dy - im.height // 2))
    return c.crop(c.getbbox()) if crop else c


def retro(im, scale):
    """Reduz com Lanczos e devolve à paleta original do quadro, alfa duro, sem dither (memória do Zero)."""
    if scale == 1:
        return im
    small = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)
    opaque = Image.new("RGB", im.size); opaque.paste(im, mask=im.getchannel("A"))
    pal = opaque.quantize(colors=max(2, min(256, len(set(im.get_flattened_data())))))
    rgb = small.convert("RGB").quantize(palette=pal, dither=Image.Dither.NONE).convert("RGB")
    out = rgb.convert("RGBA"); out.putalpha(small.getchannel("A").point(lambda v: 255 if v >= 128 else 0))
    return out


def stats(ims):
    px = [p for im in ims for p in im.get_flattened_data() if p[3]]
    return len({p[:3] for p in px}), 100 * sum(1 for p in px if p[3] < 255) / max(1, len(px))


def quad_vertices(w, h, px=0.5, py=0.5):
    """Vertex data de um sprite quad (TL, TR, BL, BR em unidades, relativos ao pivô) + UVs zerados (como o VS)."""
    l, r = -px * w / 100, (1 - px) * w / 100
    t, b = (1 - py) * h / 100, -py * h / 100
    return struct.pack("<12f", l, t, 0, r, t, 0, l, b, 0, r, b, 0) + b"\0" * 32
