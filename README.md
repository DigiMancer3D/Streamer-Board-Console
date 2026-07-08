# Streamer Board & Console

<p align="center">
  <strong>A low-resource local control hub for streamer overlays, OBS helper windows, profile actions, app adapters, and reusable pin boards.</strong>
</p>

<p align="center">
  <img alt="Platform" src="https://img.shields.io/badge/platform-Linux%20%7C%20Kubuntu%20tested-informational">
  <img alt="Python" src="https://img.shields.io/badge/python-3.12+-blue">
  <img alt="UI" src="https://img.shields.io/badge/UI-Tkinter-lightgrey">
  <img alt="OBS" src="https://img.shields.io/badge/OBS-friendly-purple">
  <img alt="Release" src="https://img.shields.io/badge/release-v0.4.5-green">
</p>

---

## What is this?

**Streamer Board & Console** is a local desktop command center for running and coordinating small streamer tools. It was built for a low-resource OBS workflow where separate apps can be launched, parked, closed, monitored, and combined into show profiles.

The project currently focuses on:

- **App adapters** for launching and controlling streamer helper apps.
- **Studio Profiles** for one-click show states such as Gaming, Clean Visuals, Talk / Podcast, or custom app mixes.
- **Pin Boards** for OBS-friendly image boards and screen elements.
- **Hotkey control files** so compatible apps can turn hotkeys on/off without global keyboard blocking.
- **Template-based integrations** so more apps can be added later.
- **Console Copier** for multiple isolated Streamer Board & Console instances.
- **Release Prep** for building clean public upload folders.

This is an initial public release. It is meant to be practical, hackable, and easy to extend.

---

## Supported / staged companion apps

Streamer Board & Console can run by itself, but it is designed to work best with companion apps from the same GitHub account.

| App | Purpose | Adapter status |
| --- | --- | --- |
| Soundcard | Microphone / audio visualizer for stream scenes | Native hotkey control supported |
| G502V | Mouse / G502 visualizer for OBS and input feedback | Native hotkey control supported |
| Bitninja Mocap Lite | OBS-focused VTuber mocap | Launch / close / profile template |
| Deck Card Widget | Low-resource deck-card OBS overlay controller | Launch / close / profile template |
| SWAR Script Writer/Reader | Script writer / reader for show planning | Launch / close / profile template |

You can use only the apps you want. Templates stay editable inside the **Apps** tab.

---

## Quick start on Kubuntu / Ubuntu

```bash
chmod +x install_kubuntu.sh launch_streamer_board_console.sh launch_streamer_board_console_rescue.sh tools/*.sh tools/*.py
./install_kubuntu.sh
./tools/sbc_selftest.sh
./launch_streamer_board_console.sh
```

The installer creates a local `.venv` inside this folder and installs the Python dependencies listed in `requirements.txt`.

---

## Install optional companion apps

The console package includes templates for the companion apps, but it does not require them. To clone the public companion repositories into one local folder, run:

```bash
chmod +x install_optional_streamer_apps.sh
./install_optional_streamer_apps.sh
```

By default this creates:

```text
~/SBC_Streamer_Apps/
├── Bitninja-Mocap-Lite/
├── Deck-Card-Widget/
├── G502V/
├── soundcard/
└── 3DChangesPerspectives/
```

After cloning, open **Apps → Adapter Templates** and point each template to the folder and launch script that exists on your machine.

---

## Main tabs

### Dashboard

Shows running app and pin-board status, process IDs, RAM, and CPU.

### Apps

Launch, close, restart, pause, resume, and write hotkey control files for active adapters. This tab also includes **Adapter Templates**, where you can create new app templates or update existing paths.

### Hotkeys

Shows adapter hotkey data and control-file status.

### Pin Boards

Launches reusable image boards for OBS. Boards are separate windows that can be captured by OBS.

### Studio Profiles

Creates one-click combinations across all active adapters. Each row can set:

- hotkeys on/off
- local/live mode placeholder
- action: Keep, Launch, Close, Restart, Pause, or Resume

The profile editor is dynamic. Newly enabled adapters appear with **Keep** as the default action.

### Backup / Migrate

Exports and imports user data. Also migrates settings from previous `Streamer_Board_Console_MVP_*` folders.

### Console Copier

Creates isolated `.sbconsole` console copies. Each copy can have its own:

- `user_data`
- profiles
- adapters
- adapter templates
- app controls

This is useful when one machine needs multiple show setups.

---

## Emoji sync

This release includes a shared emoji table:

```text
user_data/current.emoji
```

The optional app installer copies that file into companion app folders when possible. The goal is simple: keep a single unified emoji style across tools without forcing every app to share one runtime database.

---

## Adapter templates

Adapter templates live in:

```text
adapter_templates/
```

Enabled adapters live in:

```text
adapters/
```

A minimal adapter template looks like:

```json
{
  "app_id": "my_app",
  "display_name": "My App",
  "default_path": "~/My-App",
  "launch_mode": "shell",
  "entry_file": "launch_my_app.sh",
  "control_file": "user_data/app_controls/my_app.control.json",
  "supports": {
    "launch_close": true,
    "restart": true,
    "resource_monitor": true,
    "pause_park_suspend": true,
    "hotkeys_toggle": false,
    "hotkey_remap": false,
    "local_live_toggle": false,
    "theme_sync": false,
    "emoji_sync": false
  },
  "default_hotkeys": [],
  "notes": "Describe anything the user must know before enabling."
}
```

For a fuller integration guide, see:

```text
HOW2_INTEGRATE_ADAPTERS.md
```

---

## Useful commands

Run the console:

```bash
./launch_streamer_board_console.sh
```

Run the rescue launcher if the window appears off-screen:

```bash
./launch_streamer_board_console_rescue.sh
```

Run selftests:

```bash
./tools/sbc_selftest.sh
```

Check app adapters:

```bash
./tools/sbc_adapter_doctor.py
```

List console copies:

```bash
./tools/sbc_console_copier.py --list
```

Create a console copy:

```bash
./tools/sbc_console_copier.py --create "Second Show Console"
```

Build a clean release export:

```bash
./tools/sbc_release_prep.py --build
./tools/sbc_release_prep.py --inspect
```

---

## Release types

### Standard public release

Use this repo as the normal public release. It contains the console, templates, tools, docs, and clean default data.

### Full local bundle

A full bundle can include local copies of companion apps. This is useful for private testing or curated release zips. To build one from a local machine with all companion apps already present:

```bash
chmod +x build_full_streamer_bundle.sh
./build_full_streamer_bundle.sh
```

The full bundle script removes common private/runtime data such as `.git`, `.venv`, `node_modules`, caches, logs, and old runtime folders.

---

