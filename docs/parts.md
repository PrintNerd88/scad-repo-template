# Parts

One section per file in `src/`: what it makes, its parameters, and how to print it.

## `example.scad` — mounting plate

The demo part: a rectangular plate with rounded vertical corners, a grid of screw
clearance holes, and an optional centred boss, round or hexagonal. Each section of the
file is annotated with the OpenSCAD convention it illustrates. Units are millimetres, and
the plate sits in the positive octant with its bottom-left-front corner at the origin.

### Parameters

Open the part in OpenSCAD and use **Window → Customizer**, or edit the block at the top
of `src/example.scad`.

| Parameter | Default | Range | Meaning |
|---|---|---|---|
| `plate_length` | 60 | 20–200 | Plate length (mm) |
| `plate_width` | 40 | 20–200 | Plate width (mm) |
| `plate_thick` | 3 | 1.5–10, step 0.5 | Plate thickness (mm) |
| `corner_round` | 4 | 0–10, step 0.5 | Vertical corner radius (mm) |
| `hole_count_x` | 2 | 1–6 | Holes along X |
| `hole_count_y` | 2 | 1–6 | Holes along Y |
| `hole_size` | `M3` | M2…M5 | Screw size; drives clearance diameter |
| `hole_margin` | 6 | — | Edge to hole centre (mm) |
| `add_boss` | `true` | bool | Add the centred boss |
| `boss_od` | 12 | 6–30 | Boss outer diameter (mm) |
| `boss_height` | 8 | 2–30 | Boss height (mm) |
| `boss_style` | `round` | round, hex | Boss profile |

Saved sets live in `presets/example.json`: `default`, `large-m5` and `plain`.

### Print settings

Fill in per part: material, layer height, orientation, supports, infill.

## `assembly.scad` — visual check

Composes the parts to check how they fit together; it isn't meant to be printed, though
the Makefile's pattern rule renders it to `out/assembly.stl` along with the parts.
