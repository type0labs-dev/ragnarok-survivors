# Pastas de entrada, num lugar só. O padrão é a bancada do Zero; quem usa o construtor define pelo ambiente (o
# build.py preenche a partir dos argumentos):
#   RO_DATA  pasta "data" extraída do data.grf (tools/grf.py)
#   RO_BGM   pasta BGM do cliente do RO (opcional: sem ela a música fica a do VS)
#   VS_WORK  pasta de trabalho (JSON do jogo, índices, projetos de áudio)
import os

RAG = os.environ.get("RO_DATA", "/mnt/data/games/02 - RagData Extracted/data")
BGM = os.environ.get("RO_BGM", "/mnt/data/games/01 - Ragnarok RE/BGM")
WORK = os.path.expanduser(os.environ.get("VS_WORK", "~/vs-decomp"))
UI = f"{RAG}/texture/" + "유저인터페이스".encode("cp949").decode("latin1")


def work(*p):
    return os.path.join(WORK, *p)


# opcionais: Unity Editor 6000.6.2f1 (gera o FSB5 da música e dos sons; sem ele o áudio fica o do VS) e a fonte dos
# textos desenhados (padrão: Noto Serif Bold do sistema)
UNITY = os.path.expanduser(os.environ.get("UNITY_EDITOR", "~/Unity/Hub/Editor/6000.6.2f1/Editor/Unity"))


def font():
    import subprocess
    return os.environ.get("RS_FONT") or subprocess.check_output(["fc-match", "-f", "%{file}", "Noto Serif:bold"]).decode()
