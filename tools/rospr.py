#!/usr/bin/env python3
# Leitor de .spr do RO: imagens de paleta (índice 0 = transparente; v2.1 com RLE só dos zeros) e imagens RGBA
# (guardadas como ABGR, de baixo pra cima; conferido contra o export antigo, que saía com canais trocados e invertido).
# Paleta = 1024 B no fim. A camada do .act escolhe a lista pelo "type" (0 paleta, 1 RGBA) e a imagem pelo "spr".
# uso (self-check das imagens de paleta contra um export em PNG): python3 tools/rospr.py <arquivo.spr> <pasta>
import struct, sys
from PIL import Image


def read_spr(path):
    pal, rgba = read_spr_typed(path)
    return pal + rgba


def read_spr_typed(path, cache={}):
    """(imagens de paleta, imagens RGBA): a camada do .act aponta pra uma das listas pelo "type" (0/1)"""
    if path in cache:
        return cache[path]
    d = open(path, "rb").read()
    assert d[:2] == b"SP", path
    ver, = struct.unpack_from("<H", d, 2)
    npal, = struct.unpack_from("<H", d, 4)
    nrgba, off = (struct.unpack_from("<H", d, 6)[0], 8) if ver >= 0x200 else (0, 6)
    pal = d[-1024:]
    lut = [(pal[i * 4], pal[i * 4 + 1], pal[i * 4 + 2], 0 if i == 0 else 255) for i in range(256)]
    ims, rgba = [], []
    for _ in range(npal):
        w, h = struct.unpack_from("<HH", d, off); off += 4
        if ver >= 0x201:
            n, = struct.unpack_from("<H", d, off); off += 2
            src, raw, i = d[off:off + n], bytearray(), 0
            off += n
            while i < len(src):
                if src[i] == 0:
                    raw += b"\0" * src[i + 1]; i += 2
                else:
                    raw.append(src[i]); i += 1
        else:
            raw = d[off:off + w * h]; off += w * h
        im = Image.new("RGBA", (w, h))
        im.putdata([lut[b] for b in raw[:w * h]])
        ims.append(im)
    for _ in range(nrgba):
        w, h = struct.unpack_from("<HH", d, off); off += 4
        a, b, g, r = Image.frombytes("RGBA", (w, h), d[off:off + w * h * 4]).split()
        off += w * h * 4
        rgba.append(Image.merge("RGBA", (r, g, b, a)).transpose(Image.FLIP_TOP_BOTTOM))
    cache[path] = ims, rgba
    return cache[path]


if __name__ == "__main__":
    import os
    ims = read_spr(sys.argv[1])
    bad = 0
    for i, im in enumerate(ims):
        p = os.path.join(sys.argv[2], f"frame_{i:03d}.png")
        ref = Image.open(p).convert("RGBA")
        same = im.size == ref.size and im.tobytes() == ref.tobytes()
        bad += not same
        if not same:
            print(i, im.size, ref.size, list(im.getdata())[:3], list(ref.getdata())[:3])
    print(f"{len(ims)} imagens, {bad} diferentes")
