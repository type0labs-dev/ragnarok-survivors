#!/usr/bin/env python3
# Zip publicável: construtor (tools/*.py), mapping, exefs compilado (build-out/8d, nunca o 8dg), fonte OFL e o
# código do exl (GPL). Nada do VS nem do RO: recusa qualquer arquivo com extensão de asset dos jogos.
# uso: python3 tools/release.py [saida.zip]
import datetime, glob, os, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANNED = (".bundle", ".unity3d", ".assets", ".resource", ".spr", ".act", ".bmp", ".tga", ".png", ".jpg", ".gat",
          ".gnd", ".rsw", ".rsm", ".str", ".grf", ".mp3", ".ogg", ".wav", ".fsb", ".json~")
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "dist", f"ragnarok-survivors-{datetime.date.today()}.zip")

files = {"README.md": "README.md", "requirements.txt": "requirements.txt",
         "exefs/main.npdm": "build-out/8d/main.npdm", "exefs/subsdk9": "build-out/8d/subsdk9",
         "fonts/NotoSerif-Bold.ttf": "/usr/share/fonts/noto/NotoSerif-Bold.ttf",
         "fonts/OFL.txt": "/usr/share/licenses/noto-fonts/LICENSE",
         "tools/unity/BuildAudio.cs": "tools/unity/BuildAudio.cs"}
for p in glob.glob("tools/*.py", root_dir=ROOT) + glob.glob("mapping/**/*.*", root_dir=ROOT, recursive=True):
    files[p] = p
for p in glob.glob("exl/**/*", root_dir=ROOT, recursive=True):
    if os.path.isfile(os.path.join(ROOT, p)) and not p.startswith(("exl/build/", "exl/.git", "exl/deploy/")) and p != "exl/work.elf":
        files[p] = p

bad = [k for k in files if k.lower().endswith(BANNED)]
assert not bad, f"asset de jogo no pacote: {bad}"
os.makedirs(os.path.dirname(out), exist_ok=True)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for arc, src in sorted(files.items()):
        z.write(os.path.join(ROOT, src), f"ragnarok-survivors/{arc}")
print(out, len(files), "arquivos", os.path.getsize(out) // 1024, "KB")
