#!/usr/bin/env python3
# Dados de uma DLC (<dlc>_persistent_assets_all.bundle no romfs da DLC: TextAssets enemyData_*, characterData_*…).
# Hoje só aplica os multiplicadores de escala dos inimigos que o reskin_enemies.py gravou em <overlay>/enemy_scales.json
# (mesma largura na tela = mesmo hitbox). Os nomes e textos das DLCs ficam no I2 do data.unity3d do jogo base.
# uso: python3 -P tools/patch_dlc_data.py <romfs da DLC> <overlay da DLC>
import sys, os, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -P tira a pasta do script do path
from unitypatch import Bundle, text_asset_bytes

romfs, out = sys.argv[1:3]
sp = os.path.join(out, "enemy_scales.json")
scales = json.load(open(sp)) if os.path.exists(sp) else {}
done = []
for p in glob.glob(os.path.join(romfs, "*persistent_assets_all.bundle")):
    b = Bundle(p)
    n = 0
    for fname, f in b.serialized():
        for o in list(f.objects.values()):
            if o.type.name != "TextAsset":
                continue
            d = o.read()
            if not d.m_Name.lower().startswith("enemydata"):
                continue
            raw = d.m_Script if isinstance(d.m_Script, str) else d.m_Script.decode("utf-8")
            try:
                j = json.loads(raw.lstrip("﻿"))
            except json.JSONDecodeError as e:
                j = json.loads(raw.lstrip("﻿")[:e.pos])
            hit = 0
            for key, m in scales.items():
                for entry in j.get(key, []):
                    entry["scale"] = round((entry.get("scale") or 1) * m, 4)
                    hit += 1
            if hit:
                b.replace_object(fname, o, text_asset_bytes(d.m_Name, json.dumps(j, ensure_ascii=False).encode()))
                n += hit
    dst = os.path.join(out, os.path.basename(p))
    os.makedirs(out, exist_ok=True)
    b.save(dst)
    done.append(f"{os.path.basename(p)}: {n} entradas com escala")
print("ok dados da DLC:", "; ".join(done) or "sem persistent_assets")
