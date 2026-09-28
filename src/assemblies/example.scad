// example.scad — the demo mounting plate, twice, stacked to check that the
// lower plate's boss clears the upper plate. An assembly: never printed, so
// `make stl` skips it, `make png` previews it, and `make test` fails if it
// stops evaluating cleanly.
//
// `use <>` imports mounting_plate() without running ../example.scad's own
// top-level call — which is exactly why every part wraps its geometry in a
// module and takes its inputs as arguments rather than reading globals.

/* [Assembly] */
stack_gap = 14;           // [4:40] distance between the two plates' bottom faces

/* [Quality] */
$fa = $preview ? 6 : 2;
$fs = $preview ? 1 : 0.4;

// BOSL2 must be include'd here too, not just in the part. `use <>` imports
// modules and functions but NOT variables, and BOSL2's diff()/tag() machinery
// reads globals like $tags_shown that std.scad defines. Without this line the
// part renders empty (2021.01) or fails an assert inside BOSL2 (2025+).
// Paths are one level deeper than in a part.
include <../../vendor/BOSL2/std.scad>
use <../example.scad>

// One colour per part, so the check reads at a glance. `make png` previews
// assemblies rather than rendering them, which keeps the colours on every
// OpenSCAD version.
module assembly() {
    color("steelblue") mounting_plate();
    // The upper plate without its boss, so only the lower boss is in question.
    color("orange") translate([0, 0, stack_gap]) mounting_plate(boss = false);
}

assembly();
