#!/usr/bin/env python3
# Músicas do VS (bgm_* bundles: AudioClip mono 44,1 kHz Vorbis, CompressedInMemory, FSB5 no .resource) → BGM do RO
# (mapping/stages_music_ui_story.yaml music.tracks). O FSB5 Vorbis sai do Unity Editor local (Linux; o FSB é o
# mesmo formato do FMOD em qualquer plataforma) e é transplantado: .resource inteiro + m_Length/m_Frequency/
# m_Channels/m_Resource.m_Size do AudioClip.
# Clipe "_intro" (o VS toca intro e depois o loop): vira 0,5 s de silêncio e o loop leva a faixa inteira.
# uso: python3 -P tools/build_music.py <romfs> <overlay> [clipe ...]
import sys, os, re, subprocess, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -P tira a pasta do script do path
import yaml
from unitypatch import Bundle, typetree_bytes

romfs, out = sys.argv[1:3]
ONLY = set(sys.argv[3:])
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
AA = os.environ.get("VS_AA", "Data/StreamingAssets/aa/Switch")  # DLC: "" (bundles na raiz do romfs)
from paths import UNITY, BGM, work
PROJ = work("unity-audio")
BUILT = work("unity-audio-out")
COMPAT = os.path.expanduser("~/.local/opt/unity-compat/usr/lib")  # libxml2.so.2 (mesma solução do asset-catalog)

from mapping import section
music = section("music")
import glob as _g


def norm(c):
    """nome do clipe → nome no bundle (os das DLCs têm espaço e maiúscula: "A Quick Warm-up_intro")"""
    return c.lower().replace(" ", "")


def clip_bundle(c):
    """bundle do clipe: base vs_local_assets_<clip>.bundle; DLC <dlc>_dynamic_assets_<clip>.bundle"""
    if os.path.exists(os.path.join(romfs, AA, f"vs_local_assets_{norm(c)}.bundle")):
        return f"vs_local_assets_{norm(c)}.bundle"
    hits = sorted(_g.glob(os.path.join(romfs, AA, f"*_dynamic_assets_{_g.escape(norm(c))}.bundle")))
    return os.path.basename(hits[0]) if hits else None


jobs = {}  # clipe do VS -> número da faixa do RO
for t in music:
    m = re.match(r"\s*(\d+)", str(t.get("ro", "")))
    if not m:
        continue
    clips = t["clip"] if isinstance(t["clip"], list) else [t["clip"]]
    for c in clips:
        if (not ONLY or c in ONLY) and clip_bundle(c):
            jobs[c] = int(m.group(1))

import tempfile
from unity_audio import build as unity_build, bundle_path
tmp = tempfile.mkdtemp(prefix="rosurv-bgm-")
wavs = {}
for clip, n in jobs.items():
    dst = f"{tmp}/{norm(clip)}.wav"
    if "_intro" in clip.lower():
        cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "0.5", dst]
    else:
        cmd = ["ffmpeg", "-v", "error", "-y", "-i", f"{BGM}/{n:02d}.mp3", "-ac", "1", "-ar", "44100", dst]
    subprocess.run(cmd, check=True)
    wavs[norm(clip)] = dst
print(f"{len(jobs)} clipes decodificados; Unity em lotes…", flush=True)
unity_build(wavs, BUILT, "vorbis", "unity-audio")
shutil.rmtree(tmp, ignore_errors=True)

done = []
for clip, n in jobs.items():
    nb = Bundle(bundle_path(BUILT, norm(clip)))
    (nf, nfile), = nb.serialized()
    nclip = next(o for o in nfile.objects.values() if o.type.name == "AudioClip").read_typetree()
    nres = nclip["m_Resource"]["m_Source"].rsplit("/", 1)[-1]
    fsb = bytes(nb.raw[nres][nclip["m_Resource"]["m_Offset"]:nclip["m_Resource"]["m_Offset"] + nclip["m_Resource"]["m_Size"]])
    assert fsb[:4] == b"FSB5", "o .resource do Unity não começa com FSB5"
    rel = os.path.join(AA, clip_bundle(clip))
    vb = Bundle(f"{romfs}/{rel}")
    (vf, vfile), = vb.serialized()
    vo = next(o for o in vfile.objects.values() if o.type.name == "AudioClip")
    vt = vo.read_typetree()
    vres = vt["m_Resource"]["m_Source"].rsplit("/", 1)[-1]
    assert vt["m_Resource"]["m_Offset"] == 0 and len(vb.raw[vres]) == vt["m_Resource"]["m_Size"], "resource com mais coisa"
    vb.raw[vres] = bytearray(fsb)
    for k in ("m_Length", "m_Frequency", "m_Channels", "m_BitsPerSample", "m_CompressionFormat"):
        vt[k] = nclip[k]
    vt["m_Resource"] = {**vt["m_Resource"], "m_Size": len(fsb)}
    vb.replace_object(vf, vo, typetree_bytes(vo, vt))
    os.makedirs(os.path.dirname(f"{out}/{rel}"), exist_ok=True)
    vb.save(f"{out}/{rel}")
    done.append(f"{clip}←{n:02d} ({vt['m_Length']:.0f}s, {len(fsb) // 1024} KB)")
print("ok músicas:", "; ".join(done))
