# Equipment Photos

This folder holds the **real, on-site photographs of LADLI's actual lab instruments**
shown on `equipment.html`, kept separate from the older generic/stock imagery used
elsewhere on the site so it can be updated manually without touching code.

## Confirmed real photos (verified against your on-site labels)

| File | Instrument | Card on `equipment.html` | Also used on |
|---|---|---|---|
| `dga-gas-chromatograph.jpg` / `.webp` | Gas Chromatograph — Dissolved Gas Analysis (DGA) | DGA by GC-TCD/FID | `dga.html` |
| `oil-bdv-tester.jpg` / `.webp` | Automatic Oil Breakdown Voltage (BDV) Tester | Oil Breakdown Voltage Tester | `test-bdv.html` |
| `karl-fischer-titrator-moisture.jpg` / `.webp` | Coulometric KF Titrator / Micro Moisture Meter | Karl Fischer Titrator | `test-moisture.html` |
| `automatic-titrator-acidity.jpg` / `.webp` | Automatic Potentiometric Titrator (Acidity / Neutralisation Value) | Automatic Titrator | `test-acidity.html` |
| `flash-fire-point-apparatus.jpg` / `.webp` | Pensky-Martens Flash Point Apparatus | *(currently not shown — see note)* | `test-flash-point.html` |

## No-photo cards (photo removed at your request)

These `equipment.html` cards currently show **no photo at all** — just the title,
description, and "Discuss capability" link. No broken image, no placeholder
graphic, nothing:

- Tan Delta / Power Factor Meter
- Resistivity Meter
- Density Meter
- Flash and Fire Point Apparatus
- Low Temperature Bath
- Supporting Equipment

## How to add a photo to one of these cards

1. Save your photo into this folder, e.g. `tan-delta-power-factor-meter.jpg`
   (recommended: JPG, ~1200px on the longest side, quality ~80–90%).
2. In `site/equipment.html`, find that card's `<article class="card">` block and
   add an `<img>` line back in, following the pattern used by the cards that
   already have photos, e.g.:
   ```html
   <article class="card" style="padding: 0; overflow: hidden">
     <img src="assets/images/equipment/tan-delta-power-factor-meter.jpg"
          alt="Tan Delta / Power Factor Meter"
          style="width: 100%; height: 210px; object-fit: contain; background: var(--sky-12); padding: 10px" />
     <div style="padding: 24px">
       <h3>Tan Delta / Power Factor Meter</h3>
       ...
   ```

## Note on Flash and Fire Point Apparatus

A real, correctly-matched photo of your Pensky-Martens apparatus already exists
here as `flash-fire-point-apparatus.jpg` / `.webp` (it's used on
`test-flash-point.html`). It was **not** deleted — it's simply not referenced by
the equipment.html card right now, per your request to remove that card's photo.
To bring it back, add the `<img>` back per the instructions above pointing at
`flash-fire-point-apparatus.jpg`.

## Still using older generic placeholder imagery (unchanged)

- Interfacial Tension (IFT) Apparatus — still uses `../equipment-ift.webp`
