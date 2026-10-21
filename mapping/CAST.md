# Cast: VS unlock path → RO class change

Zero (2026-10-16): the cast starts as the Novice, and the first classes unlock the same way VS unlocks

> **Revision (Zero, 2026-10-16 night):** each character's RO class must fit their starting weapon (whip → Dancer, staff →
> Mage, knife → Thief…). Antonio is now the Dancer and the Novice left the starting cast. `characters_weapons.yaml` is
> the source of truth; the table below is the original rationale.

characters. Each VS character keeps its perks (stat bonuses and per-level growth, numbers unchanged) and its
starting weapon. The RO side gives the class whose job change, job bonus and signature skill play the same role.
Unlocking a VS character = a job change in RO.

Source of the VS side: `CHARACTER_DATA` (price, stats, level perks, startingWeapon) and `ACHIEVEMENT_DATA`
(`characterToUnlock` + condition). Secret (code-unlocked) and EXTRA characters stay as in
`characters_weapons.yaml` (NPCs and monsters, plus 3rd/expanded jobs).

## Tier 0: default
| VS | Perk (kept) | Starting weapon → RO skill | RO class | Unlock (VS → RO text) |
|---|---|---|---|---|
| Antonio | +10% Might every 10 levels (max +50%), 1 Armor | Whip → **Basic Attack** (knife slash); evolution Bloody Tear → **Bash** (the Novice's slash "job-changes" into the Swordman's) | **Novice** (Aprendiz) | default |

## Tier 1: bought with gold (VS price kept) = job change paid with Zeny
| VS | Perk | Weapon → skill | RO class | Unlock |
|---|---|---|---|---|
| Imelda | +10% XP every 5 levels (max +30%) | Magic Wand → Soul Strike | **Mage** (Mago) | 10 gold → 10 Zeny |
| Pasqualina | +10% projectile speed every 5 levels | Runetracer → Holy Light | **Acolyte** (Noviço) | 100 → 100 Zeny |
| Gennaro | +1 projectile (all weapons) | Knife → Double Strafe ("double" = +1 projectile) | **Archer** (Arqueiro) | 500 → 500 Zeny |

## Tier 2: master a weapon or a feat = master the skill that opens the class
| VS | Perk | Weapon → skill | RO class | Unlock (VS → RO) |
|---|---|---|---|---|
| Poe Ratcho | +25% pickup range, −30 Max HP | Garlic → Magnum Break | **Swordman** (Espadachim) | Garlic Lv7 → Magnum Break Lv7 |
| Lama | +Might, Move Speed, Curse every 10 levels | Axe → Mammonite (Merchants fight with axes) | **Merchant** (Mercador) | survive 20 min with +10% Curse |
| Arca | −5% cooldown every 10 levels | Fire Wand → Fire Ball | **Wizard** (Bruxo) | Fire Wand Lv4 → Fire Ball Lv4 |
| Porta | big Area, fading Cooldown bonus | Lightning Ring → Thunderstorm (evo Lord of Vermilion) | **High Wizard** (Arquimago) | Lightning Ring Lv4 → Thunderstorm Lv4 |
| Clerici | +Recovery, huge starting Area | Santa Water → Sanctuary | **Priest** (Sacerdote) | heal 1000 HP total |
| Dommario | +40% Duration and Speed, −40% Move Speed | King Bible → Spirit Spheres (orbit) | **Monk** (Monge) | earn 5000 Zeny in one run |
| Krochi | starts with 1 Revival, +30% Move Speed | Cross → Shield Boomerang | **Crusader** (Templário) | defeat 100,000 enemies |
| Christine | starts 1 level ahead | Pentagram → Magnus Exorcismus | **High Priest** (Sumo Sacerdote) | Pentagram Lv7 → Magnus Exorcismus Lv7 |

## Tier 3: coffins = the job-change NPC hidden in the stage's region
| VS | Perk | Weapon → skill | RO class | Coffin stage → RO region |
|---|---|---|---|---|
| Pugnala | +1% Might per level | Phiera/Eight → Triple Action | **Gunslinger** (Justiceiro) | Mad Forest → Payon Forest |
| Giovanna | +1% projectile speed per level | Gatti Amari → Homunculus (Vanilmirth) | **Alchemist** (Alquimista) | Inlaid Library → Glast Heim |
| Poppea | +1% Duration per level | Song of Mana → Severe Rainstorm | **Dancer** (Odalisca) | Dairy Plant → Einbroch |
| Concetta | +1% Area per level | Shadow Pinion → Venom Dust (poison zones along the path) | **Thief** (Gatuno) | Gallo Tower → Clock Tower |
| Zi'Assunta | +0.5% Might/Speed/Duration/Area per level | Vento Sacro → Sonic Blow | **Assassin Cross** (Algoz) | Cappella Magna → Cursed Abbey |

## Tier 4: kill 3000 of X = play as X (monster/NPC, like VS)
| VS | Weapon → skill | RO | Unlock |
|---|---|---|---|
| Mortaccio | Bone → thrown bone | **Skeleton** (monster) | 3000 Skeletons |
| Cavallo | Cherry Bomb → bomb | **Peco Peco** (monster) | 3000 Lion Heads (→ Gryphon) |
| Ramba | Carréllo → Cart Revolution | **Blacksmith** (Ferreiro) | 3000 Milk Elementals (→ Marin) |
| O'Sole Meeo | Celestial Dusting → Falling Star | **Star Emperor** | 3000 Dragon Shrimps |
| Ambrojoe | La Robba → Potion Pitcher | **Alchemist guildmaster** (NPC) | 6000 Stage Killers |

## Tier 5: evolution unlocks
| VS | Weapon → skill | RO | Unlock |
|---|---|---|---|
| Gallo Valletto | Clock Lancet → Frost Diver | Rooster (NPC) | obtain Infinite Corridor |
| Divano Thelma | Laurel → Kyrie Eleison | Sister (NPC) | obtain Crimson Shroud |

## Notes
- Thief has no natural early VS weapon (the Knife is the Archer's Double Strafe), so it lands in the coffin
  tier, as Concetta (shadow theme). Alternative: Gennaro → Thief (Knife → Throw Venom Knife, "+1 projectile" →
  Double Attack), and the Archer moves to a later slot.
- Second classes before every first class is unlocked are fine: VS does the same (Arca/Porta/Clerici arrive
  before some starters are bought).
- The unlock texts (achievementLang) get rewritten to the RO side of each row.
