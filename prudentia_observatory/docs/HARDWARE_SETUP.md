# Hardware Setup Guide — Prudentia Observatory

## ⚠ Critical Safety Warning

**Real telescope movement can cause serious damage to equipment, accessories, and
people.**

Before connecting real hardware:

1. Remove all lens caps and covers.
2. Ensure the optical tube assembly (OTA) can swing freely without hitting the tripod,
   cables, pier, or observatory walls.
3. Never leave the telescope unattended during a slew.
4. Keep all cables slack and out of the slew path.
5. **NEVER point at or near the Sun without a certified solar filter (Baader, Thousand Oaks,
   Seymour Solar, etc.).**  Permanent eye damage and camera sensor destruction can occur
   in fractions of a second.

---

## Telescope Mount

### ASCOM Alpaca (Recommended — Cross-platform)

ASCOM Alpaca is a REST/JSON protocol that works on macOS, Windows, and Linux.

**Windows setup:**
1. Install the [ASCOM Platform](https://ascom-standards.org/Downloads/Index.htm) (v6.6+).
2. Install the driver for your mount (e.g., EQMOD, TheSkyX, AstroPhysics, iOptron).
3. Install [ASCOM Remote](https://github.com/ASCOMInitiative/ASCOMRemote/releases) to
   expose the driver via HTTP.
4. In Prudentia Observatory Settings:
   - Set Mount Backend → `ascom_alpaca`
   - Set Alpaca Host → `localhost`
   - Set Alpaca Port → `11111` (or your configured port)
   - Set Alpaca Device # → `0` (or your device number)

**macOS / Linux setup:**
1. Use [INDI](https://indilib.org/) with the INDI Alpaca bridge, or use a Windows
   machine on the local network to host the Alpaca server.
2. Set Alpaca Host to the IP address of the Windows machine.

**Compatible mounts:** Any mount with an ASCOM driver.
Common ones: Sky-Watcher EQ6-R, iOptron CEM, AstroPhysics, Losmandy,
Celestron CGX, Meade LX200.

---

### INDI (Linux / macOS)

INDI (Instrument-Neutral Distributed Interface) is an open-source observatory
control protocol.

**Setup:**
```bash
# Ubuntu/Debian
sudo apt install indi-full

# macOS (Homebrew tap)
brew tap indilib/indi
brew install indi

# Start the INDI server for your mount
indiserver -v indi_eqmod_telescope
```

In Prudentia Observatory Settings:
- Set Mount Backend → `indi`
- Set INDI Host → `localhost`
- Set INDI Port → `7624`
- Set INDI Driver → driver name (e.g., `EQMod Mount`, `Celestron GPS`, etc.)

---

## Camera

### gPhoto2 (DSLR via USB)

gPhoto2 supports Canon, Nikon, Sony, Pentax, and 2,000+ other cameras.

**macOS:**
```bash
brew install libgphoto2 gphoto2
pip install gphoto2
```

**Ubuntu/Debian:**
```bash
sudo apt install gphoto2 libgphoto2-dev
pip install gphoto2
```

**Check your camera is detected:**
```bash
gphoto2 --auto-detect
```

In Settings → Camera Backend → `gphoto2`.

**Supported cameras:**
[http://gphoto.org/proj/libgphoto2/support.php](http://gphoto.org/proj/libgphoto2/support.php)

---

### Folder Watch / Tethered Shooting

If you use Canon EOS Utility, Nikon Camera Control Pro, Capture One, or
Lightroom tethering:

1. Configure your tethering software to save images to a local directory.
2. In Settings → Camera Backend → `folder_watch`.
3. Set Watch Directory to the same folder.

Prudentia Observatory will detect new files automatically.

---

### INDI Camera

ZWO, QHY, and many other astronomy cameras are supported via INDI drivers.

```bash
indiserver -v indi_asi_ccd   # for ZWO ASI cameras
```

In Settings → Camera Backend → `indi`.

---

## Plate Solving

### Local Astrometry.net

The fastest and most private option.  Works without internet.

**macOS:**
```bash
brew install astrometry-net
```

**Ubuntu/Debian:**
```bash
sudo apt install astrometry.net
```

You also need index files.  For a typical amateur setup (f/6–f/10, APS-C sensor):

```bash
# Index files for field widths 1–5°
wget -P /usr/share/astrometry http://data.astrometry.net/4100/index-4107.fits
wget -P /usr/share/astrometry http://data.astrometry.net/4100/index-4108.fits
wget -P /usr/share/astrometry http://data.astrometry.net/4100/index-4109.fits
wget -P /usr/share/astrometry http://data.astrometry.net/4100/index-4110.fits
```

Choose appropriate index files for your field of view:
[http://data.astrometry.net/](http://data.astrometry.net/)

In Settings → Solver Backend → `astrometry_local`.

---

### Remote Astrometry.net

Works without local installation.  Requires internet.

1. Create a free account at [nova.astrometry.net](https://nova.astrometry.net/).
2. Copy your API key from your profile page.
3. In Settings → Solver Backend → `astrometry_remote`, paste your API key.

Solves take 30–300 seconds depending on server load.

---

## Recommended Equipment

| Category | Budget | Mid-range | High-end |
|---|---|---|---|
| Mount | Sky-Watcher HEQ5 | Sky-Watcher EQ6-R | AstroPhysics 1100 |
| OTA | Refractor 80/600 | Ritchey-Chrétien 6" | CDK12.5 |
| Camera | Canon EOS Rebel series | ASI533MC Pro | ASI2600MM Pro |
| Guide scope | 30mm guide scope | 60mm guide scope | OAG |
| Guide camera | ZWO ASI120Mini | ZWO ASI174Mini | QHY5-III |
| Focuser | Crayford manual | ZWO EAF | Moonlite motor |

---

## Polar Alignment

For accurate tracking and plate-solve-and-centre workflows, polar alignment
is essential.

- Use **PoleMaster** (QHYCCD) or **SharpCap**'s polar alignment routine.
- For EQ mounts: Polar Alignment Error < 2 arcmin is sufficient for
  3–5 minute unguided exposures.
- For longer exposures, use a guide camera (PHD2/PHD Guiding 2) and guide star.

> Guide camera support is planned for a future version of Prudentia Observatory.
> The dithering placeholder in the sequence panel is reserved for this integration.
