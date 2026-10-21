#!/usr/bin/env python3
# NSP próprio do Ragnarok Survivors, montado na máquina do jogador a partir do dump DELE (nada de jogo vem no pacote):
# VS 1.15.113 vanilla + overlay do build.py --sd, TID novo (convive com o VS), nome e ícone do RO.
#   python3 tools/make_nsp.py --exefs <exefs do update> --romfs <romfs> --control <romfs do NCA control>
#       --mod <saída do build.py --sd> --ro <cliente do RO> --keys <prod.keys> --hacpack <binário> [--logo <dir>]
# Precisa do hacpack (v1.36). O NSP sai em <work>/nsp/ e é só pra uso próprio: ele contém o jogo inteiro.
import argparse, hashlib, io, os, shutil, struct, subprocess, sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OLD, NEW = 0x010089A0197E4000, 0x0100525356000000
MAIN_BUILD_ID = "59e1da1b9c861470eee5ae11d624c0d3"  # exefs/main do 1.15.113
VANILLA = "111f7ba47fc8c8115ee7fec4901fbea0192235d73482d4c773c6ca84f6de9d96"  # Data/data.unity3d do 1.15.113
NAME, PUBLISHER = "Ragnarok Survivors", "Fan reskin (VS + RO)"

ap = argparse.ArgumentParser()
ap.add_argument("--exefs", required=True, help="exefs do update 1.15.113 (main, main.npdm, rtld, sdk, subsdk0)")
ap.add_argument("--romfs", required=True, help="romfs vanilla (a mesma pasta do build.py --romfs)")
ap.add_argument("--control", required=True, help="romfs do NCA control (control.nacp + icon_*.dat)")
ap.add_argument("--mod", required=True, help="pasta passada ao build.py --sd")
ap.add_argument("--ro", required=True, help="pasta do cliente do RO (usa o ragnarok.ico)")
ap.add_argument("--keys", required=True, help="prod.keys do teu console")
ap.add_argument("--hacpack", default="hacpack")
ap.add_argument("--logo", help="seção logo do NCA program (NintendoLogo.png + StartupMovie.gif); opcional")
ap.add_argument("--keygeneration", default="16")
ap.add_argument("--work", default=os.path.join(ROOT, "work"))
a = ap.parse_args()
W = os.path.abspath(os.path.join(a.work, "nsp"))
MOD = os.path.join(a.mod, "atmosphere", "contents", f"{OLD:016X}")


def run(*c):
    subprocess.run(c, check=True)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def swap_ids(b, pairs):
    for o, n in pairs:
        b = b.replace(struct.pack("<Q", o), struct.pack("<Q", n))
    return b


main = open(os.path.join(a.exefs, "main"), "rb").read(0x60)
if main[:4] != b"NSO0" or main[0x40:0x50].hex() != MAIN_BUILD_ID:
    sys.exit("--exefs não é do Vampire Survivors 1.15.113 (dump o exefs do update, não o do jogo base)")
if sha(os.path.join(a.romfs, "Data", "data.unity3d")) != VANILLA:
    sys.exit("--romfs não é o do 1.15.113 sem mods")
if not os.path.isfile(os.path.join(MOD, "exefs", "subsdk9")):
    sys.exit(f"{MOD} não tem o mod: rode antes tools/build.py --sd {a.mod}")

shutil.rmtree(W, ignore_errors=True)
for d in ("exefs", "romfs", "control", "nca", "tmp"):
    os.makedirs(os.path.join(W, d))

# exefs: executável vanilla + hooks; o ProgramID do npdm vira o TID novo
for f in ("main", "rtld", "sdk", "subsdk0"):
    shutil.copy(os.path.join(a.exefs, f), os.path.join(W, "exefs", f))
shutil.copy(os.path.join(MOD, "exefs", "subsdk9"), os.path.join(W, "exefs", "subsdk9"))
npdm = open(os.path.join(MOD, "exefs", "main.npdm"), "rb").read()
assert npdm.count(struct.pack("<Q", OLD)) == 1, "npdm inesperado"
open(os.path.join(W, "exefs", "main.npdm"), "wb").write(swap_ids(npdm, [(OLD, NEW)]))

# romfs: vanilla por hardlink (cai pra cópia em outro disco) com o overlay do mod por cima
def link_or_copy(s, d):
    try:
        os.link(s, d)
    except OSError:
        shutil.copy2(s, d)
shutil.copytree(a.romfs, os.path.join(W, "romfs"), copy_function=link_or_copy, dirs_exist_ok=True)
for root, _, files in os.walk(os.path.join(MOD, "romfs")):
    for f in files:
        s = os.path.join(root, f)
        d = os.path.join(W, "romfs", os.path.relpath(s, os.path.join(MOD, "romfs")))
        os.makedirs(os.path.dirname(d), exist_ok=True)
        if os.path.exists(d):
            os.unlink(d)  # nunca escrever no hardlink: é o romfs vanilla do jogador
        shutil.copy(s, d)

# control: nome, publisher e todos os IDs do nacp; ícone do RO (32x32 ampliado sem filtro) em todo idioma
nacp = bytearray(open(os.path.join(a.control, "control.nacp"), "rb").read())
for i in range(16):
    if nacp[i * 0x300]:
        nacp[i * 0x300:(i + 1) * 0x300] = NAME.encode().ljust(0x200, b"\0") + PUBLISHER.encode().ljust(0x100, b"\0")
nacp = swap_ids(bytes(nacp), [(OLD, NEW), (OLD + 0x1000, NEW + 0x1000)])
assert struct.pack("<Q", OLD) not in nacp
open(os.path.join(W, "control", "control.nacp"), "wb").write(nacp)
ico = Image.open(os.path.join(a.ro, "ragnarok.ico"))
ico = max((ico.ico.getimage(s) for s in ico.ico.sizes()), key=lambda im: im.width).convert("RGBA")
bg = Image.new("RGBA", ico.size, "black")
bg.alpha_composite(ico)
buf = io.BytesIO()
bg.convert("RGB").resize((256, 256), Image.NEAREST).save(buf, "JPEG", quality=95)
icons = [f for f in os.listdir(a.control) if f.startswith("icon_")] or ["icon_AmericanEnglish.dat"]
for f in icons:
    open(os.path.join(W, "control", f), "wb").write(buf.getvalue())

# NCAs → NSP
tid = f"{NEW:016x}"
common = [a.hacpack, "-k", a.keys, "--tempdir", os.path.join(W, "tmp", "hp"), "--backupdir", os.path.join(W, "tmp", "bk"),
          "--titleid", tid, "--keygeneration", a.keygeneration, "-o", os.path.join(W, "nca"), "--type", "nca"]
logo = ["--logodir", a.logo] if a.logo else []
run(*common, "--ncatype", "program", "--exefsdir", os.path.join(W, "exefs"), "--romfsdir", os.path.join(W, "romfs"), *logo)
program = next(f for f in os.listdir(os.path.join(W, "nca")))
run(*common, "--ncatype", "control", "--romfsdir", os.path.join(W, "control"))
control = next(f for f in os.listdir(os.path.join(W, "nca")) if f != program)
run(*common, "--ncatype", "meta", "--titletype", "application",
    "--programnca", os.path.join(W, "nca", program), "--controlnca", os.path.join(W, "nca", control))
run(a.hacpack, "-k", a.keys, "--tempdir", os.path.join(W, "tmp", "hp"), "--titleid", tid, "-o", W,
    "--type", "nsp", "--ncadir", os.path.join(W, "nca"))
out = os.path.join(W, f"RagnarokSurvivors[{tid.upper()}].nsp")
os.replace(os.path.join(W, f"{tid}.nsp"), out)
for d in ("exefs", "romfs", "control", "nca", "tmp"):
    shutil.rmtree(os.path.join(W, d))
print("NSP:", out, os.path.getsize(out) // 2**20, "MB  (uso próprio: contém o jogo inteiro, não distribua)")
