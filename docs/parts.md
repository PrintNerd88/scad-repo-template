# Parts

One section per file in `src/`: what it makes, its parameters, and how to print it.

Every measurement is in `src/params.scad`, which each part includes, so the plate and the
cap always fit each other. To change one, edit that file; OpenSCAD's Customizer panel
doesn't show them when a part is open. To build a variant, override them with `-D` (see
[Variants](development.md#variants)).

## `plate.scad` — mounting plate

The demo part: a rectangular plate with rounded vertical corners, a grid of screw
clearance holes, and an optional centred boss, round or hexagonal. Each section of the
file is annotated with the OpenSCAD convention it illustrates. Units are millimetres, and
the plate sits in the positive octant with its bottom-left-front corner at the origin.

### Parameters

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
| `boss_od` | 12 | 6–30 | Boss outer diameter, across flats when hex (mm) |
| `boss_height` | 8 | 2–30 | Boss height (mm) |
| `boss_style` | `round` | round, hex | Boss profile |

### Print settings

Fill in per part: material, layer height, orientation, supports, infill.

## `cap.scad` — boss cap

A cup that fits over the plate's boss: round or hexagonal inside, as the boss is, with
clearance all round from `clearance()` in `src/lib/common.scad`. It reads the boss's
measurements from `params.scad`, so it follows any change to the boss. It refuses to
render if `cap_depth` would reach down to the plate.

### Parameters

| Parameter | Default | Range | Meaning |
|---|---|---|---|
| `cap_fit` | `normal` | tight, normal, loose | Clearance round the boss |
| `cap_wall` | 2 | 0.8–5, step 0.2 | Side wall thickness (mm) |
| `cap_top` | 2 | 0.8–5, step 0.2 | Closed end thickness (mm) |
| `cap_depth` | 6 | 1–30, step 0.5 | How far it reaches down the boss; less than `boss_height` (mm) |

### Print settings

The STL stands it on its closed end, so it prints without support.

## `assembly.scad` — cap on the plate

Not a part, so never printed: the plate with the cap seated on its boss, the cap
see-through so the boss shows inside it. `cap_lift` raises the cap off the boss to see
both; 0 seats it. `make png` previews it to `out/assembly.png`, each part in its own
colour.
