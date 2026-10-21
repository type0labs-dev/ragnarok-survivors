#!/usr/bin/env python3
# Roda o Unity Editor local (projeto ~/vs-decomp/unity-audio) pra transformar WAVs em AssetBundles com FSB5.
# Em lotes: com ~170 clipes de uma vez o Editor dá SIGSEGV no meio da importação (visto com as faixas das DLCs);
# lotes de 40 com 1 nova tentativa resolvem. Cada lote sai numa pasta própria; bundle_path() acha o do clipe.
import os, glob, shutil, subprocess

from paths import UNITY, work
PROJ = work("unity-audio")
COMPAT = os.path.expanduser("~/.local/opt/unity-compat/usr/lib")  # libxml2.so.2 (mesma solução do asset-catalog)
CHUNK = 40


def build(wavs, out, fmt="vorbis", log="unity-audio"):
    """wavs: {nome do clipe: caminho do wav}; gera <out>/<lote>/<clipe> (AssetBundle descomprimido)"""
    root = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isdir(f"{PROJ}/ProjectSettings"):  # 1ª vez: projeto vazio
        subprocess.run([UNITY, "-batchmode", "-nographics", "-quit", "-createProject", PROJ,
                        "-logFile", work("unity-create.log")], env=dict(os.environ, LD_LIBRARY_PATH=COMPAT))
    os.makedirs(f"{PROJ}/Assets/Editor", exist_ok=True)
    shutil.copy(os.path.join(root, "unity", "BuildAudio.cs"), f"{PROJ}/Assets/Editor/BuildAudio.cs")
    shutil.rmtree(out, ignore_errors=True)
    names = sorted(wavs)
    for i in range(0, len(names), CHUNK):
        audio = f"{PROJ}/Assets/Audio"
        shutil.rmtree(audio, ignore_errors=True)
        os.makedirs(audio)
        for n in names[i:i + CHUNK]:
            shutil.copy(wavs[n], f"{audio}/{n.lower()}.wav")
        dst = f"{out}/{i // CHUNK:03d}"
        for attempt in range(2):
            r = subprocess.run([UNITY, "-batchmode", "-nographics", "-quit", "-projectPath", PROJ, "-executeMethod",
                                "BuildAudio.Run", "-out", dst, "-format", fmt,
                                "-logFile", work(f"{log}-{i // CHUNK:03d}.log")],
                               env=dict(os.environ, LD_LIBRARY_PATH=COMPAT))
            if all(os.path.exists(f"{dst}/{n.lower()}") for n in names[i:i + CHUNK]):
                break  # o Editor às vezes cai ao sair depois de gravar tudo: vale o que está no disco
        else:
            missing = [n for n in names[i:i + CHUNK] if not os.path.exists(f"{dst}/{n.lower()}")]
            raise SystemExit(f"Unity falhou no lote {i // CHUNK} (rc {r.returncode}); faltam {missing[:5]}")


def bundle_path(out, clip):
    hits = glob.glob(f"{out}/*/{clip.lower()}")
    return hits[0] if hits else None
