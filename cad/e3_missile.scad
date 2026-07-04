// E3 folding-wing pusher interceptor — parametric (mirrors cuas/design/e3_config.py)
// Monoplane wing (folds for tube launch) + small fixed cruciform tail fins + rear pusher.
// Render:
//   openscad -D 'part="assembly"' -o out/e3_assembly.stl cad/e3_missile.scad
//   parts: "nose" | "body" | "tail" | "wing" | "tail_fin" | "control_surface" | "assembly"
// Units: mm.

/* ---- params ---- */
body_d    = 58;
wall      = 2.4;
nose_len  = 130;
body_len  = 300;
tail_len  = 120;
motor_d   = 30;
cam_d     = 6;

// monoplane wing (each half folds back along the fuselage for the tube)
wing_semispan = 230;     // per side
wing_root_c   = 130;
wing_tip_c    = 80;
wing_th       = 10;

// small FIXED cruciform tail fins (fit the tube, give stability)
fin_span = 35;
fin_root = 55;
fin_tip  = 30;
fin_th   = 5;
$fn      = 72;

total_len = nose_len + body_len + tail_len;
wing_z    = nose_len + body_len*0.45;
fin_z     = nose_len + body_len + tail_len*0.45;

function nose_r(z) = (body_d/2) * sqrt(max(0, 1 - pow((nose_len - z)/nose_len, 2)));

module fuselage_outer() {
  rotate_extrude($fn=$fn)
    polygon(concat(
      [[0.02, 0]],
      [ for (i=[0:16]) let(z = i/16*nose_len) [ max(0.02, nose_r(z)), z ] ],
      [[body_d/2, nose_len + body_len]],
      [[motor_d/2 + 4, total_len]],
      [[0.02, total_len]]
    ));
}

module fuselage() {
  difference() {
    fuselage_outer();
    translate([0,0, nose_len*0.55]) cylinder(h = body_len + nose_len*0.45 + 1, d = body_d - 2*wall); // bay
    translate([0,0, nose_len - 8]) cylinder(h = 40, d = cam_d);                                        // camera bore
    translate([-22, body_d/2 - wall - 1, nose_len + 40]) cube([44, 10, 150]);                          // battery hatch
    translate([0,0, total_len - 24]) cylinder(h = 30, d = motor_d);                                    // motor bore
    // wing spar tunnel (folding wing hinge passes through) + aileron servo pockets
    translate([-body_d/2-1, -6, wing_z-6]) cube([body_d+2, 12, 12]);                                   // spar tunnel
    for (a = [90,270]) rotate([0,0,a]) translate([body_d/2-14, -10, wing_z+30]) cube([15, 20, 20]);    // aileron servo
    // elevator servo pockets at tail fins
    for (a = [45,135,225,315]) rotate([0,0,a]) translate([body_d/2-13, -9, fin_z-9]) cube([14, 18, 18]);
  }
}

module panel(span, root, tip, th) {
  hull() {
    translate([-th/2, 0, 0]) cube([th, 0.1, root]);
    translate([-th/2, span, root*0.35]) cube([th, 0.1, tip]);
  }
}

module monoplane_wing() {                      // two big panels L/R (deployed)
  for (a = [90,270]) rotate([0,0,a]) translate([0, body_d/2 - 3, wing_z - wing_root_c/2])
    panel(wing_semispan, wing_root_c, wing_tip_c, wing_th);
}

module tail_fins() {                           // 4 small fixed cruciform fins
  for (a = [45,135,225,315]) rotate([0,0,a]) translate([0, body_d/2 - 2, fin_z - fin_root/2])
    panel(fin_span, fin_root, fin_tip, fin_th);
}

module motor_mount() {
  translate([0,0, total_len - wall])
    difference() {
      cylinder(h = wall + 4, d = motor_d + 8);
      translate([0,0,-0.1]) cylinder(h = wall + 5, d = motor_d - 6);
      for (a = [0:90:359]) rotate([0,0,a]) translate([8,0,-0.1]) cylinder(h = wall + 5, d = 3.2);
    }
}

cs_chord = wing_root_c * 0.25;                 // aileron / elevator chord
module control_surface(chord, span, th) {
  difference() {
    panel(span, chord, chord * 0.6, th);
    translate([-th/2 - 0.1, 4, 4]) cube([th + 0.2, 2.5, 6]);   // horn slot
  }
}

module assembly() {
  fuselage();
  monoplane_wing();
  tail_fins();
  motor_mount();
}

/* ---- part selector ---- */
part = "assembly";
if (part == "assembly") assembly();
else if (part == "nose") intersection() { fuselage(); translate([-100,-100,0]) cube([200,200, nose_len + 25]); }
else if (part == "body") { intersection() { fuselage(); translate([-100,-100, nose_len + 25]) cube([200,200, body_len - 10]); } }
else if (part == "tail") { intersection() { fuselage(); translate([-100,-100, nose_len + body_len + 15]) cube([200,200, tail_len]); } tail_fins(); motor_mount(); }
else if (part == "wing") panel(wing_semispan, wing_root_c, wing_tip_c, wing_th);   // print 2x (fold at root)
else if (part == "tail_fin") panel(fin_span, fin_root, fin_tip, fin_th);
else if (part == "control_surface") control_surface(cs_chord, wing_semispan * 0.5, wing_th);
