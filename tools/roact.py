#!/usr/bin/env python3
# Leitor mínimo de .act do RO com os attach points (o export animation.ron não guarda; a cabeça encaixa por eles).
# Layout conferido nos bytes do 검사_남.act (versão 0x205) e validado contra o animation.ron do export.
import struct, re, sys


def read_act(path):
    d = open(path, "rb").read()
    assert d[:2] == b"AC", "não é ACT"
    ver = struct.unpack_from("<H", d, 2)[0]
    n_act = struct.unpack_from("<H", d, 4)[0]
    p = 16
    acts = []
    for _ in range(n_act):
        n_mot = struct.unpack_from("<I", d, p)[0]
        p += 4
        mots = []
        for _ in range(n_mot):
            p += 32  # dois retângulos legados
            n_lay = struct.unpack_from("<I", d, p)[0]
            p += 4
            lays = []
            for _ in range(n_lay):
                x, y, spr, mirror = struct.unpack_from("<iiii", d, p)
                p += 16
                lay = dict(x=x, y=y, spr=spr, mirror=bool(mirror))
                if ver >= 0x200:
                    lay["color"] = tuple(d[p:p + 4]); p += 4
                    sx = struct.unpack_from("<f", d, p)[0]; p += 4
                    sy = sx
                    if ver >= 0x204:
                        sy = struct.unpack_from("<f", d, p)[0]; p += 4
                    lay["scale"] = (sx, sy)
                    lay["rot"], lay["type"] = struct.unpack_from("<ii", d, p); p += 8
                    if ver >= 0x205:
                        lay["w"], lay["h"] = struct.unpack_from("<ii", d, p); p += 8
                lays.append(lay)
            ev = -1
            if ver >= 0x200:
                ev = struct.unpack_from("<i", d, p)[0]; p += 4
            att = []
            if ver >= 0x203:
                n_att = struct.unpack_from("<i", d, p)[0]; p += 4
                for _ in range(n_att):
                    _, ax, ay, attr = struct.unpack_from("<iiii", d, p); p += 16
                    att.append((ax, ay))
            mots.append(dict(layers=lays, event=ev, attach=att))
        acts.append(mots)
    return ver, acts


if __name__ == "__main__":
    # self-check: anchors e sprite_index batem com o animation.ron exportado pelo ro-sprite-exporter
    ver, acts = read_act(sys.argv[1])
    ron = open(sys.argv[2]).read()
    anchors = [tuple(map(int, a)) for a in re.findall(r"anchor: \((-?\d+), (-?\d+)\)", ron)]
    sprs = [int(s) for s in re.findall(r"sprite_index: (-?\d+)", ron)]
    mine = [((l["x"], l["y"]), l["spr"]) for a in acts for m in a for l in m["layers"]]
    assert len(mine) == len(anchors), (len(mine), len(anchors))
    assert all(m == (a, s) for m, a, s in zip(mine, anchors, sprs)), "divergência com o animation.ron"
    print(f"ok: versão {ver:#x}, {len(acts)} ações, {len(mine)} camadas batem com o RON; "
          f"attach do 1º motion = {acts[0][0]['attach']}")
