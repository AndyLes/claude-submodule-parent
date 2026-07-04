// E3 PNEUMATIC tube launcher — printed parts (tube itself = off-the-shelf square section).
// Decision: pneumatic (constant force -> peak g = avg 6.6g at 1.3m, within airframe 10g limit;
// bungee would peak ~12g). Low pressure (~0.7-1 bar), repeatable exit speed, fast reset.
// Render: openscad -D 'part="assembly"' -o out/e3_launcher.stl cad/e3_launcher.scad
// parts: piston | breech | muzzle | assembly
// Units: mm.

/* ---- params ---- */
tube_id   = 115;      // square tube inner (fits fuselage 46x40 + folded wings/tail)
tube_wall = 4;       // off-the-shelf tube wall
seal_w    = 4;       // O-ring / foam seal land
$fn       = 48;
tube_o    = tube_id + 2*tube_wall;

module rrect(w, h, r) { hull() for (sx=[-1,1], sy=[-1,1]) translate([sx*(w/2-r), sy*(h/2-r)]) circle(r=r, $fn=24); }

/* piston / sabot: slides in tube behind airframe, pushes tail, stopped at muzzle */
module piston() {
  h = 30;
  difference() {
    linear_extrude(h) rrect(tube_id - 1, tube_id - 1, 8);
    translate([0,0, h*0.45]) linear_extrude(seal_w)                      // seal groove
      difference() { rrect(tube_id - 1, tube_id - 1, 8); rrect(tube_id - 7, tube_id - 7, 6); }
    translate([0,0,-1]) linear_extrude(h*0.55) rrect(tube_id - 18, tube_id - 18, 6); // lighten
  }
  translate([0,0,h]) cylinder(h = 10, d = 22);                          // push spigot (airframe tail)
}

/* breech cap: seals rear, air-inlet boss + valve mount, bolts to tube */
module breech_cap() {
  difference() {
    union() {
      linear_extrude(6) rrect(tube_o + 18, tube_o + 18, 10);            // flange
      translate([0,0,6]) linear_extrude(22) rrect(tube_id - 1, tube_id - 1, 8); // plug into tube
    }
    translate([0,0,-1]) cylinder(h = 10, d = 11.5);                     // 1/4" BSP air inlet
    for (sx=[-1,1], sy=[-1,1]) translate([sx*(tube_o/2 + 4), sy*(tube_o/2 + 4), -1]) cylinder(h = 8, d = 4.2); // bolts
  }
}

/* muzzle guide: front collar, guides airframe, catches piston (stop lip) */
module muzzle_guide() {
  difference() {
    linear_extrude(32) rrect(tube_o + 18, tube_o + 18, 10);            // collar
    translate([0,0,-1]) linear_extrude(24) rrect(tube_id - 2, tube_id - 2, 7);   // bore
    for (sx=[-1,1], sy=[-1,1]) translate([sx*(tube_o/2 + 4), sy*(tube_o/2 + 4), -1]) cylinder(h = 34, d = 4.2);
  }
  translate([0,0,23]) linear_extrude(9)                                // piston stop lip (narrower)
    difference() { rrect(tube_o + 18, tube_o + 18, 10); rrect(tube_id - 16, tube_id - 16, 6); }
}

part = "assembly";
if (part == "piston") piston();
else if (part == "breech") breech_cap();
else if (part == "muzzle") muzzle_guide();
else {
  color("silver") translate([0,0,40]) linear_extrude(220)              // tube section (off-the-shelf)
    difference() { rrect(tube_o, tube_o, 10); rrect(tube_id, tube_id, 8); }
  translate([0,0,8]) breech_cap();
  translate([0,0,60]) piston();
  translate([0,0,235]) muzzle_guide();
}
