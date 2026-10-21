#!/usr/bin/env python3
# Extrai o data.grf do cliente do RO numa pasta "data/" com os mesmos nomes que o resto das ferramentas usa, iguais
# aos da extração de referência (conferido arquivo a arquivo): bytes do nome lidos como cp1252 (latin1 onde o cp1252
# não define; ex.: sprite/ÀÌÆÑÆ®), "\" virando "/", e pasta com a caixa da 1ª vez que aparece (como no Windows).
# Formato (0x200): cabeçalho de 46 B (magic 16, chave 14, offset da tabela, seed, nº de arquivos + seed + 7, versão);
# tabela zlib em 46+offset; entrada = nome\0, tam. comprimido, tam. alinhado, tam. real, flags, offset.
# Entradas cifradas (flags 2/4, só em GRFs antigos) ou com zlib quebrado são puladas e contadas. Retoma: arquivo já
# extraído com o tamanho certo não é lido de novo.
# uso: python3 tools/grf.py <saida> <data.grf>
import os, struct, sys, zlib

_CP = "".join(bytes([b]).decode("cp1252", "ignore") or chr(b) for b in range(256))


def _name(raw):
    return "".join(_CP[b] for b in raw)


def _path(dirs, rel):
    """caminho com a caixa da 1ª vez que cada pasta apareceu (dirs: minúsculas -> como ficou)"""
    *parts, base = rel.split("/")
    cur = ""
    for x in parts:
        nxt = f"{cur}/{x}" if cur else x
        cur = dirs.setdefault(nxt.lower(), f"{dirs[cur.lower()]}/{x}" if cur else x)
    return f"{cur}/{base}" if cur else base


def entries(path):
    f = open(path, "rb")
    h = f.read(46)
    assert h[:15] == b"Master of Magic", f"{path}: não é GRF"
    off, seed, n, ver = struct.unpack_from("<IIII", h, 30)
    assert ver == 0x200, f"{path}: versão {ver:#x} (só 0x200)"
    f.seek(46 + off)
    csize, _ = struct.unpack("<II", f.read(8))
    t, p = zlib.decompress(f.read(csize)), 0
    for _ in range(n - seed - 7):
        e = t.index(b"\0", p)
        name = _name(t[p:e]).replace("\\", "/")
        cs, ca, rs, fl, o = struct.unpack_from("<IIIBI", t, e + 1)
        p = e + 18
        if fl & 1:
            yield name, cs, ca, rs, fl, o


def extract(out, grfs):
    skip = done = 0
    dirs = {}  # pasta em minúsculas -> caixa da 1ª vez
    for g in grfs:
        f = open(g, "rb")
        for name, cs, ca, rs, fl, o in entries(g):
            if fl & 6:
                skip += 1
                continue
            rel = name[5:] if name.lower().startswith("data/") else name
            dst = os.path.join(out, _path(dirs, rel))
            if os.path.exists(dst) and os.path.getsize(dst) == rs:  # retomada
                done += 1
                continue
            f.seek(46 + o)
            raw = f.read(ca)
            try:
                data = zlib.decompress(raw[:cs])
            except zlib.error:
                if cs != rs:
                    print("quebrado:", rel)
                    skip += 1
                    continue
                data = raw[:rs]  # guardado sem compressão
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            open(dst, "wb").write(data)
            done += 1
    return done, skip


if __name__ == "__main__":
    d, s = extract(sys.argv[1], sys.argv[2:])
    print(f"{d} arquivos extraídos em {sys.argv[1]}, {s} pulados (cifrados ou quebrados)")
