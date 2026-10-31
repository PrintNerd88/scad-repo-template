// assembly.scad — the demo parts together, to check how they fit: the cap on
// the plate's boss. An assembly: never printed, so `make stl` skips it,
// `make png` previews it, and `make test` fails if it stops evaluating
// cleanly.
//
// `use <>` imports mounting_plate() and boss_cap() without running the part
// files' own top-level calls — which is exactly why every part wraps its
// geometry in a module.
//
// The parts take their measurements from params.scad. Change them there; this
// file only says what to show.

/* [View] */
// Lifts the cap off the boss, to see both; 0 seats it.
cap_lift = 0;             // [0:1:40]

/* [Quality] */
$fa = $preview ? 6 : 2;
$fs = $preview ? 1 : 0.4;

module __Customizer_Limit__ () {}

// BOSL2 must be include'd here too, not just in the parts. `use <>` imports
// modules and functions but NOT variables, and BOSL2's diff()/tag() machinery
// reads globals like $tags_shown that std.scad defines. Without this line the
// plate renders empty or fails an assert inside BOSL2, depending on the
// OpenSCAD version.
// params.scad is include'd for the same reason: this file needs its
// variables, to know where the boss is.
include <../vendor/BOSL2/std.scad>
include <params.scad>
use <plate.scad>
use <cap.scad>

// One colour per part, so the check reads at a glance. `make png` previews
// the assembly rather than rendering it, which keeps the colours on every
// OpenSCAD version. The preview only shows what lies behind something
// transparent if it is drawn first, so the see-through cap comes last.
module assembly() {
    color("steelblue") mounting_plate();
    if (add_boss)
        color("orange", 0.6)
            translate([plate_length / 2, plate_width / 2, plate_thick + boss_height + cap_lift])
                boss_cap();
}

assembly();
