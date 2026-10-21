#!/usr/bin/env python3
# Leitura mínima dos mapas do RO pra montar fases: texturas do chão (.gnd) e texturas dos modelos 3D do cenário
# (.rsw → .rsm). Árvore, mato e flor no RO são quadros texturizados com fundo magenta: viram sprites 2D.
# Formatos conferidos nos bytes de pay_fild01 (GND 1.7, RSW 2.1).
import os, struct

from paths import RAG
TEX = f"{RAG}/texture"


def _s(b, p, n):
    return b[p:p + n].split(b"\0")[0].decode("cp949", "replace")


def _path(rel, base):
    """'필드바닥\\숲속바닥-01.bmp' → caminho real (nomes do GRF em coreano lidos como latin1, caixa variável)"""
    p = base
    for part in rel.replace("\\", "/").split("/"):
        want = part.encode("cp949").decode("latin1").lower()
        try:
            hit = next((n for n in os.listdir(p) if n.lower() == want), None)
        except FileNotFoundError:
            return None
        if hit is None:
            return None
        p = os.path.join(p, hit)
    return p


def gnd_textures(m):
    b = open(f"{RAG}/{m}.gnd", "rb").read()
    assert b[:4] == b"GRGN"
    n, ln = struct.unpack_from("<II", b, 18)
    out = []
    for i in range(n):
        p = _path(_s(b, 26 + i * ln, ln), TEX)
        if p and p not in out:
            out.append(p)
    return out


def rsw_models(m):
    b = open(f"{RAG}/{m}.rsw", "rb").read()
    assert b[:4] == b"GRSW"
    ver = (b[4], b[5])
    p = 6 + 40 * 3 + (40 if ver >= (1, 4) else 0)
    if ver >= (1, 3):
        p += 4 * 5 + (4 if ver >= (1, 8) else 0)
    if ver >= (1, 5):
        p += 4 * 2 + 4 * 6 + (4 if ver >= (1, 7) else 0)
    if ver >= (1, 6):
        p += 4 * 4
    if ver >= (2, 2):
        p += 1  # build number (não aparece nos mapas clássicos)
    n, = struct.unpack_from("<i", b, p)
    p += 4
    out = []
    for _ in range(n):
        t, = struct.unpack_from("<i", b, p)
        p += 4
        if t == 1:
            name = _s(b, p + 40 + 12, 80)  # nome 40, animType i32, animSpeed f32, blockType i32, arquivo 80
            p += 40 + 12 + 80 + 80 + 36
            if name not in out:
                out.append(name)
        elif t == 2:
            p += 80 + 12 + 40  # luz (nome 80, pos 3f, cor 3i, alcance f) — tamanho clássico
        elif t == 3:
            p += 80 + 80 + 12 + 4 + 4 + 4 + 4  # som
        elif t == 4:
            p += 80 + 12 + 4 + 16  # efeito
        else:
            break
    return out


def rsm_textures(model):
    path = _path(model, f"{RAG}/model")
    if not path:
        return []
    b = open(path, "rb").read()
    if b[:4] != b"GRSM" or b[4] >= 2:
        return []
    ver = (b[4], b[5])
    p = 6 + 8 + (1 if ver >= (1, 4) else 0) + 16
    n, = struct.unpack_from("<i", b, p)
    if not 0 < n < 64:
        return []
    return [q for q in (_path(_s(b, p + 4 + i * 40, 40), TEX) for i in range(n)) if q]


if __name__ == "__main__":
    import sys
    m = sys.argv[1] if len(sys.argv) > 1 else "pay_fild01"
    g = gnd_textures(m)
    ms = rsw_models(m)
    tx = sorted({t for x in ms for t in rsm_textures(x)})
    assert g and ms, "mapa sem chão ou sem modelos"
    print(m, f"{len(g)} texturas de chão, {len(ms)} modelos, {len(tx)} texturas de modelo")
    for t in tx[:15]:
        print("  ", t.encode("latin1", "replace").decode("cp949", "replace").rsplit("/", 2)[-2:])
