#!/usr/bin/env python3
# Patch do data.unity3d: campos do JSON (*_DATA) e textos da tela (I2Languages). Números de gameplay ficam os do VS.
# uso: python3 -P tools/patch_data.py <romfs> <overlay>
import sys, os, json, re
import yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -P tira a pasta do script do path
from unitypatch import Bundle, I2Terms, text_asset_bytes

romfs, out = sys.argv[1], sys.argv[2]
REL = "Data/data.unity3d"

# Nomes vêm de mapping/*.yaml (fonte da verdade do de-para); só os campos de JSON ainda ficam aqui.
# (TextAsset, chave) -> campos. CHARACTER_DATA.scale não afeta o jogador (testado); ENEMY_DATA.scale vira
# _scaleMul → transform.localScale do inimigo (EnemyController.InitialiseLocalData/UpdateScale).
JSON_EDITS = {}
# multiplicadores de ENEMY_DATA.scale que o reskin_enemies.py grava no overlay (mesma largura na tela = mesmo hitbox)
_sp = os.path.join(out, "enemy_scales.json")
ENEMY_SCALES = json.load(open(_sp)) if os.path.exists(_sp) else {}
PT = 5  # índice do PT-BR no I2Languages (0 = EN); os outros 12 idiomas recebem o EN (decisão padrão do plano)
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mapping")


def clean(v):
    """'Swordman (M)' -> 'Swordman', 'Névoa Venenosa [trad]' -> 'Névoa Venenosa': o que vai pra tela"""
    v = re.sub(r"\s*(\([^)]*\)|\[[^\]]*\])", "", str(v)).strip()
    return v.rstrip("?").strip()


def mapping_texts():
    """Nomes da tela a partir de mapping/*.yaml: termo I2 -> (EN, PT-BR). Descrições ficam as do VS por enquanto."""
    from mapping import section  # jogo base + mapping/dlc/*.yaml (os termos das DLCs também moram neste I2)
    cw = {k: section(k) for k in ("characters", "weapons", "passives", "powerups")}
    it = {k: section(k) for k in ("pickups", "relics", "arcanas")}
    en = {"enemies": section("enemies")}
    st = {"stages": section("stages")}
    out = {}
    def put(key, x):
        if key in out or x.get("scope") == "later" or x.get("parent") or not clean(x.get("ro_en") or ""):  # 1ª linha vence (GEM tem 3 tiers)
            return
        out[key] = (clean(x["ro_en"]), clean(x.get("ro_ptbr") or x["ro_en"]))
    for x in cw["characters"]:
        put(f"characterLang/{{{x['vs_id']}}}charName", x)
        if f"characterLang/{{{x['vs_id']}}}charName" in out:
            out[f"characterLang/{{{x['vs_id']}}}surname"] = (" ", " ")  # vazio faria o I2 cair na chave
    for x in cw["weapons"] + cw["passives"]:
        put(f"weaponLang/{{{x['vs_id']}}}name", x)
    for x in cw["powerups"]:
        put(f"powerUpLang/{{{x['vs_id']}}}name", x)
    for x in it["pickups"] + it["relics"]:
        put(f"itemLang/{{{x['vs_id']}}}name", x)
    for x in it["arcanas"]:
        put(f"arcanaLang/{{{x['vs_id']}}}name", x)
    for x in en["enemies"]:
        for vid in x.get("vs_ids") or []:
            put(f"enemiesLang/{{{vid}}}bName", x)
    for x in st["stages"]:
        if x.get("en_name"):
            out[f"stageLang/{{{x['vs_id']}}}stageName"] = (x["en_name"], x.get("ptbr_name") or x["en_name"])
    return out


TEXTS = mapping_texts()
# descrições, dicas, bestiário, conquistas…: mapping/texts/*.json {termo: {en, pt}} (reescritos com as mecânicas e
# números do VS intactos); nomes do YAML vencem se o mesmo termo aparecer nos dois
for _fn in sorted(os.listdir(os.path.join(ROOT, "texts"))) if os.path.isdir(os.path.join(ROOT, "texts")) else []:
    if _fn.endswith(".json"):
        for _k, _v in json.load(open(os.path.join(ROOT, "texts", _fn), encoding="utf-8")).items():
            if _k not in TEXTS and isinstance(_v, dict) and _v.get("en"):
                TEXTS[_k] = (_v["en"], _v.get("pt") or _v["en"])

b = Bundle(os.path.join(romfs, REL))
for n, f in b.serialized():
    for o in list(f.objects.values()):
        if o.type.name == "TextAsset":
            d = o.read()
            edits = {k[1]: v for k, v in JSON_EDITS.items() if k[0] == d.m_Name}
            mul = ENEMY_SCALES if d.m_Name == "ENEMY_DATA" else {}
            if edits or mul:
                j = json.loads(d.m_Script)
                for key, fields in edits.items():
                    for entry in j[key]:  # cada nível/variação do registro
                        entry.update(fields)
                for key, m in mul.items():
                    for entry in j.get(key, []):
                        entry["scale"] = round((entry.get("scale") or 1) * m, 4)
                print(f"ENEMY_DATA: escala de {len(mul)} inimigos" if mul else "", end="")
                b.replace_object(n, o, text_asset_bytes(d.m_Name, json.dumps(j, ensure_ascii=False).encode()))
        elif o.type.name == "MonoBehaviour" and b"I2Languages" in o.get_raw_data()[:64]:
            t = I2Terms(o.get_raw_data())
            hit = 0
            for key, (en, pt) in TEXTS.items():
                if key not in t.index:
                    continue
                langs = [en] * len(t.index[key][2])
                if len(langs) > PT:
                    langs[PT] = pt
                t.index[key][2] = langs
                hit += 1
            print(f"I2: {hit}/{len(TEXTS)} nomes do mapping aplicados")
            b.replace_object(n, o, t.save())
dst = os.path.join(out, REL)
os.makedirs(os.path.dirname(dst), exist_ok=True)
print("ok", REL, b.save(dst))
