// plate.scad — parametric mounting plate. Template main part.
//
// Purpose: demonstrate OpenSCAD conventions, not to be a useful part.
// Every section is annotated with the convention it illustrates.
// Its measurements are in params.scad, shared with cap.scad, which fits
// over the boss; assembly.scad shows the two together.
// Units: millimetres. Origin: bottom-left-front corner of the plate, Z up,
// so the part occupies the positive octant: x in [0,l], y in [0,w], z in [0,t].
//
// Requires: OpenSCAD stable or nightly (nightly recommended), BOSL2 in vendor/.
// Build:    make stl   |   openscad -o out/plate.stl src/plate.scad

// ---------------------------------------------------------------------------
// 1. CUSTOMIZER PARAMETERS
//    - Measurements live in params.scad, so every part that shares one reads
//      the same value. Add new ones there, never here.
//    - What stays here is only this file's own: render quality.
//    - Top of file, before any include/use, so they're the first thing a
//      reader sees and the Customizer picks them up.
// ---------------------------------------------------------------------------

/* [Quality] */
// Prefer $fa/$fs over a global $fn: resolution scales with feature size.
// Preview coarse, render fine — $preview is true in F5, false in F6/CLI.
$fa = $preview ? 6 : 2;
$fs = $preview ? 1 : 0.4;

// Anything below this line is hidden from the Customizer regardless of group.
module __Customizer_Limit__ () {}

// ---------------------------------------------------------------------------
// 2. IMPORTS
//    - include <> : textual paste — needed for BOSL2 (it defines constants
//      like TOP/BOTTOM/CENTER and $-variables that `use` would not export),
//      and for params.scad, whose variables `use` would not import either.
//    - use <>     : definitions only — correct for your own src/lib/ files, as
//      cap.scad does.
//    - Relative paths, never OPENSCADPATH.
// ---------------------------------------------------------------------------

include <../vendor/BOSL2/std.scad>
include <params.scad>

// ---------------------------------------------------------------------------
// 3. CONSTANTS AND LOOKUP DATA
//    - Variables are immutable and file-scoped; the LAST assignment wins and
//      applies to the whole file (classic gotcha — never "reassign").
//    - UPPER_SNAKE for true constants/tables; snake_case for everything else.
//    - Data as lists of [key, value] pairs and read with lookup()/search().
// ---------------------------------------------------------------------------

// [name, clearance_hole_d, head_d, head_h] — ISO 273 medium fit
SCREW_TABLE = [
    ["M2",   2.4,  3.8, 2.0],
    ["M2.5", 2.9,  4.5, 2.5],
    ["M3",   3.4,  5.5, 3.0],
    ["M4",   4.5,  7.0, 4.0],
    ["M5",   5.5,  8.5, 5.0],
];

// ---------------------------------------------------------------------------
// 4. FUNCTIONS
//    - Pure, single expression, no side effects. Use let() for intermediates
//      and ternary chains for branching. Recursion for loops.
//    - assert() inside functions validates inputs at the call site.
//    - Doc comment above: what it returns, units, and any assumptions.
// ---------------------------------------------------------------------------

// Returns [clearance_d, head_d, head_h] for a screw name, or asserts.
function screw_dims(name) =
    let (idx = search([name], SCREW_TABLE, 1, 0)[0])
    assert(idx != [], str("unknown screw size: ", name))
    [for (i = [1:3]) SCREW_TABLE[idx][i]];

// Evenly spaced positions along one axis, inset by `margin` from each end.
// n == 1 returns the centre.
function axis_positions(length, n, margin) =
    n == 1 ? [length / 2]
           : [for (i = [0 : n - 1]) margin + i * (length - 2 * margin) / (n - 1)];

// Cartesian product of two position lists -> list of [x, y].
function grid_points(xs, ys) = [for (x = xs, y = ys) [x, y]];

// ---------------------------------------------------------------------------
// 5. MODULES
//    - Each module is one nameable thing. Keep them small; compose them.
//    - Parameters with defaults; callers use NAMED arguments for anything
//      past the first one or two.
//    - Positive geometry in one module, negatives in another, so the caller
//      controls the boolean. Negatives are oversized by eps on open faces.
//    - BOSL2 idioms shown: cuboid/cyl with anchors, attach(), diff()/tag(),
//      positional helpers (up/down/etc.), and *_copies() distributors.
// ---------------------------------------------------------------------------

// Base plate, rounded vertical edges only. Anchored so its bottom-left-front
// corner sits at origin (see header) and the plate extends into +X/+Y/+Z.
// BOSL2 anchors avoid manual translate(). Note FRONT (-Y face) is the anchor
// that makes the body extend toward +Y — using BACK here puts the plate in
// -Y, where the hole grid and boss (both computed in +Y) would miss it.
module plate(l, w, t, r) {
    cuboid([l, w, t], rounding = r, edges = "Z", anchor = BOTTOM + LEFT + FRONT);
}

// Through-hole negative. h is oversized and starts below Z=0 (BOTTOM anchor
// then down(eps)) so both faces are cut cleanly.
module clearance_hole(d, t) {
    down(eps) cyl(d = d, h = t + 2 * eps, anchor = BOTTOM);
}

// Optional boss on the top face. Demonstrates a style switch on a string
// parameter, and children() passthrough so callers can attach to it.
module boss(od, h, style = "round") {
    if (style == "hex") {
        // circumscribed hex: flat-to-flat = od
        cyl(d = od / cos(30), h = h, $fn = 6, anchor = BOTTOM) children();
    } else {
        cyl(d = od, h = h, rounding2 = 1, anchor = BOTTOM) children();
    }
}

// The finished part. Everything is parameterised through arguments, which
// default to the values in params.scad, so another file can `use` it and
// pass its own.
module mounting_plate(
    l = plate_length,
    w = plate_width,
    t = plate_thick,
    r = corner_round,
    nx = hole_count_x,
    ny = hole_count_y,
    screw = hole_size,
    margin = hole_margin,
    boss = add_boss,
    boss_d = boss_od,
    boss_h = boss_height,
    style = boss_style
) {
    // Validate early; message names the parameter.
    assert(2 * margin < l && 2 * margin < w, "hole_margin too large for plate");
    assert(!boss || boss_d < min(l, w), "boss_od larger than plate");

    hole_d = screw_dims(screw)[0];
    pts    = grid_points(axis_positions(l, nx, margin), axis_positions(w, ny, margin));

    // BOSL2 diff(): children tagged "remove" are subtracted from the rest.
    // Cleaner than difference(){ ... } with positional first-child semantics.
    diff() {
        plate(l, w, t, r);

        // Subtract holes. move_copies() places one child per point.
        tag("remove") move_copies(pts) clearance_hole(hole_d, t);

        // Add the boss on the top face, centred. Not tagged, so it's unioned.
        if (boss)
            translate([l / 2, w / 2, t]) boss(boss_d, boss_h, style);
    }
}

// ---------------------------------------------------------------------------
// 6. TOP-LEVEL INSTANTIATION
//    - Exactly one call, at the bottom. No guard is needed: `use <>` imports
//      definitions only and never runs top-level geometry, which is exactly
//      why parts wrap their geometry in a module. (`$parent_modules` is undef
//      at file scope, so guarding on it renders nothing at all.)
//    - No debug modifiers (# % ! *) committed. Use them locally, remove.
//    - echo() a short summary — useful in CI logs and the console.
// ---------------------------------------------------------------------------

echo(str("mounting_plate ", plate_length, "x", plate_width, "x", plate_thick,
         " holes=", hole_count_x * hole_count_y, " ", hole_size));
mounting_plate();
