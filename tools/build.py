#!/usr/bin/env python3
# Construtor do Ragnarok Survivors: monta o overlay do zero, na ordem certa (patch_data relê o data.unity3d do romfs;
# ícones gravam por cima dele), a partir do romfs do VS e do cliente do RO de quem roda. Nada do VS nem do RO vai no
# pacote publicado; tudo sai daqui, na máquina do jogador.
#   python3 tools/build.py --romfs <romfs do VS 1.15.113> --ro <pasta do cliente do RO com data.grf> --sd <saída>
#     → <saída>/atmosphere/contents/010089A0197E4000/{romfs,exefs}, pronto pro cartão SD
# Sem --ro, usa as pastas da bancada (tools/paths.py). --out muda o overlay (padrão <work>/overlay).
import argparse, hashlib, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TID = "010089A0197E4000"
VANILLA = "111f7ba47fc8c8115ee7fec4901fbea0192235d73482d4c773c6ca84f6de9d96"  # Data/data.unity3d do 1.15.113
ENEMY_BUNDLES = ["enemies_universal", "enemies", "enemies2", "enemies3", "enemies2023", "enemies2025", "enemiesm"]

ap = argparse.ArgumentParser()
ap.add_argument("--romfs", required=True)
ap.add_argument("--ro", help="pasta do cliente do RO (data.grf e BGM/)")
ap.add_argument("--work", default=os.path.join(ROOT, "work"))
ap.add_argument("--out", help="overlay (padrão <work>/overlay)")
ap.add_argument("--sd", help="monta atmosphere/contents/... aqui")
ap.add_argument("--exefs", help="main.npdm + subsdk9 (padrão: exefs/ do pacote, ou build-out/8d na bancada)")
a = ap.parse_args()
R = os.path.abspath(a.romfs)
O = os.path.abspath(a.out or os.path.join(a.work, "overlay"))


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


du = os.path.join(R, "Data", "data.unity3d")
if not os.path.exists(du):
    sys.exit(f"{du} não existe: --romfs tem que ser a pasta romfs do dump (a que tem Data/)")
if sha(du) != VANILLA:
    sys.exit("o romfs não é do Vampire Survivors 1.15.113 sem mods (os hooks só servem nessa versão)")

env = dict(os.environ)
if a.ro:
    grf, bgm = os.path.join(a.ro, "data.grf"), os.path.join(a.ro, "BGM")
    rag = os.path.join(os.path.abspath(a.work), "ro", "data")
    if not os.path.exists(os.path.join(rag, ".ok")):
        if not os.path.exists(grf):
            sys.exit(f"{grf} não existe")
        print("extraindo o data.grf (uma vez só; ~4 GB)…", flush=True)
        sys.path.insert(0, HERE)
        from grf import extract
        print(extract(rag, [grf]))
        open(os.path.join(rag, ".ok"), "w").close()
    os.environ["RO_DATA"] = env["RO_DATA"] = rag
    os.environ["RO_BGM"] = env["RO_BGM"] = bgm
    os.environ["VS_WORK"] = env["VS_WORK"] = os.path.abspath(a.work)
font = os.path.join(ROOT, "fonts", "NotoSerif-Bold.ttf")
if os.path.exists(font) and "RS_FONT" not in env:
    env["RS_FONT"] = font

sys.path.insert(0, HERE)
from paths import work, BGM, UNITY

# JSON do jogo (CHARACTER_DATA…), lidos do romfs: o mapping e várias ferramentas consultam
import UnityPy
os.makedirs(work("data"), exist_ok=True)
for o in UnityPy.load(du).objects:
    if o.type.name == "TextAsset":
        t = o.read()
        if t.m_Name.endswith("_DATA"):
            s = t.m_Script
            open(work("data", t.m_Name + ".json"), "wb").write(s.encode("utf-8", "surrogateescape") if isinstance(s, str) else bytes(s))


def run(*args, ok=False, last=True):
    r = subprocess.run([sys.executable, "-P", os.path.join(HERE, args[0]), *args[1:]], env=env, cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = (r.stdout + r.stderr).strip().splitlines()
    print(*(lines[-1:] if last else lines), sep="\n", flush=True)
    if r.returncode and not ok:
        print(r.stderr[-3000:])
        sys.exit(f"falhou: {args[0]}")


shutil.rmtree(O, ignore_errors=True)
os.makedirs(O)
# todo personagem do mapping com arte própria (seguidores com "parent" usam a do dono); falha não para o build
from mapping import section, vs_data, texture_index
import yaml
idx, cd = texture_index(R, "Data/StreamingAssets/aa/Switch"), vs_data("CHARACTER")
for c in [x["vs_id"] for x in section("characters") if not x.get("parent") and "/" in str(x.get("ro_ref", ""))
          and x["vs_id"] in cd and cd[x["vs_id"]][0].get("textureName") in idx]:
    run("reskin_char.py", R, O, c, "2", ok=True)
for bn in ENEMY_BUNDLES:
    run("reskin_enemies.py", R, O, f"vs_local_assets_{bn}.bundle")
# fases: cada atlas de tileset com o chão e a vegetação dos mapas do RO da região (mapping: tilesets)
y = yaml.safe_load(open(os.path.join(ROOT, "mapping", "stages_music_ui_story.yaml"), encoding="utf-8"))
for tex, maps in list(y["tilesets"].items()) + list(y["backgrounds"].items()):
    run("reskin_stage.py", R, O, tex, ",".join(maps), ok=True)
audio = os.path.exists(UNITY) and shutil.which("ffmpeg") and os.path.isdir(BGM)
if audio:
    run("build_music.py", R, O)
else:
    print("sem Unity Editor/ffmpeg/BGM: música e sons ficam os do VS")
for s in ["patch_data.py", "reskin_icons.py", "reskin_props.py",
          "reskin_spritesets.py",  # conjuntos avulsos em bundles character_* (seguidores, Tarantella…)
          "reskin_wheel.py",  # roleta: ícones do VS apagados, itens do RO no lugar
          "reskin_vfx.py",
          "rofx.py",  # efeitos do RO animados pelo hook (ro_fx): atlas rofx + exl/.../rofx_table.inc
          "reskin_stagecards.py", "reskin_arcana.py", "reskin_ui.py",
          "sync_data_atlases.py"]:  # cópias dos atlas de inimigos no data.unity3d (Mudman, Ghost…)
    run(s, R, O)
# baú e modal originais (Zero, 16/10): tools/build_chest.py fica guardado, fora do build
if audio:
    run("build_sfx.py", R, O)
for f in os.listdir(O):
    if f.startswith("preview_") or f == "enemy_scales.json":
        os.remove(os.path.join(O, f))
print("overlay pronto:", O)

if a.sd:
    exefs = a.exefs or next((p for p in (os.path.join(ROOT, "exefs"), os.path.join(ROOT, "build-out", "8d"))
                             if os.path.isdir(p)), None)
    if not exefs:
        sys.exit("sem exefs (main.npdm + subsdk9)")
    dst = os.path.join(a.sd, "atmosphere", "contents", TID)
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(O, os.path.join(dst, "romfs"))
    shutil.copytree(exefs, os.path.join(dst, "exefs"))
    print("pronto pro SD:", dst)
