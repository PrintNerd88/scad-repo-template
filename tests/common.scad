// common.scad — asserts on lib/common.scad. Run with `make test`.
//
// OpenSCAD's whole test framework is assert() and echo(): a failed assert
// exits non-zero, which is all `make test` needs. Test functions, not
// geometry — there is no good automated STL diff in the standard toolchain.

use <../lib/common.scad>

assert(clearance(3) == 3.2, "default clearance");
assert(clearance(3, "tight") == 3.1, "tight clearance");
assert(clearance(3, "loose") == 3.4, "loose clearance");
assert(clearance(3, "nonsense") == 3.2, "unknown fit falls back to normal");

echo("common.scad: OK");
