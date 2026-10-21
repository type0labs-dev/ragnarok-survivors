#!/usr/bin/env python3
# Vídeos de abrir baú (bundles chestnobg/2/3: VideoClip H.264 Constrained Baseline 634x332, 60 fps, fundo preto que
# o jogo soma por cima da tela) → versão RO no mesmo roteiro e no mesmo nº de quadros (o jingle do baú tem a duração
# do vídeo): Treasure Mimic do RO embaixo, feixe azul com ícones de itens do RO rolando como caça-níquel e chuva
# de Zeny e gemas. O contador de ouro desenhado no vídeo do VS fica de fora (o jogo mostra o valor de verdade).
# uso: python3 -P tools/build_chest.py <romfs> <overlay>
import sys, os, random, subprocess, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -P tira a pasta do script do path
from PIL import Image, ImageDraw
from unitypatch import Bundle, typetree_bytes
from rosprite import compose, HUMAN, MONSTER
from roact import read_act
from roicons import ro_icon, load_icon

romfs, out = sys.argv[1:3]
AA = os.environ.get("VS_AA", "Data/StreamingAssets/aa/Switch")  # DLC: "" (bundles na raiz do romfs)
W, H = 634, 332
# Treasure Mimic (o baú-monstro do RO): ação 0 = fechado parado, 2 = abre derramando moedas e gemas, 4 (último
# quadro) = aberto cheio de joias. Fechado até o feixe, abre, e fica aberto.
MIMIC = [f"{MONSTER}/treasure_mimic.act"]
_acts = read_act(MIMIC[0])[1]
IDLE = [compose(MIMIC, 0 * 8, m) for m in range(len(_acts[0]))]
OPEN = [compose(MIMIC, 2 * 8, m) for m in range(len(_acts[16]))] + [compose(MIMIC, 4 * 8, len(_acts[32]) - 1)]
ICONS = [load_icon(p) for p in (ro_icon(f"item {i}") for i in (501, 502, 503, 504, 505, 607, 608, 616, 617, 715, 716,
                                                                717, 718, 719, 720, 721, 722, 723, 726, 728, 7228, 969))
         if p]
COINS = [load_icon(p) for p in (ro_icon(f"item {i}") for i in (671, 673, 675, 715, 716, 717)) if p]


def scale(im, k):
    return im.resize((im.width * k, im.height * k), Image.NEAREST)


def frames(n, seed):
    rng = random.Random(seed)
    start = int(n * 0.24)  # o feixe abre perto de 1/4 do vídeo, como no do VS
    drops = [(rng.uniform(0, W), rng.uniform(-H, 0), rng.uniform(1.2, 3.2), rng.choice(COINS)) for _ in range(70)]
    reel = [rng.choice(ICONS) for _ in range(400)]
    cx = W // 2
    for i in range(n):
        im = Image.new("RGB", (W, H))
        d = ImageDraw.Draw(im)
        if i >= start:
            t = i - start
            bw = min(26, 4 + t)  # feixe azul abrindo
            for x in range(cx - bw, cx + bw):
                a = 1 - abs(x - cx) / max(1, bw)
                d.line([(x, 0), (x, H - 40)], fill=(int(20 * a), int(40 * a), int(170 * a)))
            off = (t * 6) % 40
            for k in range(10):  # ícones rolando dentro do feixe
                ic = reel[(t // 7 + k) % len(reel)]
                y = H - 70 - k * 40 + off
                if 0 <= y < H - 50:
                    im.paste(ic, (cx - ic.width // 2, int(y) - ic.height // 2), ic)
            for j, (x, y0, v, ic) in enumerate(drops):  # chuva de moedas e gemas
                y = (y0 + t * v) % (H + 40) - 20
                im.paste(ic, (int(x), int(y)), ic)
        bx = IDLE[(i // 8) % len(IDLE)] if i < start else OPEN[min(len(OPEN) - 1, (i - start) // 5)]
        im.paste(bx, (cx - bx.width // 2, H - bx.height - 6), bx)
        yield im


done = []
for name in ("chestnobg", "chestnobg2", "chestnobg3"):
    rel = f"{AA}/vs_local_assets_{name}.bundle"
    b = Bundle(f"{romfs}/{rel}")
    (fname, f), = b.serialized()
    vo = next(o for o in f.objects.values() if o.type.name == "VideoClip")
    vt = vo.read_typetree()
    n = vt["m_FrameCount"]
    with tempfile.TemporaryDirectory() as td:
        mp4 = f"{td}/v.mp4"
        ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                               "-r", "60", "-i", "-", "-c:v", "libx264", "-profile:v", "baseline", "-level", "3.1",
                               "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-g", "60", "-crf", "26", mp4],
                              stdin=subprocess.PIPE)
        for im in frames(n, name):
            ff.stdin.write(im.tobytes())
        ff.stdin.close()
        assert ff.wait() == 0
        data = open(mp4, "rb").read()
    got = int(subprocess.check_output(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                                       "stream=nb_read_frames", "-of", "csv=p=0", "-"], input=data).strip())
    assert got == n, (name, got, n)
    res = vt["m_ExternalResources"]["m_Source"].rsplit("/", 1)[-1]
    assert vt["m_ExternalResources"]["m_Offset"] == 0 and len(b.raw[res]) == vt["m_ExternalResources"]["m_Size"]
    b.raw[res] = bytearray(data)
    vt["m_ExternalResources"] = {**vt["m_ExternalResources"], "m_Size": len(data)}
    b.replace_object(fname, vo, typetree_bytes(vo, vt))
    os.makedirs(os.path.dirname(f"{out}/{rel}"), exist_ok=True)
    b.save(f"{out}/{rel}")
    done.append(f"{name} {n} quadros {len(data) // 1024} KB")
print("ok baús:", "; ".join(done))
