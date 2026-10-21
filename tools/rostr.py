#!/usr/bin/env python3
# Efeitos 3D do RO em STR (texture/effect/*.str: "STRM" v0x94) → quadros 2D. Formato conferido nos bytes do kyrie.str
# (cabeçalho de 36 B; camada = nº de texturas, nomes de 128 B, nº de keyframes, keyframes de 124 B). Keyframe tipo 0 =
# base, tipo 1 = delta somado a cada quadro depois da base (mesma regra do roBrowser). Quads somados em modo aditivo
# sobre preto (como o cliente desenha esses efeitos); o alfa sai da luminância, pra ir num atlas com alfa normal.
# uso: python3 tools/rostr.py <arquivo.str> <quadro> <saida.png>
import math, os, struct, sys
from PIL import Image
from paths import RAG

KEY = struct.Struct("<iI2f8f8ffIff4fIII")  # 124 B


def read_str(path):
    d = open(path, "rb").read()
    assert d[:4] == b"STRM", path
    fps, maxkey, nlayers = struct.unpack_from("<III", d, 8)
    off, layers = 36, []
    for _ in range(nlayers):
        n, = struct.unpack_from("<i", d, off); off += 4
        tex = [d[off + 128 * i:off + 128 * (i + 1)].split(b"\0")[0].decode("latin1") for i in range(n)]; off += 128 * n
        k, = struct.unpack_from("<i", d, off); off += 4
        keys = [KEY.unpack_from(d, off + 124 * i) for i in range(k)]; off += 124 * k
        layers.append((tex, keys))
    assert off == len(d), (off, len(d))
    return fps, maxkey, layers


def _state(keys, f):
    """base (tipo 0) mais recente com quadro <= f, mais o delta (tipo 1) logo depois dela vezes os quadros passados"""
    base = None
    for i, k in enumerate(keys):
        if k[1] == 0 and k[0] <= f:
            base = i
    if base is None or f > max(k[0] for k in keys):
        return None
    b = list(keys[base])
    d = keys[base + 1] if base + 1 < len(keys) and keys[base + 1][1] == 1 else None
    if d:
        n = f - b[0]
        b = [b[i] + d[i] * n if i >= 2 and isinstance(b[i], float) else b[i] for i in range(len(b))]
    return b


def _tex(name, cache={}):
    if name not in cache:
        p = f"{RAG}/texture/effect/{name}"
        if not os.path.exists(p):
            cache[name] = None
        else:
            im = Image.open(p).convert("RGB")  # BMP: magenta = vazio
            px = [(0, 0, 0) if c[0] > 240 and c[1] < 20 and c[2] > 240 else c for c in im.get_flattened_data()]
            im.putdata(px)
            cache[name] = im
    return cache[name]


def render(path, frame, size=640, only=None):
    """quadro inteiro (size², origem do efeito no centro) em RGBA; only = só camadas com essas texturas"""
    _, _, layers = read_str(path)
    acc = Image.new("RGB", (size, size))
    for tex, keys in layers:
        if not tex or not keys or (only and not any(t.split('.')[0] in only for t in tex)):
            continue
        s = _state(keys, frame)
        if not s:
            continue
        # campos: 0 quadro, 1 tipo, 2-3 posição, 4-11 uv, 12-19 xy (x0..x3, y0..y3), 20 aniframe, 21 anitype,
        # 22 delay, 23 ângulo (1024 = volta), 24-27 cor, 28 srcalpha, 29 destalpha, 30 mtpreset
        im = _tex(tex[min(len(tex) - 1, max(0, int(s[20])))])
        if im is None or s[27] <= 0:
            continue
        xs, ys = s[12:16], s[16:20]
        w, h = max(1, round(max(xs) - min(xs))), max(1, round(max(ys) - min(ys)))
        q = im.resize((w, h), Image.BILINEAR)
        tint = [min(1.0, max(0.0, c / 255)) for c in s[24:27]]
        a = min(1.0, max(0.0, s[27] / 255))
        q = q.point(lambda v, m=a: int(v * m))
        q = Image.merge("RGB", [ch.point(lambda v, t=t: int(v * t)) for ch, t in zip(q.split(), tint)])
        ang = -s[23] * 360 / 1024
        if abs(ang) > 0.01:
            q = q.rotate(ang, Image.BILINEAR, expand=True)
        cx = size / 2 + (s[2] - 320) + (min(xs) + max(xs)) / 2
        cy = size / 2 + (s[3] - 320) + (min(ys) + max(ys)) / 2
        x0, y0 = round(cx - q.width / 2), round(cy - q.height / 2)
        region = acc.crop((x0, y0, x0 + q.width, y0 + q.height))
        acc.paste(_add(region, q), (x0, y0))
    a = acc.convert("L").point(lambda v: 0 if v < 24 else min(255, (v - 24) * 3))  # fumaça escura (fff.bmp) some
    out = acc.convert("RGBA")
    out.putalpha(a)
    return out


def _add(a, b):
    from PIL import ImageChops
    return ImageChops.add(a, b)


if __name__ == "__main__":
    src, f, dst = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    im = render(src, f)
    bb = im.getbbox()
    (im.crop(bb) if bb else im).save(dst)
    print(dst, im.getbbox())
