#!/usr/bin/env python3
# Janela do Eden da bancada (o nightly em ~/vs-decomp), achada pelo PID: outra sessão pode ter um Eden próprio aberto
# (Exiled Kingdoms no ws 7, 17/10) e a classe "eden" é a mesma. Imprime "endereço workspace x,y wxh" ou nada.
import json, os, subprocess

def cmd(p):
    try:
        return open(f"/proc/{p}/cmdline", "rb").read().decode(errors="replace")
    except OSError:  # processo sumiu no meio da varredura
        return ""


pids = {int(p) for p in os.listdir("/proc") if p.isdigit() and "vs-decomp/tools/eden-nightly" in cmd(p)}
for c in json.loads(subprocess.run(["hyprctl", "clients", "-j"], capture_output=True, text=True).stdout):
    if c["pid"] in pids:
        print(c["address"], c["workspace"]["id"], "%d,%d %dx%d" % (*c["at"], *c["size"]))
        break
