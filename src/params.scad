// params.scad — every measurement of the demo parts. Template parameters.
//
// The plate and the cap both take their sizes from here, so the cap always
// fits the plate's boss: change a measurement here, never in a part file.
// Each part `include`s this file, which copies its variables into the part;
// `use` would not, as it imports only modules and functions.
//
// Not a part: it draws nothing, and `make` builds nothing from it.
//
// Units: millimetres.

// ---------------------------------------------------------------------------
// CUSTOMIZER FORMAT
//    - Group with /* [Name] */ headers. Annotate ranges/choices in a trailing
//      comment; that comment IS the widget definition. A comment on the line
//      above a parameter is its description.
//    - snake_case throughout. Units in the name or comment when not mm.
//    - OpenSCAD's Customizer panel, and its JSON presets, only reach the
//      opened file's own parameters, never these from a part that includes
//      them. The format still says what each one is and the values it takes.
//      For a variant, override them with -D (see AGENTS.md).
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// The plate, src/plate.scad
// ---------------------------------------------------------------------------

/* [Plate] */
plate_length = 60;        // [20:200]
plate_width  = 40;        // [20:200]
plate_thick  = 3;         // [1.5:0.5:10]
corner_round = 4;         // [0:0.5:10]

/* [Mounting holes] */
hole_count_x = 2;         // [1:6]
hole_count_y = 2;         // [1:6]
hole_size    = "M3";      // [M2, M2.5, M3, M4, M5]
hole_margin  = 6;         // distance from edge to hole centre

/* [Boss] */
// A boss in the middle of the top face, which the cap fits over.
add_boss     = true;
boss_od      = 12;        // [6:30]       across flats, when hex
boss_height  = 8;         // [2:30]
boss_style   = "round";   // [round, hex]

// ---------------------------------------------------------------------------
// The cap, src/cap.scad
// ---------------------------------------------------------------------------

/* [Cap] */
// Clearance round the boss, as src/lib/common.scad's clearance() adds it. If the
// cap is loose, go tighter; if it won't go on, looser.
cap_fit      = "normal";  // [tight, normal, loose]
cap_wall     = 2;         // [0.8:0.2:5]  side wall
cap_top      = 2;         // [0.8:0.2:5]  closed end
// How far it reaches down the boss. Keep it below boss_height, so the cap
// sits on top of the boss rather than on the plate.
cap_depth    = 6;         // [1:0.5:30]

/* [Hidden] */
// Internals that must be top-level but shouldn't appear in the Customizer.
eps = 0.01;               // overlap fudge so booleans don't leave zero-thickness faces
