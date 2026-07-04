// E3 folding-wing pusher interceptor — ROUNDED-RECT fuselage + slide-in equipment tray.
// Flat internal shelves -> easy assembly/service; top hatch; square-tube / rail launch.
// Top speed is prop-limited, so the small drag penalty of a boxy body costs ~few% range, not speed.
// Render: openscad -D 'part="assembly"' -o out/e3_assembly.stl cad/e3_missile.scad
// parts: nose | body | tail | tray | wing | control_surface | hinge_pin | assembly
// Units: mm.

/* ---- fuselage cross-section (rounded rectangle) ---- */
bw       = 46;      // width  (fits 6S 3500 + tray)
bh       = 40;      // height
corner_r = 8;       // rounded corners
wall     = 2.4;
nose_len = 120;
body_len = 300;
tail_len = 120;
motor_d  = 30;
cam_d    = 6;
$fn      = 40;

// monoplane folding wing
wing_semispan = 230; wing_root_c = 130; wing_tip_c = 80; wing_th = 10;
// conventional tail: horizontal stab (elevator) + vertical fin (rudder)
tail_root = 55; tail_tip = 32; tail_th = 5; tail_hspan = 70; tail_vspan = 60;

total_len = nose_len + body_len + tail_len;
wing_z    = nose_len + body_len*0.45;
fin_z     = nose_len + body_len + tail_len*0.5;

module rrect(w, h, r) {
  hull() for (sx=[-1,1], sy=[-1,1]) translate([sx*(w/2-r), sy*(h/2-r)]) circle(r=r, $fn=24);
}

module fuse_solid() {
  // ogive-ish nose (hull of tapering rrect slices following a semi-ellipse)
  hull() for (i=[0:5]) let(z = i/5*nose_len, s = sqrt(max(0.05, 1 - pow((nose_len - z)/nose_len, 2))))
    translate([0,0,z]) linear_extrude(0.6) rrect(max(3, bw*s), max(3, bh*s), max(1.5, corner_r*s));
  // body
  translate([0,0,nose_len]) linear_extrude(body_len) rrect(bw, bh, corner_r);
  // boattail to motor
  hull() {
    translate([0,0,nose_len+body_len]) linear_extrude(0.6) rrect(bw, bh, corner_r);
    translate([0,0,total_len]) linear_extrude(0.6) rrect(motor_d+8, motor_d+8, 8);
  }
}

module fuselage() {
  difference() {
    fuse_solid();
    translate([0,0, nose_len*0.5]) linear_extrude(body_len + nose_len*0.5 + 1) rrect(bw-2*wall, bh-2*wall, corner_r-1); // bay
    translate([0,0, nose_len - 8]) cylinder(h = 40, d = cam_d);                                                         // camera bore
    translate([-(bw/2-8), bh/2 - wall - 1, nose_len + 30]) cube([bw-16, 8, body_len - 70]);                             // TOP HATCH (tray access)
    translate([0,0, total_len - 24]) cylinder(h = 30, d = motor_d);                                                     // motor bore
    for (s=[90,270]) rotate([0,0,s]) translate([0, bw/2-14, wing_z+30]) cube([20, 16, 18]);                             // aileron servo pockets
  }
}

module panel(span, root, tip, th) {
  hull() {
    translate([-th/2, 0, 0]) cube([th, 0.1, root]);
    translate([-th/2, span, root*0.35]) cube([th, 0.1, tip]);
  }
}

module monoplane_wing() {
  for (a=[90,270]) rotate([0,0,a]) translate([0, bw/2 - 3, wing_z - wing_root_c/2])
    panel(wing_semispan, wing_root_c, wing_tip_c, wing_th);
}

/* ---- folding-wing pin hinge (fold axis = wing thickness) ---- */
pin_d = 2.5; barrel_l = 24;
module wing_hinge_barrel() {
  translate([0, bw/2 - 1, wing_z]) rotate([0,90,0])
    difference() {
      union() { cylinder(h=barrel_l, d=9, center=true, $fn=28); translate([0,-7,0]) cube([9,14,barrel_l], center=true); }
      cylinder(h=barrel_l+1, d=pin_d, center=true, $fn=20);
      translate([6,0,0]) cube([6,6,barrel_l+1], center=true);        // torsion-spring seat
    }
}
module wing_hinges() { for (a=[90,270]) rotate([0,0,a]) wing_hinge_barrel(); }
module hinge_pin() { cylinder(h = barrel_l + 6, d = pin_d - 0.15, $fn = 20); }

module tail() {
  for (a=[90,270]) rotate([0,0,a]) translate([0, bw/2 - 2, fin_z - tail_root/2]) panel(tail_hspan, tail_root, tail_tip, tail_th); // horiz stab
  translate([0, bh/2 - 2, fin_z - tail_root/2]) panel(tail_vspan, tail_root, tail_tip, tail_th);                                  // vert fin
}

module motor_mount() {
  translate([0,0, total_len - wall])
    difference() {
      cylinder(h = wall+4, d = motor_d+8);
      translate([0,0,-0.1]) cylinder(h = wall+5, d = motor_d-6);
      for (a=[0:90:359]) rotate([0,0,a]) translate([8,0,-0.1]) cylinder(h = wall+5, d = 3.2);
    }
}

/* ---- slide-in equipment tray: all electronics on ONE part, pulls out the top hatch ---- */
module wallbox(w, l, h) { difference() { cube([w, h, l]); translate([2,-1,2]) cube([w-4, h+2, l-4]); } }
module equipment_tray() {
  tw = bw - 2*wall - 3; base = 2.5; tl = body_len - 60;
  difference() {
    union() {
      translate([-tw/2, 0, 0]) cube([tw, base, tl]);                                  // base plate
      translate([-16, base, 30]) wallbox(32, 32, 6);                                  // FC bay (30x30)
      translate([-15, base, 80]) wallbox(30, 42, 5);                                  // ESC bay
      translate([-16, base, 150]) wallbox(32, 68, 6);                                 // Pi Zero 2W bay (30x65)
    }
    for (z=[tl-70, tl-20]) translate([-tw/2-1, -1, z]) cube([tw+2, base+2, 4]);        // battery strap slots
  }
}

module assembly() {
  fuselage();
  monoplane_wing();
  wing_hinges();
  tail();
  motor_mount();
}

/* ---- part selector ---- */
part = "assembly";
if (part == "assembly") assembly();
else if (part == "nose") intersection() { fuselage(); translate([-100,-100,0]) cube([200,200, nose_len + 25]); }
else if (part == "body") intersection() { fuselage(); translate([-100,-100, nose_len + 25]) cube([200,200, body_len - 10]); }
else if (part == "tail") { intersection() { fuselage(); translate([-100,-100, nose_len + body_len + 15]) cube([200,200, tail_len]); } tail(); motor_mount(); }
else if (part == "tray") equipment_tray();
else if (part == "wing") panel(wing_semispan, wing_root_c, wing_tip_c, wing_th);
else if (part == "control_surface") control_surface_stub();
else if (part == "hinge_pin") hinge_pin();

module control_surface_stub() { panel(wing_semispan*0.5, wing_root_c*0.25, wing_root_c*0.15, wing_th); }
