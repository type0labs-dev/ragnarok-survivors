#!/usr/bin/env python3
# Inventário de um arquivo Unity (data.unity3d ou .bundle): conta tipos, lista TextAssets e texturas/sprites.
# uso: python3 -I tools/inventory.py <arquivo> [filtro-de-nome]
import sys, collections
import UnityPy

env = UnityPy.load(sys.argv[1])
flt = sys.argv[2].lower() if len(sys.argv) > 2 else None
count = collections.Counter()
rows = []
for obj in env.objects:
    t = obj.type.name
    count[t] += 1
    if t not in ("TextAsset", "Texture2D", "Sprite", "SpriteAtlas", "AudioClip"):
        continue
    d = obj.read()
    name = getattr(d, "m_Name", "")
    if flt and flt not in name.lower():
        continue
    if t == "TextAsset":
        rows.append(f"TextAsset {name} {len(d.m_Script)}B")
    elif t == "Texture2D":
        rows.append(f"Texture2D {name} {d.m_Width}x{d.m_Height} fmt={d.m_TextureFormat}")
    elif t == "Sprite":
        r = d.m_Rect
        rows.append(f"Sprite {name} {r.width:.0f}x{r.height:.0f} ppu={d.m_PixelsToUnits}")
    else:
        rows.append(f"{t} {name}")
print(dict(count.most_common(12)))
for r in rows[:int(sys.argv[3]) if len(sys.argv) > 3 else 60]:
    print(r)
print(f"... {len(rows)} linhas")
