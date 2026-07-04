// E2 5" printed auto-ram frame — parametric (values mirror cuas/design/e2_config.py)
// Render one part at a time (set `part` below), e.g.:
//   openscad -D 'part="frame"'        -o out/e2_frame.stl        cad/e2_frame.scad
//   openscad -D 'part="battery_tray"' -o out/e2_battery_tray.stl cad/e2_frame.scad
//   openscad -D 'part="nose"'         -o out/e2_nose.stl         cad/e2_frame.scad
// Units: mm.  True-X 5" (220 mm wheelbase). PETG, deep-section arms vs flutter.

/* ---------- parameters (mirror e2_config.py) ---------- */
wheelbase   = 220;            // motor-to-motor diagonal
arm_len     = wheelbase/2;    // 110 mm, center -> motor
arm_w       = 7;             // arm width
arm_h       = 9;             // arm height (deep section: raises resonance)
hub_r       = 24;            // central hub radius
motor_mount = 16;            // 16x16 M3 (2207)
motor_shaft = 8.2;           // motor shaft/bell clearance
stack       = 30.5;          // 30.5x30.5 M3 stack (FC/ESC)
m3          = 3.2;           // M3 clearance hole
prop_r      = 63.5;          // 5" prop radius (clearance reference)
nose_len    = 46;            // reinforced ram nose forward
cam_d       = 6;             // camera lens bore (nose, < tip so it stays manifold)
deck_floor  = 3;             // stack bathtub floor thickness
$fn         = 48;

part = "frame";              // "frame" | "battery_tray" | "nose"

/* ---------- helpers ---------- */
module m3hole(h) { translate([0,0,-0.1]) cylinder(h=h+0.2, d=m3); }

module motor_pad() {
    difference() {
        cylinder(h=arm_h, r=12);
        translate([0,0,-0.1]) cylinder(h=arm_h+0.2, d=motor_shaft);   // shaft
        for (sx=[-1,1], sy=[-1,1])
            translate([sx*motor_mount/2, sy*motor_mount/2, 0]) m3hole(arm_h);
    }
}

module arm() {
    union() {
        translate([hub_r-8, -arm_w/2, 0]) cube([arm_len-(hub_r-8), arm_w, arm_h]); // deep beam
        translate([arm_len, 0, 0]) motor_pad();                                    // motor mount
        translate([hub_r-8, -(arm_w/2+2), 0]) cube([18, arm_w+4, arm_h]);          // root gusset
    }
}

module hub() {
    difference() {
        cylinder(h=arm_h, r=hub_r);
        translate([0,0,deck_floor]) cylinder(h=arm_h, r=hub_r-3);        // stack bathtub
        for (sx=[-1,1], sy=[-1,1])
            translate([sx*stack/2, sy*stack/2, 0]) m3hole(arm_h+deck_floor);
    }
}

module nose() {
    difference() {
        hull() {
            translate([hub_r-6, 0, 0]) cylinder(h=arm_h, r=8);
            translate([hub_r+nose_len, 0, 0]) cylinder(h=arm_h, r=5);    // blunt tip spreads impact
        }
        // forward-looking camera bore (smaller than tip -> stays 2-manifold)
        translate([hub_r, 0, arm_h/2]) rotate([0,90,0]) cylinder(h=nose_len+8, d=cam_d);
    }
}

module frame() {
    hub();
    for (a=[45,135,225,315]) rotate([0,0,a]) arm();   // true-X: motors land at (+-78,+-78)
    nose();                                            // nose sits between the two front arms
}

/* ---------- battery tray (separate print) ---------- */
batt_l = 78; batt_w = 36; tray_wall = 2.4; tray_lip = 6;
module battery_tray() {
    difference() {
        cube([batt_l+2*tray_wall, batt_w+2*tray_wall, tray_wall+tray_lip]);
        translate([tray_wall, tray_wall, tray_wall]) cube([batt_l, batt_w, tray_lip+1]);
        for (x=[batt_l*0.25, batt_l*0.7])
            translate([tray_wall+x, -1, tray_wall]) cube([12, batt_w+2*tray_wall+2, 3]); // strap slots
    }
}

/* ---------- render selector ---------- */
if (part == "frame") frame();
else if (part == "battery_tray") battery_tray();
else if (part == "nose") nose();
