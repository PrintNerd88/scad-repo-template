// common.scad — shared modules/functions. Definitions only.
//
// Nothing in this file instantiates geometry at the top level, and nothing
// reads a global: every input is a parameter. That makes the file safe to
// `use <>` from anywhere, including tests.

// Grid of cylinders for a hole pattern. Caller subtracts it.
module hole_pattern(w, h, d, margin = 5) {
    for (x = [margin, w - margin], y = [margin, h - margin])
        translate([x, y, -1]) cylinder(d = d, h = 100);
}

function clearance(nominal, fit = "normal") =
    fit == "tight" ? nominal + 0.1 :
    fit == "loose" ? nominal + 0.4 :
                     nominal + 0.2;
