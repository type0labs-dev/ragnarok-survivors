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
- The **Ragnarok Online client**, from the official Korean client (kRO) download:
  https://ro.gnjoy.com/pds/down/ (free GNJOY account needed to start the download). You need its `data.grf`
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

## Optional: standalone NSP

Instead of LayeredFS, you can build your own NSP. It installs as a separate game called "Ragnarok Survivors" with the
Ragnarok Online icon (title ID `0100525356000000`), next to the original Vampire Survivors. Updating Vampire Survivors
does not break it.

You need, from your own console and your own copy of the game:
- the **exefs** of the 1.15.113 update, the **romfs** (the same one used above) and the **control** romfs
  (`control.nacp` and `icon_*.dat`), for example dumped with nxdumptool or extracted with hactool;
- optionally the **logo** section of the program NCA (`NintendoLogo.png`, `StartupMovie.gif`);
- your console's **prod.keys** (Lockpick_RCM);
- **hacpack** v1.36, built from source.

First run `tools/build.py --sd <output folder>` as above, then:

```
python3 tools/make_nsp.py --exefs <exefs> --romfs <romfs> --control <control> --mod <output folder> \
    --ro <RO client folder> --keys <prod.keys> --hacpack <hacpack> [--logo <logo>]
```

The NSP lands in `work/nsp/`. Install it with Tinfoil, DBI or sphaira (signature patches required). Its save is
separate from Vampire Survivors; copy it over with JKSV if you want your progress.

> **Disclaimer:** the NSP contains the whole game, your copy of Vampire Survivors plus Ragnarok Online art. It is for
> your own consoles only. Do not share or upload it. This repository will never host NSPs, game files or links to
> them.

## Legal

Vampire Survivors © poncle. Ragnarok Online © Gravity Co., Ltd. This is a non-commercial fan project, not affiliated
with either company. You must own both games.

The code in `tools/` and `mapping/` is ours. The hooks in `exl/` are built on exlaunch (GPL-2.0).
