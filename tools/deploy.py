#!/usr/bin/env python3
"""Publica mod/ no SD do console por FTP, com readback SHA-256 por arquivo. Só escreve dentro de
/atmosphere/contents/010089A0197E4000 e (sem exefs); nunca toca saves.
Uso: deploy.py [--host IP] [--only <trecho do caminho>] [--rm <pasta remota>]...   (login anônimo, como o ftpd do sphaira aceita)"""
import ftplib, hashlib, io, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent / "mod"
ALLOWED = ("atmosphere/contents/010089A0197E4000/",) + tuple(f"atmosphere/contents/010089A0197E500{i}/" for i in range(1, 8))  # jogo + 7 DLCs

_made = set()

def mkdirs(ftp, path):
    cur = ""
    for part in path.split("/")[:-1]:
        cur += "/" + part
        if cur in _made: continue
        try: ftp.mkd(cur)
        except ftplib.error_perm: pass
        _made.add(cur)

def rmtree(ftp, path):
    """Apaga uma pasta remota, só dentro da área permitida."""
    assert path.lstrip("/").startswith(ALLOWED), f"fora da área permitida: {path}"
    for e in ftp.nlst(path):
        e = e if e.startswith("/") else f"{path}/{e.split('/')[-1]}"
        try: ftp.delete(e)
        except ftplib.error_perm: rmtree(ftp, e)
    ftp.rmd(path)

def main(host="192.168.68.127", port=5000, remove=(), only=None):
    ftp = ftplib.FTP(); ftp.connect(host, port, timeout=60); ftp.login()
    for r in remove:
        try: rmtree(ftp, r); print("removido:", r)
        except ftplib.error_perm as e: print("nada a remover:", r, e)
    files = sorted(p for p in ROOT.rglob("*") if p.is_file() and (not only or only in p.as_posix()))
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        assert rel.startswith(ALLOWED), f"fora da área permitida: {rel}"
        data = p.read_bytes()
        mkdirs(ftp, rel)
        ftp.storbinary(f"STOR /{rel}", io.BytesIO(data))
        back = io.BytesIO(); ftp.retrbinary(f"RETR /{rel}", back.write)
        if hashlib.sha256(back.getvalue()).digest() != hashlib.sha256(data).digest():
            raise SystemExit(f"readback divergente: {rel}")
    ftp.quit()
    print(f"ok: {len(files)} arquivos publicados e conferidos")

if __name__ == "__main__":
    # uso: deploy.py [--rm /atmosphere/contents/010089A0197E4000/romfs/...] ...
    rm = [sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--rm"]
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None  # ex.: --only /exefs/
    host = sys.argv[sys.argv.index("--host") + 1] if "--host" in sys.argv else "192.168.68.127"
    main(host=host, remove=rm, only=only)
