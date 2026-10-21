#!/usr/bin/env python3
# Cópias dos atlas de inimigos dentro do data.unity3d (resources.assets "enemies", sharedassets1 "enemies2"/"enemiesM")
# com uns poucos sprites (Mud/Mudman1, Ghost…) que o jogo desenha daqui e não do bundle. Depois do reskin_enemies:
# a textura recebe a imagem do atlas do bundle já trocado (inline RGBA32) e cada sprite que aponta pra ela copia
# rect/malha do sprite de mesmo nome do bundle (as referências PPtr do data.unity3d ficam).
# uso: python3 -P tools/sync_data_atlases.py <romfs> <overlay>   (rodar depois do patch_data e do reskin_enemies)
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -P tira a pasta do script do path
from unitypatch import Bundle, typetree_bytes

romfs, out = sys.argv[1:3]
AA = "Data/StreamingAssets/aa/Switch"
DATA = "Data/data.unity3d"
NAMES = {"enemies", "enemies2", "enemiesm"}  # nome da textura (minúsculo) = sufixo do bundle vs_local_assets_<nome>
COPY = ("m_Rect", "m_Offset", "m_Border", "m_PixelsToUnits", "m_Pivot", "m_Extrude", "m_IsPolygon", "m_PhysicsShape")
KEEP_RD = ("texture", "alphaTexture", "secondaryTextures")

src = os.path.join(out, DATA) if os.path.exists(os.path.join(out, DATA)) else os.path.join(romfs, DATA)
b = Bundle(src)
files = dict(b.serialized())
texs = {(fn, pid): o for fn, f in files.items() for pid, o in f.objects.items()
        if o.type.name == "Texture2D" and o.read().m_Name.lower() in NAMES}
done = []
for (tfn, tpid), tex in texs.items():
    name = tex.read().m_Name.lower()
    nb = Bundle(os.path.join(out, AA, f"vs_local_assets_{name}.bundle"))
    (_, nf), = nb.serialized()
    ntex = next(o for o in nf.objects.values() if o.type.name == "Texture2D")
    nspr = {o.read_typetree()["m_Name"].lower(): o.read_typetree() for o in nf.objects.values()
            if o.type.name == "Sprite"}
    b.set_texture_rgba(tex, ntex.read().image)
    n, miss = 0, []
    for fn, f in files.items():
        ext = [e.path.rsplit("/", 1)[-1] for e in f.externals]
        for o in list(f.objects.values()):
            if o.type.name != "Sprite":
                continue
            t = o.read_typetree()
            r = t["m_RD"]["texture"]
            if (fn if r["m_FileID"] == 0 else ext[r["m_FileID"] - 1]) != tfn or r["m_PathID"] != tpid:
                continue
            s = nspr.get(t["m_Name"].lower())
            if not s:
                miss.append(t["m_Name"])
                continue
            for k in COPY:
                if k in s:
                    t[k] = s[k]
            t["m_RD"] = {**s["m_RD"], **{k: t["m_RD"][k] for k in KEEP_RD if k in t["m_RD"]}}
            b.replace_object(fn, o, typetree_bytes(o, t))
            n += 1
    done.append(f"{name}: {n} sprites" + (f" (sem par no bundle: {miss})" if miss else ""))
os.makedirs(os.path.dirname(os.path.join(out, DATA)), exist_ok=True)
b.save(os.path.join(out, DATA))
print("ok atlas do data.unity3d:", "; ".join(done))
