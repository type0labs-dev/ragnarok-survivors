#!/usr/bin/env python3
# Troca o atlas de um personagem do VS pela classe do RO que mapping/characters_weapons.yaml dá pra ele, com o
# andar nas 8 direções.
# O VS ignora o pixels-per-unit (tamanho na tela = nº de pixels do sprite), então N é a densidade: cada caixa 32x32
# do original vira 32N x 32N; o hook (exl, PLAYER_ART_SCALE = 1/N) encolhe o jogador de volta. O RO é reduzido pra
# caber e recebe o tratamento retro: volta pra paleta do próprio quadro e alfa duro, sem dither.
# Sprites: os originais (andar leste, usados no menu e antes do 1º passo) + 8 direções × quadros do andar do RO
# como objetos novos "<prefixo>d{dir RO}_{01..}" (0 = sul, sentido horário, 6 = leste); o hook registra walk_d0..7.
# uso: python3 -P tools/reskin_char.py <romfs> <overlay> <VS_ID> [N] [cabelo]   ex.: ... ANTONIO 2
import sys, os, random, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -P tira a pasta do script do path
import yaml
from PIL import Image
from unitypatch import Bundle, typetree_bytes
from rosprite import compose, retro, stats, HUMAN, MONSTER
from roact import read_act

romfs, out, VS_ID = sys.argv[1:4]
N = int(sys.argv[4]) if len(sys.argv) > 4 else 2
HAIR = int(sys.argv[5]) if len(sys.argv) > 5 else 1
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

from mapping import vs_data, section, texture_index
AA = os.environ.get("VS_AA", "Data/StreamingAssets/aa/Switch")  # DLC: "" (bundles na raiz do romfs)
cd = vs_data("CHARACTER")[VS_ID][0]
_bn = f"vs_local_assets_{cd['textureName'].lower()}.bundle"
if not os.path.exists(os.path.join(romfs, AA, _bn)):  # DLC: <dlc>_dynamic_assets_character_x.bundle
    _bn = texture_index(romfs, AA)[cd["textureName"]][0]
REL = os.path.join(AA, _bn)
PREFIX = cd["spriteName"].replace("01.png", "")  # "newAntonio_"; o hook acha o personagem pelo mesmo prefixo
row = next(x for x in section("characters") if x["vs_id"] == VS_ID)
k = lambda t: t.encode("cp949").decode("latin1")  # nomes crus do GRF: coreano lido como latin1
# job do export (inglês) → nome cru do .act (os attach points da cabeça só existem no .act; o PNG exportado não tem)
KOR = {"novice": "초보자", "swordsman": "검사", "magician": "마법사", "archer": "궁수", "acolyte": "성직자",
       "merchant": "상인", "thief": "도둑", "knight": "기사", "wizard": "위저드", "hunter": "헌터",
       "priest": "프리스트", "blacksmith": "제철공", "assassin": "어세신", "crusader": "크루세이더", "sage": "세이지",
       "bard": "바드", "dancer": "무희", "monk": "몽크", "alchemist": "연금술사", "rogue": "로그",
       "lord_knight": "로드나이트", "high_wizard": "하이위저드", "sniper": "스나이퍼", "high_priest": "하이프리",
       "whitesmith": "화이트스미스", "assassin_cross": "어쌔신크로스", "paladin": "팔라딘", "professor": "프로페서",
       "clown": "클라운", "gypsy": "집시", "champion": "챔피온", "creator": "크리에이터", "stalker": "스토커",
       "taekwon": "태권소년", "star_gladiator": "권성", "soul_linker": "소울링커", "건너": "건너", "gunslinger": "건너",
       "ninja": "닌자", "super_novice": "슈퍼노비스", "rune_knight": "룬나이트", "warlock": "워록", "ranger": "레인져",
       "arch_bishop": "아크비숍", "mechanic": "미케닉", "guillotine_cross": "길로틴크로스", "royal_guard": "가드",
       "sorcerer": "소서러", "minstrel": "민스트럴", "wanderer": "원더러", "sura": "슈라", "genetic": "제네릭",
       "shadow_chaser": "쉐도우체이서", "star_emperor": "성제", "soul_reaper": "소울리퍼", "rebellion": "rebellion",
       "kagerou": "kagerou", "oboro": "oboro", "magic_gear": "마도기어", "santa": "산타"}
ref = row["ro_ref"].split()[0]  # body/female/x_female | doram/body/male/summoner_male | npc/4_poring | monster/GRAND_PECO
WALK, SOUTH = 1, 0  # ação andar; direção sul (card da seleção, pedido do Zero)
PICK = (0, 2, 4, 6)          # 4 dos 8 quadros do andar do RO → _01.._04 do VS
if ref.startswith(("body/", "doram/")):
    kind = "jogador"
    bits = ref.split("/")
    gender, job_g = bits[-2], bits[-1]
    G = {"male": "남", "female": "여"}[gender]
    base, _, extra = job_g.partition(f"_{gender}")  # rebellion_female_권총 → rebellion + _권총
    h = base.endswith("_h")
    job = base[:-2] if h else base
    raw = (KOR[job] if job in KOR else job) + ("_h" if h else "") + "_" + G + extra
    if ref.startswith("doram/"):
        D = f"{HUMAN}/../{k('도람족')}"
        PARTS = [f"{D}/{k('몸통')}/{k(G)}/{k(raw)}.act", f"{D}/{k('머리통')}/{k(G)}/{k(f'1_{G}')}.act"]
    else:
        PARTS = [f"{HUMAN}/{k('몸통')}/{k(G)}/{k(raw)}.act", f"{HUMAN}/{k('머리통')}/{k(G)}/{k(f'{HAIR}_{G}')}.act"]
else:
    # NPC ou monstro jogável (Zero: como o VS faz com alguns inimigos). Monstro tem andar em 8 direções; NPC às vezes
    # só fica parado e/ou tem 1 direção — aí as 8 direções repetem o que existe.
    name = ref.split("/")[-1].lower()
    mon = f"{MONSTER}/{name}.act"
    if os.path.exists(mon) and os.path.exists(mon[:-4] + ".spr"):
        kind, PARTS = "monstro", [mon]
    else:
        kind, PARTS = "npc", [f"{HUMAN}/../npc/{name}.act"]
acts0 = read_act(PARTS[0])[1]
NDIR = 8 if len(acts0) >= 8 else 1
WALK = WALK if len(acts0) >= 16 and acts0[WALK * 8] else 0
idx = lambda d: WALK * 8 + (d if NDIR == 8 else 0)
n_mot = len(acts0[idx(0)])
job_g = ref.split("/")[-1]
print(f"{VS_ID}: {kind} {job_g}, {len(acts0)} ações×dir, {NDIR} direções, ação {WALK}, {n_mot} quadros")

# todas as direções na mesma tela: recorte comum mantém a origem do RO (pé) no mesmo ponto em todos os quadros
canv = {(d, m): compose(PARTS, idx(d), m, shadow=True, crop=False, size=512) for d in range(8) for m in range(n_mot)}
boxes = [c.getbbox() for c in canv.values()]
U = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
canv = {k: c.crop(U) for k, c in canv.items()}
# o hook registra exatamente 8 quadros por direção (kDirFrames): reamostra quem tem outra contagem (NPC, monstro)
canv = {(d, m): canv[(d, m * n_mot // 8)] for d in range(8) for m in range(8)}
n_mot = 8

b = Bundle(os.path.join(romfs, REL))
(fname, f), = b.serialized()
tex = next(o for o in f.objects.values() if o.type.name == "Texture2D")
sprites = [o for o in f.objects.values() if o.type.name == "Sprite"]

src = tex.read().image.convert("RGBA")
# caixa do sprite de andar do VS (<prefixo>01) × N: a grade nova usa ela e a escala do RO cabe nela. As caixas do
# original variam (Antonio 31..34, Poe 26..32, nem sempre quadradas); sprite antigo menor recebe o quadro reduzido.
t0 = next(o.read_typetree() for o in sprites if o.read_typetree()["m_Name"] == f"{PREFIX}01")
cw, ch = int(t0["m_Rect"]["width"]) * N, int(t0["m_Rect"]["height"]) * N
uw, uh = U[2] - U[0], U[3] - U[1]
scale = min(1.0, (ch - 2) / uh, cw / uw)
before = stats(list(canv.values()))
frames = {k: retro(c, scale) for k, c in canv.items()}
print(f"escala RO {scale:.2f}; recorte comum {uw}x{uh}; caixa {cw}x{ch}; cores {before[0]}→{stats(list(frames.values()))[0]}")
fw, fh = next(iter(frames.values())).size

# atlas: área original em 1× embaixo à esquerda (rects do Unity são medidos de baixo; os sprites do VS ficam com o
# tamanho de antes e a UI — card do menu, resultados — desenha no tamanho certo; no jogo o hook troca pro andar RO
# logo no InitCharacter), grade 8×n_mot das direções em N× em cima
old_w, old_h = src.width, src.height
W, H = max(old_w, n_mot * cw), old_h + 8 * ch
atlas = Image.new("RGBA", (W, H))  # imagem de cima pra baixo; em branco (sobras do original viravam riscos)


def paste(fr, bx, by_unity, bw):
    """caixa de largura bw com canto inferior esquerdo em (bx, by) no sistema do Unity; pé no fundo, 1px de margem"""
    atlas.paste(fr, (bx + (bw - fr.width) // 2, H - by_unity - 1 - fr.height), fr)


def card_frame(fi, bw, bh):
    """quadro sul pra uma caixa antiga (1×: card da seleção, resultados), reduzido de novo a partir do RO cru"""
    key = (SOUTH, PICK[fi % len(PICK)])
    return retro(canv[key], min(scale, (bh - 2) / uh, bw / uw))


for o in sprites:
    t = o.read_typetree()
    r = t["m_Rect"]
    fi = int(t["m_Name"][-2:]) - 1 if t["m_Name"][-2:].isdigit() else 0  # _01.._04; legacy/skin reaproveita
    paste(card_frame(fi, int(r["width"]), int(r["height"])), int(r["x"]), int(r["y"]), int(r["width"]))
    if t["m_Name"] == f"{PREFIX}01":  # molde dos sprites novos: campos em pixel ×N (malha e pivô ficam)
        o0, t0 = o, t
        for key in ("m_Rect", "m_Offset", "m_Border"):
            t0[key] = {a: v * N for a, v in t0[key].items()}
        t0["m_PixelsToUnits"] *= N
        for key in ("textureRect", "textureRectOffset", "uvTransform"):  # uvTransform = (ppu, cx, ppu, cy)
            t0["m_RD"][key] = {a: v * N for a, v in t0["m_RD"][key].items()}

# 8 direções: cópias do newAntonio_01 (mesma caixa, pivô e malha) com rect/uv deslocados e nome novo
rng = random.Random(0x524F)  # path_ids fixos entre execuções
used = {o.path_id for o in f.objects.values()}
new, names = [], []
for d in range(8):
    for m in range(n_mot):
        bx, by = m * cw, old_h + (7 - d) * ch
        paste(frames[(d, m)], bx, by, cw)
        t = {**t0, "m_Name": f"{PREFIX}d{d}_{m + 1:02d}", "m_RD": dict(t0["m_RD"])}
        dx, dy = bx - t0["m_Rect"]["x"], by - t0["m_Rect"]["y"]
        t["m_Rect"] = {**t0["m_Rect"], "x": float(bx), "y": float(by)}
        rd = t["m_RD"]
        rd["textureRect"] = {**rd["textureRect"], "x": rd["textureRect"]["x"] + dx, "y": rd["textureRect"]["y"] + dy}
        uv = rd["uvTransform"]
        rd["uvTransform"] = {**uv, "y": uv["y"] + dx, "w": uv["w"] + dy}
        key, k2 = t0["m_RenderDataKey"]
        t["m_RenderDataKey"] = ({**key, "data[0]": (key["data[0]"] + 1 + len(new)) & 0xFFFFFFFF}, k2)
        pid = rng.getrandbits(63)
        assert pid not in used
        used.add(pid)
        new.append((pid, list(f.types).index(o0.serialized_type), typetree_bytes(o0, t)))
        names.append(t["m_Name"])

tt = tex.read_typetree()
res = tt["m_StreamData"]["path"].rsplit("/", 1)[-1]
assert tt["m_StreamData"]["offset"] == 0 and len(b.raw[res]) == tt["m_StreamData"]["size"], "resS com mais coisa"
px = atlas.transpose(Image.FLIP_TOP_BOTTOM).tobytes()
tt["m_Width"], tt["m_Height"] = atlas.size
tt["m_CompleteImageSize"] = tt["m_StreamData"]["size"] = len(px)
b.raw[res] = bytearray(px)
b.replace_object(fname, tex, typetree_bytes(tex, tt))

# AssetBundle: os sprites novos entram no preload e no container sob a mesma chave da textura (o jogo carrega
# todos os sub-assets da chave e procura por m_Name; catálogo do Addressables não muda)
ab = next(o for o in f.objects.values() if o.type.name == "AssetBundle")
at = ab.read_typetree()
assert len(at["m_PreloadTable"]) == len(at["m_Container"]) and len({c[0] for c in at["m_Container"]}) == 1
key = at["m_Container"][0][0]
at["m_PreloadTable"] = sorted(at["m_PreloadTable"] + [{"m_FileID": 0, "m_PathID": p} for p, _, _ in new],
                              key=lambda e: e["m_PathID"])
at["m_Container"] += [(key, {"preloadIndex": 0, "preloadSize": 0, "asset": {"m_FileID": 0, "m_PathID": p}})
                      for p, _, _ in new]
for _, info in at["m_Container"]:
    info["preloadSize"] = len(at["m_PreloadTable"])
b.replace_object(fname, ab, typetree_bytes(ab, at))
b.add_objects(fname, new)

dst = os.path.join(out, REL)
os.makedirs(os.path.dirname(dst), exist_ok=True)
print("ok", VS_ID, "->", job_g, REL, b.save(dst), f"atlas {atlas.size}, quadro {fw}x{fh} na caixa {cw}x{ch}, {len(new)} sprites novos "
      f"({names[0]}..{names[-1]})")
atlas.save(os.path.join(out, f"preview_{VS_ID}.png"))
