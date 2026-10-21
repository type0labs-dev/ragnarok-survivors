# Ragnarok Survivors: full VS → RO mapping plan

Goal: every visual, name, sound and text in Vampire Survivors becomes Ragnarok Online, while the VS gameplay
numbers stay exactly as they are. The RO counterpart of each thing is picked by what it does on screen
(the mechanic) first and by theme second.

## Sources of truth (this folder)

| File | Covers | Entries |
|---|---|---|
| `CAST.md` | cast parallel: VS unlock tier, perks and weapon → RO job change | 24 main + tiers |
| `characters_weapons.yaml` | characters, weapons/evolutions, passives, shop PowerUps | 68 / 125 / 26 / 29 |
| `enemies.yaml` | all 303 VS enemy sprite families (192 used by stages; bosses; events) | 303 |
| `items.yaml` | pickups, relics, arcanas, props/destructibles, map NPCs | 43 / 47 / 35 / 23 / 7 |
| `stages_music_ui_story.yaml` | 24 stages, 46 music ids, SFX, UI/branding, text strategy | |
| `TECH_NOTES.md` | verified formats and risk level for stages, audio, SFX, UI, fonts | |

Every entry has `confidence` (high/med/low) and `asset` (ok / str / missing). The drafts were written by four
parallel passes on 2026-10-16 and then cross-checked (stage regions unified, see below). Low-confidence rows are
review material, not decisions.

## Rules

1. Playable characters = RO **classes + NPCs + monsters** (Zero, 2026-10-16). The main VS roster becomes jobs.
   The odd/secret VS characters become iconic NPCs or monsters, the same way VS makes some enemies playable
   (Mortaccio → Skeleton, Exdash → Lunatic, Avatar → Baphomet, Nostro/Red Death → Death...).
2. A character keeps its VS starting weapon, and that weapon's RO skill belongs to the character's job.
3. Weapon → RO skill; evolution → the stronger or higher-job version of that skill; passive → an RO item or
   card whose effect matches the stat; shop PowerUp → stat or buff (STR/AGI/…, Blessing, Increase AGI…).
4. Stage → RO region. **Monster ecology wins**: the stage's enemies must live in, or fit, that region.
5. Bosses → MVPs and minibosses. Swarm fodder → small common mobs.
6. Names in EN + PT-BR (official bRO names where known; `[trad]` marks our own translation).
7. Scope v1 = base game + EXTRA (free content). The 7 DLCs (art already in the base romfs, data in their own
   titles) are later expansions, each one an RO episode.

## Stage → region (canonical)

| VS stage | RO region | BGM normal / B |
|---|---|---|
| Mad Forest | Payon forest | 03 / 36 |
| Inlaid Library | Glast Heim Castle (Rideword, Raydric) | 43 / 44 |
| Dairy Plant | Einbroch | 86 / 88 |
| Gallo Tower | Clock Tower (Al De Baran) | 60 / 61 |
| Cappella Magna | Nameless Island, Cursed Abbey | 113 / 112 |
| Il Molise | Umbala | 68 |
| Moongolow | Byalan Island | 29 / 49 |
| Green Acres | Prontera fields | 05 |
| Bone Zone | Niflheim | 84 / 85 |
| Boss Rash | Endless Tower | 123 / 125 |
| Eudaimonia M. | Juperos / Ymir's Heart | 89 |
| Holy Forbidden | Valhalla | 09 |
| Whiteout | Lutie | 59 |
| Lycaeum | Illusion of Under Water | 100 |
| The Coop | Hugel / Peco farm | 93 |
| Space 54 | Juperos (low confidence) | 128 |
| Carlo Cart | Mjolnir / Einbroch mine line | 27 |
| Laborratory | Lighthalzen Bio Lab | 92 |
| Westwoods | Rock Ridge | 172 / 171 |
| Bat Country | Geffen Dungeon (Dracula) | 21 |
| Astral Stair | Odin Temple | 110 |
| Mazerella | Labyrinth Forest | 16 |
| Tiny Bridge | Amatsu | 77 / 76 |
| Devil Room | Satan Morroc's lair | 121 |

The BGM numbers come from the client's `mp3NameTable.txt` (map → track).

## Technical tracks (what each category needs)

| Track | Covers | Status |
|---|---|---|
| Character atlas + 8 dirs + scale hooks | all playable characters | **proven** (Swordman, build `8d`); generalize `reskin_char.py` per job/gender/NPC/monster |
| Enemy atlas by data (`reskin_enemy.py` + `ENEMY_DATA.scale`) | 303 families | **proven** for idle; still to add: death frames (RO die action), per-family scale, big bosses |
| JSON + I2 text (`patch_data.py`) | all names/descriptions | **proven**, names read from these YAMLs (547 terms, EN + PT-BR) |
| RGBA32 atlas pixels | character/enemy atlases | **proven** |
| ASTC swizzled texture write | stage tilesets, UI cards, logo, icons | **proven** (Mad Forest floor recolor, 2026-10-16) |
| Stage tilesets from RO floor textures (`필드바닥`, 1,080 textures) | 24 stages | **likely** technically; the art work (seamless 32 px tiles from perspective ground) is real effort per stage |
| Icons atlas `tps_lossless_icons` | weapon/passive/item icons | **likely**; RO item icons are in `texture/유저인터페이스/item` (not exported yet) |
| Skill effects | weapon projectiles/areas | **spike**: 311 `.str` effects need a renderer to frames; the classic skills (Bash, bolts, Soul Strike, Magnum Break, LoV, Spirit Spheres) are drawn by the client code, so they get hand-built effects from the client's loose `.tga`/`.bmp` textures |
| Music (FSB5 Vorbis in `bgm_*` bundles) | 46 tracks | **likely**: write FSB5 as PCM/ADPCM (simple; ~500 MB for all tracks, too big?) or encode Vorbis through the installed Unity Editor |
| SFX (187 clips in `resources.resource`, IMA ADPCM) | hits, pickups, level up, chest | **likely** (same FSB5 writer) |
| Fonts | | keep LanaPixel (already covers PT-BR); number/bitmap fonts retextured in place |
| Chest opening | 3 H.264 videos | **spike** (small): re-encode with the same frame count |

## Phases (each one a vertical slice, gated in Eden, then on the console)

1. **Pipeline from the YAMLs.** `patch_data.py`, `reskin_char.py` and `reskin_enemy.py` read the mapping
   files instead of tables in code. Add enemy death frames and per-family scale. First in-game ASTC write
   (the logo is the smallest one).
2. **Payon Forest complete (Mad Forest).**
   - Characters: Novice (default) + Mage, Acolyte, Archer (the Zeny tier), Swordman (Magnum Break Lv7).
   - Weapons: their weapons + evolutions + the passives that evolve them.
   - Enemies and bosses: every Mad Forest family.
   - Ground: tileset from Payon forest floors.
   - Pickups, title logo and icons, BGM 03/36, EN + PT-BR texts for all of it.
   - Gate: one full run on the console (performance, RT 2×).
3. **The other three main stages** (Glast Heim Castle, Einbroch, Clock Tower), with the characters and weapons
   they unlock, the remaining base weapons and passives, and the effects pipeline (`.str` renderer + hand-built
   classic skills).
4. **Cursed Abbey + secret/extra stages**, arcanas (tarot), relics, secrets, achievements, bestiary texts,
   Directer/merchant NPCs, music for every stage, SFX.
5. **EXTRA content** (Eudaimonia, Laborratory, Westwoods…, their characters and weapons).
6. **DLCs** as RO episodes (Moonspell, Foscari, Emergency Meeting, Operation Guns, Castlevania, Emerald
   Diorama, Ante Chamber), in the order Zero prefers.

Also open: the character-select card overflows with the larger sprites (fix in phase 2).

## Decisions for Zero (before phase 2)

1. ~~Core cast~~ decided: starts as the Novice; unlocks follow the VS path as RO job changes (`CAST.md`).
2. **Text languages.** Rewrite EN + PT-BR only and copy EN into the other 12 languages (estimated 9–11
   writer-days for ~45k words, ~60% by dictionary substitution)?
3. **Classic skill effects.** Hand-build Bash, the bolts, Soul Strike, Magnum Break… from client textures (most
   faithful, most work), or use the nearest `.str` effect as a placeholder first?
4. **Music size.** PCM (simple, ~500 MB more on the SD) or Vorbis via the Unity Editor (smaller, one more build
   step)?
5. **Low-confidence rows.** 119 enemy picks and about 30 character/weapon/item picks are marked `low`; the
   biggest ones are listed at the end of each YAML pass report (Runetracer → Holy Light, Gorgeous Moon →
   Judex, Gatti Amari → Vanilmirth, Giant Enemy Crab → King Dramoh, the Molisano set → Utan tribe…).
