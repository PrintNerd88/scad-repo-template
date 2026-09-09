// assembly.scad — composes parts for a visual check. Not printed.
//
// `use <>` imports mounting_plate() without running example.scad's own
// top-level call — which is exactly why every part wraps its geometry in a
// module and takes its inputs as arguments rather than reading globals.
//
// Note: the Makefile's pattern rule renders every src/*.scad, so this does
// produce out/assembly.stl. Ignore it, or move assemblies to src/assemblies/
// and exclude them from PARTS.

// BOSL2 must be include'd here too, not just in example.scad. `use <>` imports
// modules and functions but NOT variables, and BOSL2's diff()/tag() machinery
// reads globals like $tags_shown that std.scad defines. Without this line the
// part renders empty (2021.01) or fails an assert inside BOSL2 (2025+).
include <../vendor/BOSL2/std.scad>
use <example.scad>

$fa = $preview ? 6 : 2;
$fs = $preview ? 1 : 0.4;

stack_gap = 14;   // clearance between the two plates

module assembly() {
    mounting_plate();
    // Second plate flipped and stacked, to check the boss clears it.
    translate([0, 0, stack_gap]) mounting_plate(boss = false);
}

assembly();
