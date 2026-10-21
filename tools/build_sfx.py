#!/usr/bin/env python3
# Efeitos sonoros do VS (187 AudioClip do data.unity3d/resources.assets, bytes no arquivo solto
# Data/resources.resource, quase todos IMA ADPCM) → wav do RO (mapping: sfx_clips). Mesmo caminho das músicas: o
# Unity Editor local gera o FSB5 (aqui ADPCM), que é anexado ao fim de uma cópia do resources.resource; cada clipe
# é reapontado (m_Resource offset/size + duração/canais/frequência). O volume do RO (mais baixo, 22 kHz) é
# normalizado pelo pico pra não sumir no meio dos efeitos do VS.
# Roda depois de patch_data/reskin_icons/reskin_ui (lê e grava o data.unity3d do overlay).
# uso: python3 -P tools/build_sfx.py <romfs> <overlay>
import sys, os, subprocess, shutil, struct, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -P tira a pasta do script do path
import yaml
from unitypatch import Bundle, typetree_bytes

romfs, out = sys.argv[1:3]
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
from paths import UNITY, RAG, BGM, work
WAV = f"{RAG}/wav"
PROJ = work("unity-audio")
BUILT = work("unity-sfx-out")
COMPAT = os.path.expanduser("~/.local/opt/unity-compat/usr/lib")
REL = "Data/data.unity3d"
_y = yaml.safe_load(open(f"{ROOT}/mapping/stages_music_ui_story.yaml"))
table = _y["sfx_clips"]
BUNDLES = _y.get("sfx_bundles") or {}
AA = os.environ.get("VS_AA", "Data/StreamingAssets/aa/Switch")  # DLC: "" (bundles na raiz do romfs)

import tempfile
audio = tempfile.mkdtemp(prefix="rosurv-sfx-")  # o unity_audio limpa o Assets/Audio do projeto a cada lote
for clip, ro in table.items():
    src = os.path.join(WAV, *[p.encode("cp949").decode("latin1") for p in ro.split("/")])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-ac", "1", "-ar", "44100",
                    "-af", "dynaudnorm=f=75:g=3:p=0.9", f"{audio}/{clip.lower()}.wav"], check=True)
blen = {}  # clipe em bundle próprio -> duração do VS
for clip, ref in BUNDLES.items():
    rel = f"{AA}/vs_local_assets_{clip.lower()}.bundle"
    if not os.path.exists(f"{romfs}/{rel}"):
        continue
    vb = Bundle(f"{romfs}/{rel}")
    L = next(o for _, f in vb.serialized() for o in f.objects.values() if o.type.name == "AudioClip").read_typetree()["m_Length"]
    blen[clip] = L
    kind, name = ref.split(None, 1)
    src = (f"{BGM}/{int(name):02d}.mp3" if kind == "bgm"
           else os.path.join(WAV, *[p.encode("cp949").decode("latin1") for p in name.split("/")]))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-stream_loop", "-1", "-i", src, "-t", f"{L:.3f}", "-ac", "1",
                    "-ar", "44100", "-af", f"dynaudnorm=f=75:g=3:p=0.9,afade=t=out:st={max(0, L - 0.5):.3f}:d=0.5",
                    f"{audio}/{clip.lower()}.wav"], check=True)
print(f"{len(table)} efeitos + {len(blen)} em bundle decodificados; Unity…", flush=True)
from unity_audio import build as unity_build, bundle_path
unity_build({os.path.basename(p)[:-4]: p for p in glob.glob(f"{audio}/*.wav")}, BUILT, "adpcm", "unity-sfx")

blob = bytearray(open(f"{romfs}/Data/resources.resource", "rb").read())  # sempre do original: anexos não acumulam
src_path = os.path.join(out, REL) if os.path.exists(os.path.join(out, REL)) else os.path.join(romfs, REL)
b = Bundle(src_path)
orig = {(n, o.path_id): o for n, f in Bundle(os.path.join(romfs, REL)).serialized() for o in f.objects.values()
        if o.type.name == "AudioClip"}
done = 0
for fname, f in b.serialized():
    for o in f.objects.values():
        if o.type.name != "AudioClip":
            continue
        t = o.read_typetree()
        if t["m_Name"] not in table or not t["m_Resource"]["m_Source"].endswith("resources.resource"):
            # fora da tabela (ex.: sons da morte, Zero preferiu os do VS): volta o objeto original, senão o offset
            # de uma rodada anterior aponta pra um anexo que o resources.resource novo não tem
            ob = orig[(fname, o.path_id)].get_raw_data()
            if o.get_raw_data() != ob:
                b.replace_object(fname, o, ob)
            continue
        nb = Bundle(bundle_path(BUILT, t['m_Name']))
        (_, nfile), = nb.serialized()
        nt = next(x for x in nfile.objects.values() if x.type.name == "AudioClip").read_typetree()
        nres = nt["m_Resource"]["m_Source"].rsplit("/", 1)[-1]
        fsb = bytes(nb.raw[nres][nt["m_Resource"]["m_Offset"]:nt["m_Resource"]["m_Offset"] + nt["m_Resource"]["m_Size"]])
        assert fsb[:4] == b"FSB5"
        blob.extend(b"\0" * ((-len(blob)) % 32))
        off = len(blob)
        blob.extend(fsb)
        for k in ("m_Length", "m_Frequency", "m_Channels", "m_BitsPerSample", "m_CompressionFormat", "m_LoadType"):
            t[k] = nt[k]
        t["m_Resource"] = {**t["m_Resource"], "m_Offset": off, "m_Size": len(fsb)}
        b.replace_object(fname, o, typetree_bytes(o, t))
        done += 1
open(f"{out}/Data/resources.resource", "wb").write(blob)
for clip in blen:  # bundles próprios: troca o .resource inteiro, como nas músicas
    rel = f"{AA}/vs_local_assets_{clip.lower()}.bundle"
    nb = Bundle(bundle_path(BUILT, clip))
    (_, nfile), = nb.serialized()
    nt = next(x for x in nfile.objects.values() if x.type.name == "AudioClip").read_typetree()
    nres = nt["m_Resource"]["m_Source"].rsplit("/", 1)[-1]
    fsb = bytes(nb.raw[nres][nt["m_Resource"]["m_Offset"]:nt["m_Resource"]["m_Offset"] + nt["m_Resource"]["m_Size"]])
    vb = Bundle(f"{romfs}/{rel}")
    (vf, vfile), = vb.serialized()
    vo = next(o for o in vfile.objects.values() if o.type.name == "AudioClip")
    vt = vo.read_typetree()
    vres = vt["m_Resource"]["m_Source"].rsplit("/", 1)[-1]
    assert vt["m_Resource"]["m_Offset"] == 0 and len(vb.raw[vres]) == vt["m_Resource"]["m_Size"]
    vb.raw[vres] = bytearray(fsb)
    for kk in ("m_Length", "m_Frequency", "m_Channels", "m_BitsPerSample", "m_CompressionFormat"):
        vt[kk] = nt[kk]
    vt["m_Resource"] = {**vt["m_Resource"], "m_Size": len(fsb)}
    vb.replace_object(vf, vo, typetree_bytes(vo, vt))
    os.makedirs(os.path.dirname(f"{out}/{rel}"), exist_ok=True)
    vb.save(f"{out}/{rel}")
print(f"ok bundles de efeito: {len(blen)}")
print("ok efeitos:", done, "clipes;", REL, b.save(os.path.join(out, REL)), "; resources.resource", len(blob))
