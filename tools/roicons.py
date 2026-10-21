#!/usr/bin/env python3
# Ícones do RO: skill → texture/유저인터페이스/item/<skill>.bmp; item Id → nome do recurso (idnum2itemresnametable)
# → .bmp. Usado por reskin_icons.py e reskin_props.py.
import os, re
from PIL import Image

from paths import RAG
ICONS = f"{RAG}/texture/" + "유저인터페이스".encode("cp949").decode("latin1") + "/item"

resname = {}
for line in open(f"{RAG}/idnum2itemresnametable.txt", "rb").read().decode("cp949", "replace").splitlines():
    p = line.split("#")
    if len(p) >= 2 and p[0].strip().isdigit():
        resname[int(p[0])] = p[1]


def ro_icon(ref):
    """'skill SM_BASH' / 'item 657 ...' / 717 → caminho do .bmp (ou None)"""
    ref = str(ref)
    m = re.search(r"\bskill\s+([A-Z][A-Z0-9_]+)", ref)
    if m:
        p = f"{ICONS}/{m.group(1).lower()}.bmp"
        return p if os.path.exists(p) else None
    m = re.search(r"(?:\bitem\b\D*?|^)(\d+)\b", ref)
    if m and int(m.group(1)) in resname:
        p = f"{ICONS}/" + resname[int(m.group(1))].encode("cp949").decode("latin1") + ".bmp"
        return p if os.path.exists(p) else None
    return None


def load_icon(p):
    im = Image.open(p).convert("RGBA")
    px = [(0, 0, 0, 0) if c[:3] == (255, 0, 255) else c for c in im.get_flattened_data()]
    im.putdata(px)
    return im.crop(im.getbbox())




def fit_icon(im, w, h):
    """Ícone do RO (bbox recortado) numa caixa w×h de atlas 2×, preenchendo como o VS: ampliação inteira em NEAREST
    se couber; senão retro (Lanczos + paleta original, alfa duro) até a borda, pra cima ou pra baixo."""
    from rosprite import retro
    s = min(w / im.width, h / im.height)
    if s >= 2:  # inteiro: pixel do RO dobrado, idêntico
        s = int(s)
        return im.resize((im.width * s, im.height * s), Image.NEAREST)
    return retro(im, s) if abs(s - 1) > 0.05 else im  # Zero: preencher a caixa como o ícone da gladius


if __name__ == "__main__":
    sq = Image.new("RGBA", (12, 15), (255, 0, 0, 255))
    assert fit_icon(sq, 32, 32).size == (24, 30)   # ×2 inteiro
    assert fit_icon(sq, 22, 28).size == (22, 28)   # ~1,83×, preenche
    assert fit_icon(Image.new("RGBA", (24, 24), (9, 9, 9, 255)), 32, 32).size == (32, 32)  # 1,33×: preenche
    assert fit_icon(Image.new("RGBA", (40, 40)), 32, 32).size == (32, 32)  # reduz
    print("ok fit_icon")
