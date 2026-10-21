#!/usr/bin/env python3
# Carrega o de-para: mapping/*.yaml do jogo base + mapping/dlc/*.yaml (as DLCs usam os mesmos campos; ids não se
# repetem). section("characters") devolve a lista juntando base e DLCs; dict_section("tilesets") junta os dicts.
# Também junta os dados do VS do jogo base (~/vs-decomp/data) com os das DLCs (~/vs-decomp/dlc/*/data).
import os, glob, json, yaml
from paths import work

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mapping")
BASE = {"characters": "characters_weapons", "weapons": "characters_weapons", "passives": "characters_weapons",
        "powerups": "characters_weapons", "vfx_families": "characters_weapons", "weapon_bundles": "characters_weapons",
        "enemies": "enemies", "ro_variant_pools": "enemies", "ro_variant_overrides": "enemies", "pickups": "items", "relics": "items", "arcanas": "items", "props": "items",
        "npcs": "items", "sprite_variants": "items", "sprite_families": "items", "stages": "stages_music_ui_story",
        "tilesets": "stages_music_ui_story", "backgrounds": "stages_music_ui_story", "sfx_clips": "stages_music_ui_story",
        "sfx_bundles": "stages_music_ui_story"}
_cache = {}


def _y(path):
    if path not in _cache:
        _cache[path] = yaml.safe_load(open(path, encoding="utf-8")) or {}
    return _cache[path]


def _dlc_docs():
    if os.environ.get("VS_DLC") != "1":  # Zero, 2026-10-16: DLCs fora do escopo; mapping/dlc fica guardado
        return
    """cada arquivo de DLC pode ter as seções no topo ou dentro de uma chave por DLC (moonspell: {characters: …})"""
    for p in sorted(glob.glob(f"{ROOT}/dlc/*.yaml")):
        d = _y(p)
        if any(isinstance(v, dict) and ("characters" in v or "enemies" in v or "stages" in v) for v in d.values()):
            for v in d.values():
                if isinstance(v, dict):
                    yield v
        else:
            yield d


def section(name):
    if name == "music":
        out = list((_y(f"{ROOT}/stages_music_ui_story.yaml")["music"].get("tracks")) or [])
    else:
        out = list((_y(f"{ROOT}/{BASE.get(name, name)}.yaml").get(name)) or [])
    for d in _dlc_docs():
        v = d.get(name)
        if name == "music" and isinstance(v, dict):
            v = v.get("tracks")
        if isinstance(v, list):
            out += v
    return out


def dict_section(name):
    out = dict((_y(f"{ROOT}/{BASE.get(name, name)}.yaml").get(name)) or {})
    for d in _dlc_docs():
        if isinstance(d.get(name), dict):
            for k, v in d[name].items():
                out.setdefault(k, v)
    return out


def _load_json(p):
    raw = open(p, encoding="utf-8-sig").read()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:  # alguns arquivos do VS têm lixo depois do JSON
        return json.loads(raw[:e.pos])


def vs_data(kind):
    """kind: CHARACTER / ENEMY / WEAPON / STAGE / ITEM …: base (KIND_DATA.json) + DLCs (kindData_*.json)"""
    out = dict(_load_json(work("data", f"{kind}_DATA.json")))
    camel = kind.lower() + "Data_"
    for p in [] if os.environ.get("VS_DLC") != "1" else sorted(glob.glob(work("dlc", "*", "data", f"{camel}*.json"))):
        try:
            for k, v in _load_json(p).items():
                out.setdefault(k, v)
        except Exception:
            pass
    return out


if __name__ == "__main__":
    print({s: len(section(s)) for s in ("characters", "weapons", "enemies", "stages", "music")},
          {k: len(vs_data(k)) for k in ("CHARACTER", "ENEMY", "WEAPON")})


def texture_index(romfs, aa):
    """{nome da textura: [bundles]} de um romfs, calculado uma vez por romfs (varrer centenas de bundles leva minutos)"""
    import hashlib, UnityPy
    key = hashlib.md5(os.path.realpath(romfs).encode()).hexdigest()[:8]
    cache = work(f"texture_index_{key}.json")
    if os.path.exists(cache):
        return json.load(open(cache))
    old = work("texture_index.json")  # índice antigo = romfs do jogo base
    if os.path.realpath(romfs) == os.path.realpath(work("romfs")) and os.path.exists(old):
        return json.load(open(old))
    idx = {}
    d = os.path.join(romfs, aa)
    for bn in sorted(os.listdir(d)):
        if not bn.endswith(".bundle") or "bgm" in bn:
            continue
        try:
            for o in UnityPy.load(os.path.join(d, bn)).objects:
                if o.type.name == "Texture2D":
                    idx.setdefault(o.read().m_Name, []).append(bn)
        except Exception:
            pass
    json.dump(idx, open(cache, "w"))
    return idx
