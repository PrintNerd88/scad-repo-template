// cap.scad — cap for the boss on the mounting plate. Template second part.
//
// A cup that fits over the boss in plate.scad: round or hex inside, as the
// boss is, with clearance all round. It takes the boss's measurements from
// params.scad, as the plate does, so the two always match. This file draws
// it closed end down, which is how it prints, without support;
// assembly.scad shows it on the plate.
//
// Units: millimetres. boss_cap() draws it as it sits on the boss, centred on
// the Z axis, with the top of the boss at Z=0.
//
// Requires: OpenSCAD 2021.01+ (2025.x recommended), BOSL2 in vendor/.
// Build:    make stl   |   openscad -o out/cap.stl src/cap.scad

/* [Quality] */
$fa = $preview ? 6 : 2;
$fs = $preview ? 1 : 0.4;

module __Customizer_Limit__ () {}

include <../vendor/BOSL2/std.scad>
include <params.scad>
use <lib/common.scad>

// The cap, as it sits on the boss: open end down, its inside resting on the
// top of the boss at Z=0.
module boss_cap(
    boss_d = boss_od,
    boss_h = boss_height,
    style  = boss_style,
    fit    = cap_fit,
    wall   = cap_wall,
    top    = cap_top,
    depth  = cap_depth
) {
    assert(depth < boss_h, "cap_depth reaches the plate: keep it below boss_height");

    // The boss's own shape, `fit` wider. A hex boss is boss_d across flats,
    // so its corners reach further out, and the wall goes round them.
    socket = clearance(boss_d, fit);
    corner = style == "hex" ? socket / cos(30) : socket;

    difference() {
        down(depth) cyl(d = corner + 2 * wall, h = depth + top, anchor = BOTTOM);
        down(depth + eps)
            if (style == "hex") cyl(d = corner, h = depth + eps, $fn = 6, anchor = BOTTOM);
            else                cyl(d = socket, h = depth + eps, anchor = BOTTOM);
    }
}

// The cap turned over for printing: closed end on the bed.
module boss_cap_print() {
    up(cap_top) xrot(180) boss_cap();
}

echo(str("boss_cap ", boss_style, " ", boss_od, " + ", cap_fit, " fit, ", cap_depth, " deep"));
boss_cap_print();
