# Tech notes: stages, audio, SFX, UI and fonts

Verified 2026-10-16 against `~/vs-decomp/romfs` (VS 1.15.113, Unity 6000.0.62f1) with UnityPy 1.25.4. Everything
here was read-only. Bundle names drop the `vs_local_assets_` prefix. Mapping decisions are in
`stages_music_ui_story.yaml`.

Risk levels:
- **proven** means the same path already works in game (see MODLOG).
- **likely** means the format is understood and offline round-trips passed, but nothing has been tested in game yet.
- **spike** means it needs research before it can be scheduled.

## Texture formats (applies to everything below)

- Most stage, UI and bundle textures are **ASTC 4x4** (`TextureFormat 48`, 1 byte/px, so a 512² texture is
  262144 B in the `.resS`). They carry a 92-byte `m_PlatformBlob` whose u32 at offset 8 is 4 (or 2 on small
  textures), which means 16 (or 4) GOBs per block. That makes them **Switch block-linear swizzled**.
- `character_antonio`, `tps_lossless_icons`, `enemies*` and `damNum` are **RGBA32 with no blob**, so they're
  linear. That's the proven path through `unitypatch.replace_texture`.
- `title` 332x133 is RGBA32 but swizzled (it has a blob). `introBG` 400x300 is **DXT1Crunched** (fmt 28).
  The TMP SDF atlases are Alpha8.
- I tested an offline round-trip on `forest/ForestTexturePacked`: decode, then
  `UnityPy.export.Texture2DConverter.image_to_texture2d(img, ASTC_RGB_4x4, platform=38 (Switch), blob)`,
  then decode again. It came back as exactly 262144 B with a mean error of about 0.1/255 (max 27, which is
  normal for ASTC). UnityPy (`astc_encoder` + `TextureSwizzler.swizzle`) can therefore write swizzled ASTC
  in place at the same size.
- `unitypatch.replace_texture` now writes ASTC/swizzled textures through `image_to_texture2d` (platform 38 +
  the original blob). **Proven in game 2026-10-16**: recolored `forest/ForestTexturePacked` rendered clean in
  Mad Forest (readback error mean 0.12, max 32).

## Stages / tilesets

Every tiled stage is one Addressables bundle holding a SuperTiled2Unity-imported prefab:
- `Grid`
- 9–11 Unity `Tilemap` + `TilemapRenderer` layers: Floor, FloorOverlay, Decals, Overlay1, Shadows,
  ShadowDecals, Walls, FakeWalls, PlayerWall, Obstacle, Spawning
- `SuperMap`, `SuperTileLayer` and `SuperTile` MonoBehaviours
- 2 `PhaserTilemap` components plus `PhaserTilemapBoundingBoxesAsset` (for example `Forest.tmx_Walls` and
  `Forest.tmx_PlayerWall`), which hold the collision boxes
- one tileset `Texture2D` with one 32x32 `Sprite` per used tile. Sprites are named
  `st2u_x{X}y{Y}-w32h32`, with a 1 px margin and 2 px spacing.

STAGE_DATA's `tileset.setPath/mapPath` (`assets/tilesets/Forest.json`) is a leftover from the Phaser build.
The bundle prefab is the real map.

| bundle | map (tiles @32px) | tileset texture | notes |
|---|---|---|---|
| forest | 64x64 | ForestTexturePacked 512² ASTC | Floor 4096 tiles / 24 distinct |
| library | 64x64 | LibraryTexturePacked 512² | |
| plant2 | 64x64 | PlantTexturePacked 512² | Floor uses only 3 tiles |
| tower | 64x64 | TowerTexturePacked 512² | + background4 2048x1024 parallax (9 sprites) |
| chapel | 64x64 | ChapelTexturePacked 512² | + backgroundx 2048² (56 sprites) |
| water | 64x64 | WaterTexturePacked 512² | + backgroundw 1024², bg_water 1024² |
| machine | 64x64 | MachineTexturePacked 512² | + background6 2048² |
| rash | 64x64 | RashTexturePacked 512² | |
| coop | 32x32 | CoopTexturePacked 960² | 900 sprites |
| space / spacebackup | 128x128 | SpaceTexturePacked 960x480 | + backgroundspace 2048² |
| carlocart, laborratory | 128x76 | LaborratoryTexturePacked 960² (2 copies) | |
| westwoods | 160x66 | Westwoods_Tileset2 960² | + background_westwoods 128² |
| astralstair | 320x320 | AstralStairTexturePacked 512² | + background_astral 512x1024 |
| mazerella | 272x272 | Mazerella_Tileset2 640x448 | Floor 73936 tiles / 8 distinct |
| towerbridge | 64x64 | TowerTexturePacked 512² (copy) | |
| devilroom | 32x512 | DevilRoomTexturePacked 960² | + backgrounddevil 512x1024 |
| whiteout | 128x128 | MoonspellTexturePacked 2048x1024 | |
| lycaeum | 1280x2111 | Lycaeum 1024² | huge map |
| stage5wip (Holy Forbidden) | 256x32 | ChapelTexturePacked (copy) | |
| forest_batcountry, 02greenacres, 03riskywoods, 04orchard, 05garden | 64x64 / 40x40 | ForestTexturePacked (one copy **per bundle**) | |
| planarbazaar | – | MachineTexturePacked (copy) | |

Non-tiled stages (Il Molise, Bone Zone, Green Acres fallback) use `BGTextureName`, a single tiled 1024² ASTC
texture: `bg_molise`, `bg_bonezone`/`bg_boneN`, `bg_forest`, `bg_green`, `bg_ram`, `bg_white` (128²) and
`bg_null` (resources.assets).

**Tileset verdict: replacing the tileset atlas pixels alone retextures the stage.** I decoded
ForestTexturePacked. Ground tiles, trees, tombstones, flowers, water and the brick path are all tiles in that
one atlas, and the Walls/Obstacle/Decals layers draw from it too. So the trees change along with the floor.
Collision lives in PhaserTilemap bounding boxes and the tile layers, not in the pixels, so gameplay is
untouched.

Constraints:
1. Keep each tile in its 32x32 slot. RO ground textures must be cut into seamless 32px tiles that fit the
   existing tile placement.
2. Replace **every copy**. The same texture name lives in several bundles: Forest ×6, Tower ×2, Plant/Lab ×2,
   Chapel ×2, Machine ×2.
3. Breakable props (braziers, candles, carts) are not in the tileset. They're in `tps_props` 512x1024 ASTC in
   resources.assets.
4. Day/night and inverse modes are tints (`inverse.tint`), so no extra art is needed.

Risk: **likely** (ASTC swizzle write, then in-game check).

Extra resolution (64px tiles at 2× density to match the hi-res RT hook) would need new sprite rects/PPU in
every SuperTile sprite. Tilemaps may honour PPU, unlike the character path. **spike**.

## Music

- Bundles `bgm_*` (base: `bgm_elrond_*`, `bgm_vica_01..12`, `bgm_lycaeum-*`, `bgm_will_beginning`,
  `bgm_theend*`, `vs_music_v04-01`) each hold one `AudioClip`. The audio itself is in the bundle's inner
  `CAB-*.resource`.
- AudioClip settings: `m_CompressionFormat = 1` (Vorbis), 44100 Hz stereo (squirrel: 48 kHz; BGM_Glitch:
  22 kHz). `m_LoadType` is 1 (CompressedInMemory), or 0 for the newer intro/loop clips. Lengths run 35–284 s,
  at 0.5–5.8 MB per track.
- **FSB5 v1, mode 15 (VORBIS), 1 sample, one chunk of type 11 (Vorbis setup CRC + seek table).** This was
  verified in the header bytes of `bgm_elrond_forest`, `bgm_elrond_devil_loop` and `bgm_elrond_squirrel_loop`.
- **There is no LOOP chunk in the FSB.** VS loops whole clips, and does intro+loop with separate clips (pairs
  for SpaceDude, Carts, Labor, TheCoop, Westwoods, Devil, Lycaeum phases).
- `MUSIC_DATA.hyperMod/forsakenMod` (rate/detune) is applied at runtime, so it carries over to RO tracks
  for free.
- Key→clip table: MonoBehaviour **resources.assets path_id 12687** in `data.unity3d`. Example: BGM_Forest →
  bgm_will_beginning, BGM_Forest_B → bgm_vica_01, BGM_GreenAcres → bgm_elrond_forest, BGM_Labor → lab_intro,
  lab, boss0..5. Replacing a clip's audio in its own bundle is enough; the table never has to change.
- Decoding works: UnityPy + `fmod_toolkit` (bundled `libfmod.so`) export these clips to WAV. `pyfmodex` is
  installed too.

**Replacing a clip with an RO mp3.** RO BGM is MP3, 22050 Hz stereo, ~80 kbps, loops as a whole file.
1. Use ffmpeg to decode the mp3 to WAV, trim the encoder delay, and resample to 44.1 kHz (or keep 22.05 kHz
   and set `m_Frequency`).
2. Build an FSB5 using one of these options:
   - **(a) PCM16 FSB5 (mode 2), recommended first.** The header is trivial to write in Python (~40 lines,
     no codec). Cost: 22.05 kHz stereo is about 88 KB/s, roughly 13 MB per 150 s track and about 500 MB for
     all 46. RAM goes up because load type 1 keeps the whole clip.
   - **(b) IMA ADPCM FSB5 (mode 7, 4:1).** The base game already uses this for SFX. You can confirm the
     output by decoding it back through libfmod before shipping.
   - **(c) Vorbis.** FMOD strips the Vorbis setup header and identifies it by CRC, so a plain `oggenc`
     stream will not play. Get real FSB5 Vorbis from FMOD's own encoder: either Unity Editor 6000.6.2f1
     (installed here; build a Standalone AssetBundle with a Vorbis AudioClip and lift its `.resource` bytes)
     or FMOD `fsbankcl`. FSB5 v1 should read across Unity versions, but test it.
3. Swap the bundle's inner `.resource`: `unitypatch.Bundle.raw[name] = fsb`, then `save()` (inner files are
   plain byte arrays).
4. Rewrite the AudioClip object with `typetree_bytes` + `replace_object`, updating `m_Resource.m_Size`,
   `m_Length`, `m_Frequency`, `m_Channels`, `m_BitsPerSample` and `m_CompressionFormat` (0 = PCM, 2 = ADPCM).

Risk:
- PCM/ADPCM route: **likely**. The format is fully understood and libfmod is available to check the output.
- Vorbis via the Unity Editor: **likely**, but it adds a build step.
- Loop clicks: RO tracks are whole-file loops. Crossfade or zero-cross trim the end.

## SFX

- **187 AudioClips in `data.unity3d`/resources.assets**, with data in the **loose file
  `romfs/Data/resources.resource`** (16.5 MB).
  - Formats: 181 are IMA ADPCM (fmt 2, FSB5 mode 7, mono or stereo, 44.1/48 kHz), 3 are PCM, 3 are Vorbis.
    All use load type 1, except the PCM and Vorbis ones (load type 0).
  - Names: `sfx_gem`, `sfx_levelup`, `sfx_enemyHit`, `sfx_coin_double4`, `sfx_treasure_found`,
    `sfx_gameOver`, `sfx_potBreak`, `sfx_titleIntro`, `glass01..25`, `step01..04` and so on (full list in the
    yaml).
- **Separate bundles:**
  - `sfx_treasure_1/2/3` (+`b`): the chest jingles, 9.6–19.9 s, ADPCM
  - `sfx_wind`: Whiteout ambience, 72 s
  - `sfx_geiger1..4`
  - `sfx_darkassojingle`
  - `darkasso_open` (Vorbis)
- **Replacement:**
  1. Append a new FSB5 to `resources.resource` (a loose file, so layeredFS takes it as is).
  2. Repoint that AudioClip's `m_Resource.m_Offset/m_Size` and update its fields with `replace_object` on
     resources.assets. That's the same mechanism as the I2/JSON patches.
  3. Bundled SFX use the same inner-`.resource` swap as music.
- **RO side:** `data/wav/` holds 1962 `.wav` plus the subfolder `effect/`. Key files are `levelup.wav`,
  `_enemy_hit_normal1..4.wav`, `se_get_coin.wav`, `roulette.wav`, `complete.wav`, `버튼소리.wav` (button),
  `취소.wav` (cancel), `se_prtchbell_*` and `_frozen_explosion.wav`.
- Risk: **likely**. Same FSB5 writer as music, and the clips are short, so PCM16 is fine size-wise.

## UI and branding (locations verified)

`data.unity3d` contains:
- **sharedassets0:** `UI` 1024² ASTC, linear, 536 sprites (stage icons, character badges, finger badges, header).
- **sharedassets1:**
  - title and logo pieces: `title` 332x133 (the "VAMPIRE SURVIVORS" logo, RGBA32 swizzled), `titleSurvivaton`,
    `titleDivider`
  - loading and secrets screens: `NowLoading_VS`, `SECRETS`, `secretsPortrait`, `illustrations`, `introBG`
    (DXT1Crunched)
- **sharedassets3:** `stageComplete`, `gameOver`, `DamageNumbers Atlas` 24x27, legacy fonts `titleFont-*`.
- **resources.assets:**
  - icons and props: `tps_lossless_icons` 512² RGBA32 linear (671 sprites: weapon/item/passive icons;
    WEAPON_DATA `texture: tps_lossless_icons`), `tps_props` (227)
  - menu and logo: `UI_Menu` 1024² (551 sprites: stage cards, menu frames, character mini-portraits),
    `logoAnimation` 1024x2048 (105 sprites; it decodes as white, so it's probably a mask)
  - other atlases: `UI_StageIcons` (copy), `shop`, `goldBG1/2`, `randomazzo`, `vfx` (1059 sprites)
  - the I2Languages table (path_id 9616)
- **globalgamemanagers:** splash `Logo_bordered_-_1080X1080` plus two RGB24 boot images.

Bundles:
- **`ui_stageicons`:** UI_StageIcons 1024², 32 stage cards.
- **`ui_bestiary`:** UI_Bestiary 1024x2048, 16 `background_*.png`.
- **Menu splashes:** `imeldamenusplash`, `garlicparadisemenusplash`, `shemoonmenusplash`, `emptysplash`.
  Each is a prefab with `MenuBackgroundController`, Image, RawImage and a `VideoPlayer` →
  `moonspell-menu-splash` RenderTexture, plus character art (Imeldat 320x340, Poet, Shemoont) and introBG.
- **`adventuresui`:** 44 `ADV_*` sprites.
- **Album covers:** `vs_ingame_album_vs_sidea/b/c` (256², ASTC).
- **`titlemask` / `mainmask` / `infomask`:** only `Mask` + `Image` prefabs, with no texture inside.

Chest opening is **video**: `chestnobg`, `chestnobg2`, `chestnobg3` VideoClips.
- The `.resource` is MP4 (`ftypmp42`), H.264 Constrained Baseline, yuv420p, stored at 634x332 although the
  clip declares 1268x664.
- 60 fps; 655, 1030 and 1136 frames respectively; no audio track.
- Replacement: an ffmpeg encode with the same profile and frame count, an inner-`.resource` swap, and an
  updated `m_ExternalResources.m_Size`. **likely**.

Risk:
- Pixel replacement inside existing sprite rects: **likely** for ASTC/swizzled textures, **proven** for
  RGBA32 linear ones (icons).
- Crunched `introBG`: rewrite the Texture2D as RGBA32 inline with `replace_object`. **spike** (small).

## Fonts

- **TextMeshPro SDF:**
  - `LanaPixel SDF` (bundle `lanapixelsdf` + `lanapixelsdfextendedascii` + CJK range bundles
    `lanapixelsdf4e00-5fff`…`9000-9fff`; atlases 512² Alpha8, also mirrored in resources.assets)
  - `Courier_HintedSmooth SDF8` (4 atlases)
  - `Arial Unicode MS Font SDF` (54 atlases, CJK fallback)
  - `LiberationSans SDF`
  - `DamageNumbers` (TMP asset, dmg3 Atlas 32² Alpha8 + 24x27 RGBA32)
- **Legacy bitmap `Font`:** `titleFont-export`/`-white` (144x148 ASTC), `damNum-export` 24x27,
  `GoldenFinger_Numbers-export` 72x73, `RuneFont-export` 110x108, `Skullboy-export2x` 281², `LanaPixel`,
  `Courier_HintedSmooth`, `Balatro_font` (dynamic, so the texture is 0x0).
- **Verdict:**
  - Keep LanaPixel/Courier/Arial. PT-BR accents are already covered by the ExtendedAscii atlas, and the
    pixel style suits RO. **proven** (no change).
  - Bitmap and number fonts can be retextured inside their existing glyph rects. **likely**.
  - A new RO-style TMP font means regenerating the SDF atlas plus the glyph/character tables inside a
    `TMP_FontAsset` MonoBehaviour that has no typetree under IL2CPP. **spike, not recommended.**

## Text

- I2Languages has 6580 terms, about 45k EN words, 14 languages. It round-trips byte-exact with
  `unitypatch.I2Terms` (**proven**).
- PT-BR coverage is already high: lang 902/906, enemies 802/802, weapons 1218/1346.
- Base-game share by IDs in the local `*_DATA.json`:
  - weapon 403 terms / 1553 words
  - character 222 / 651
  - enemies 366 / 8182
  - item 220 / 929
  - stage 69 / 797
  - achievement 211 / 1254
  - The rest is DLC.
- Credits are `lang/credits_*` terms. Album titles are in the `ALBUM_DATA` TextAsset. Note that the local
  `ALBUM_DATA.json` dump fails `json.load` at line 708 (the game's JSON is lenient), so `patch_data.py` must
  not reformat it.

## Biggest risks

1. **Audio codec:** no Vorbis FSB5 encoder outside FMOD/Unity. Plan on PCM/ADPCM FSB first and verify with
   libfmod, but the size/RAM impact on Switch needs checking.
2. **Swizzled ASTC write path** is untested in game, and it gates every stage/UI texture.
3. **Art fit:** RO ground textures are perspective 3D terrain textures, not top-down 32px tiles. Making them
   seamless and slicing them is real art work per stage. The 32-px tile grid also caps detail unless
   tile PPU is researched.
4. **Shared texture copies across bundles** (and resources.assets) are easy to miss, leaving one stage with
   VS art.
5. **Chest videos** need re-rendering from RO sprites, with frame counts kept in sync with the treasure jingles.
