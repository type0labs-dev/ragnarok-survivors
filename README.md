# Ragnarok Survivors

A Ragnarok Online reskin of Vampire Survivors for the Nintendo Switch (Atmosphère LayeredFS).

Characters, monsters, stages, items, icons, effects, music and sounds are replaced with Ragnarok Online art.
Gameplay numbers stay the same as Vampire Survivors.

**This release contains no game files.** It has no Vampire Survivors assets and no Ragnarok Online assets. You build
the mod on your own PC, from your own copy of each game. The release ships only:
- the builder (Python);
- the mapping tables;
- the compiled code hooks (`exefs/`).

## What you need

- A Switch running Atmosphère, with **Vampire Survivors 1.15.113**. The builder checks the version and refuses any
  other version, because the hooks only fit 1.15.113. DLCs are not covered.
- Your game's **romfs** dumped from your own copy, for example with nxdumptool (RomFS → "Data" folder).
- The **Ragnarok Online client**, from the official Korean client (kRO) download. You need its `data.grf`
  (GRF 0x200) and its `BGM/` folder.
  - Other clients may lack some files.
  - The first build extracts `data.grf` once, into `work/ro` (about 4 GB).
- **Python 3.12+**, then `pip install -r requirements.txt`.
- Optional, for music and sounds: **Unity Editor 6000.6.2f1** (free; set `UNITY_EDITOR` to its executable) and
  **ffmpeg** in PATH.
  - Without them the mod keeps Vampire Survivors' audio.

## Build

```
python3 tools/build.py --romfs <dumped romfs> --ro <RO client folder> --sd <output folder>
```

Copy `<output folder>/atmosphere` to the root of the SD card. Back up your save first (JKSV).

To uninstall, delete `atmosphere/contents/010089A0197E4000`.

## Legal

Vampire Survivors © poncle. Ragnarok Online © Gravity Co., Ltd. This is a non-commercial fan project, not affiliated
with either company. You must own both games.

The code in `tools/` and `mapping/` is ours. The hooks in `exl/` are built on exlaunch (GPL-2.0).
