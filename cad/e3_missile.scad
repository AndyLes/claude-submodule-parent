// E3 X-wing cruciform missile interceptor — parametric (mirrors cuas/design/e3_config.py)
// Render (OpenSCAD):
//   openscad -D 'part="assembly"' -o out/e3_assembly.stl cad/e3_missile.scad
//   parts: "nose" | "body" | "tail" | "wing" | "fin" | "assembly"
// Units: mm. Tube-launched; 4 cruciform wings (X, 45) + 4 tail fins; rear pusher.

/* ---- params ---- */
body_d    = 58;      // fuselage outer diameter (fits 4S pack)
wall      = 2.4;
nose_len  = 130;     // ogive nose (holds inert mass + camera)
body_len  = 300;     // battery + electronics bay
tail_len  = 120;     // boattail to pusher
motor_d   = 30;      // pusher motor OD (~2216)
wing_span = 95;      // root -> tip (single panel)
wing_root = 70;      // chord at root
wing_tip  = 40;      // chord at tip
wing_th   = 6;
fin_span  = 55;
fin_root  = 55;
fin_tip   = 30;
fin_th    = 5;
cam_d     = 6;       // camera bore (nose)
$fn       = 72;

total_len = nose_len + body_len + tail_len;
wing_z    = nose_len + body_len*0.45;              // cruciform wing station
fin_z     = nose_len + body_len + tail_len*0.45;   // tail fin station

function nose_r(z) = (body_d/2) * sqrt(max(0, 1 - pow((nose_len - z)/nose_len, 2)));  // semi-ellipse ogive

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
    // 4x servo pockets at the tail fins (MG90S), pushrod exits to control surface
    for (a = [45,135,225,315]) rotate([0,0,a]) translate([body_d/2 - 15, -12, fin_z - 12]) cube([16, 24, 24]);
  }
}

cs_chord = fin_root * 0.3;   // rear ~30% of the fin = movable control surface

module control_surface(chord, span, th) {           // hinged trailing-edge flap
  difference() {
    panel(span, chord, chord * 0.6, th);
    translate([-th/2 - 0.1, 4, 4]) cube([th + 0.2, 2.5, 6]);   // control-horn slot
  }
}

module tail_control_surfaces() {                    // 4 flaps at the fin trailing edges (neutral)
  for (a = [45,135,225,315])
    rotate([0,0,a]) translate([0, body_d/2 - 2, fin_z + fin_root/2 - cs_chord/2])
      control_surface(cs_chord, fin_span * 0.9, fin_th);
}

module panel(span, root, tip, th) {                 // tapered swept plate, extends +Y
  hull() {
    translate([-th/2, 0, 0]) cube([th, 0.1, root]);
    translate([-th/2, span, root*0.35]) cube([th, 0.1, tip]);
  }
}

module cruciform(span, root, tip, th, z_at) {
  for (a = [45, 135, 225, 315])
    rotate([0,0,a]) translate([0, body_d/2 - 2, z_at - root/2]) panel(span, root, tip, th);
}

module motor_mount() {
  translate([0,0, total_len - wall])
    difference() {
      cylinder(h = wall + 4, d = motor_d + 8);
      translate([0,0,-0.1]) cylinder(h = wall + 5, d = motor_d - 6);
      for (a = [0:90:359]) rotate([0,0,a]) translate([8,0,-0.1]) cylinder(h = wall + 5, d = 3.2);
    }
}

module assembly() {
  fuselage();
  cruciform(wing_span, wing_root, wing_tip, wing_th, wing_z);
  cruciform(fin_span, fin_root, fin_tip, fin_th, fin_z);
  tail_control_surfaces();
  motor_mount();
}

/* ---- part selector (print sections along the tube axis) ---- */
part = "assembly";
if (part == "assembly") assembly();
else if (part == "nose") intersection() { fuselage(); translate([-100,-100,0]) cube([200,200, nose_len + 25]); }
else if (part == "body") { intersection() { fuselage(); translate([-100,-100, nose_len + 25]) cube([200,200, body_len - 10]); }
                           cruciform(wing_span, wing_root, wing_tip, wing_th, wing_z); }
else if (part == "tail") { intersection() { fuselage(); translate([-100,-100, nose_len + body_len + 15]) cube([200,200, tail_len]); }
                           cruciform(fin_span, fin_root, fin_tip, fin_th, fin_z); motor_mount(); }
else if (part == "wing") panel(wing_span, wing_root, wing_tip, wing_th);
else if (part == "fin") panel(fin_span, fin_root, fin_tip, fin_th);
else if (part == "control_surface") control_surface(cs_chord, fin_span * 0.9, fin_th);   // print 4x
