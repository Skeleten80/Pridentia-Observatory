# User Guide — Prudentia Observatory

## Overview

This guide walks you through a complete night imaging session with Prudentia
Observatory, from planning targets to collecting a finished exposure sequence.

---

## 1. Application Layout

The main window has eight tabs on the left side:

| Tab | Purpose |
|---|---|
| **Sky Map** | Real-time azimuthal sky projection + Tonight's Best Targets |
| **Object Search** | Search the local catalogue, view target details |
| **Telescope** | Mount connection, slew, tracking, emergency stop |
| **Camera** | Camera connection, single-frame capture |
| **Sequence** | Build and run a multi-frame exposure sequence |
| **Plate Solver** | Trigger a plate solve, display results, sync mount |
| **Session Log** | Running log of all session events |
| **Settings** | Observer location, device backends, UI options |

The top toolbar always shows:
- **UTC clock**
- **Night Vision Mode** toggle (red/dark switch)
- **Mount / Camera / Solver** status LEDs
- **⬛ STOP** emergency stop button

---

## 2. First-Time Setup

### 2.1 Set Your Observer Location

1. Go to **Settings → Observer Location**.
2. Choose a **Preset Site** from the dropdown, or enter custom coordinates.
3. Enter your **Time Zone** (e.g., `America/New_York`, `Europe/London`).
4. Click **Save Settings**.

Your location is used for all Alt/Az calculations, rise/set times, and the
Tonight's Best Targets list.

### 2.2 Select Device Backends

In **Settings**:

- **Mount Backend**: `simulator` (default), `ascom_alpaca`, or `indi`.
- **Camera Backend**: `simulator` (default), `gphoto2`, `indi`, or `folder_watch`.
- **Solver Backend**: `simulator` (default), `astrometry_local`, or `astrometry_remote`.

See [HARDWARE_SETUP.md](HARDWARE_SETUP.md) for hardware-specific configuration.

---

## 3. Planning Targets

### 3.1 Sky Map

The **Sky Map** tab shows an azimuthal equidistant projection of the sky
from your observer location.

- **Yellow crosshair**: current telescope position.
- **Green crosshair**: selected target.
- **Coloured dots**: catalogue objects (colour by type; see legend in sky map).
- **Tonight's Best Targets**: sorted by imaging score in the right panel.

Double-click a target in the Best Targets list to select it.

### 3.2 Object Search

1. Go to **Object Search**.
2. Type a name, catalogue ID, or partial match (e.g., `M42`, `Orion`, `NGC 224`).
3. Use type checkboxes and magnitude filter to narrow results.
4. Click an object to see its full details: RA/Dec, Alt/Az, airmass, moon
   separation, transit time, and imaging recommendations.
5. Click **Slew to This Target** to pre-fill the telescope and sequence panels.

---

## 4. Running a Session

### 4.1 Connect the Mount

1. Go to **Telescope** tab.
2. Click **Connect Mount**.
3. The status LED turns green when connected.
4. Click **Unpark** if the mount started parked.

### 4.2 Slew to Target

After selecting a target via Object Search or Sky Map:
- The **Telescope** tab RA/Dec fields are auto-filled.
- Click **Slew to Target**.
- Watch the Sky Map: the yellow crosshair moves to the target position.
- The mount status shows `Slewing` then `Tracking`.

### 4.3 Connect the Camera

1. Go to **Camera** tab.
2. Click **Connect Camera**.
3. Set **Exposure** (seconds) and **ISO**.

### 4.4 Capture a Test Frame

1. In **Camera** tab, click **Capture Frame**.
2. The progress bar shows exposure progress.
3. When complete, the image path appears in "Last Image".

### 4.5 Plate Solve and Centre

1. The last captured image is automatically sent to **Plate Solver**.
2. Go to **Plate Solver** tab.
3. The hint RA/Dec is pre-filled from your target.
4. Click **Plate Solve**.
5. After solving, you'll see the solved RA/Dec, pointing error, and rotation.
6. Click **Sync Mount to Solve** to correct mount pointing.
7. Re-slew to the target if needed to centre the field.

### 4.6 Start an Imaging Sequence

1. Go to **Sequence** tab.
2. The target name is pre-filled from your selection.
3. Set:
   - **Number of Lights** (e.g., 20)
   - **Exposure** (e.g., 180 s)
   - **ISO** (e.g., 800)
   - **Delay Between Frames** (e.g., 2 s)
4. Click **▶ Start Sequence**.
5. Use **⏸ Pause** to pause and **⏹ Abort** to stop early.
6. Each completed frame is logged in the session log.

### 4.7 Review the Session Log

The **Session Log** tab shows a time-stamped record of all events:
- Mount connections and slews
- Camera captures
- Plate solve results
- Sequence start/complete/abort

Logs are saved to:
- `~/PrudentiaObservatory/logs/session_YYYYMMDDTHHMMSSZ.log`
- `~/PrudentiaObservatory/logs/session_YYYYMMDDTHHMMSSZ_events.json`

---

## 5. Night Vision Mode

Click **🔴 Night Vision** in the toolbar to switch the entire UI to red/dark
colours.  This preserves your eyes' dark adaptation during a session.

---

## 6. Emergency Stop

The **⬛ STOP** button in the toolbar immediately halts all mount motion.
It is always accessible regardless of which tab is active.

Use it immediately if:
- The telescope is about to collide with the pier, tripod, or cables.
- An unexpected slew is commanded.
- The mount is not responding as expected.

---

## 7. Image Files

Images are saved to:
- **Default**: `~/PrudentiaObservatory/images/`
- **Custom**: Configure in Settings → Image Save Directory

The simulator camera saves FITS files with a minimal header containing:
exposure time, ISO, target name, and instrument.

Real camera backends save in whatever format the camera produces (RAW, JPEG, FITS).

---

## 8. Tips

- **Airmass < 2.0** is ideal for most targets (altitude > 30°).
- **Moon separation > 30°** greatly reduces sky glow contamination.
- Check the **Imaging Score** (0–10) on the Object Search detail panel.
- For planetary imaging, use short exposures (1–30 ms) and stack many frames.
- For nebulae, try narrowband filters (Hα, OIII, SII) with longer subs.
