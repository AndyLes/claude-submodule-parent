// E3 compact tube interceptor — REAL geometry: NACA airfoil wing, fuselage sized to the
// 6S-3500 battery, ALL electronics placed, staggered folding wings, verified tube fit.
// parts: assembly | layout | wing | nose | body | tail | tray | pin | tube
// Units: mm.  (mirrors cuas/design/e3_config.py; layout x = 270 - z_from_nose)

/* fuselage — sized by battery (6S3500 43x38): internal >=45x40 -> external 52x46 */
BW=52; BH=46; corner_r=9; wall=2.4;
nose_len=120; body_len=300; tail_len=120; total=nose_len+body_len+tail_len;
motor_d=30; cam_d=8; $fn=48;
spar_d=8.2; pin_d=4.2;

/* wing — CONSTANT chord (rectangular) NACA 15% -> spar fits whole span; folding */
wing_ss=345; wing_rc=65; wing_tc=65; wing_tpc=0.15;
wing_z=240;                 // wing station
stagger=42;                 // L/R roots offset in Z so they DON'T collide when folded

/* tail — enlarged (short big-chord, fits tube) for adequate pitch volume */
tail_root=90; tail_tip=65; tail_th=5; tail_hspan=31; tail_vspan=31;
fin_z=nose_len+body_len+tail_len*0.5;
tube_id=120;                // >= folded envelope (constant chord 65 + fins)

module rrect(w,h,r){ hull() for(sx=[-1,1],sy=[-1,1]) translate([sx*(w/2-r),sy*(h/2-r)]) circle(r=r,$fn=24); }

/* ---- fuselage ---- */
// ogive skin (inset=0) or inner cavity (inset=wall). Tapers WITH the nose so the
// shell stays uniform thickness -> the tip never gets severed by a full-width cavity.
module ogive_hull(inset){
  hull() for(i=[0:6]) let(z=i/6*nose_len, s=sqrt(max(0.05,1-pow((nose_len-z)/nose_len,2))))
    translate([0,0,z]) linear_extrude(0.6) rrect(max(3,BW*s-2*inset),max(3,BH*s-2*inset),max(1,corner_r*s-inset));
}
module fuse_solid(){
  ogive_hull(0);
  translate([0,0,nose_len]) linear_extrude(body_len) rrect(BW,BH,corner_r);
  hull(){ translate([0,0,nose_len+body_len]) linear_extrude(0.6) rrect(BW,BH,corner_r);
          translate([0,0,total]) linear_extrude(0.6) rrect(motor_d+8,motor_d+8,8); }
}
/* ---- pin hinge: FORK on fuselage, solid TONGUE on wing root (mate at interface x=0, pin at x=7) ---- */
tongue_t=10; lug_t=4; gap=tongue_t+1;
module hinge_fork(){                            // extends +X into the wing; pin along Y at x=7
  difference(){
    union(){
      for(sy=[-1,1]) translate([0, sy*(gap/2+lug_t/2), -12]) cube([17, lug_t, 24]);  // two lugs (gap for tongue)
      translate([-7,-10,-12]) cube([7,20,24]);                                        // web into fuselage
      translate([13,-10,-17]) cube([4,20,5]);                                         // deploy stop (90 deg)
    }
    translate([7,-16,0]) rotate([-90,0,0]) cylinder(h=32,d=pin_d,$fn=20);   // pin bore Y (through both lugs)
    translate([13,-16,0]) rotate([-90,0,0]) cylinder(h=32,d=3.2,$fn=16);    // latch detent seat
    translate([7,-6,0]) rotate([-90,0,0]) cylinder(h=6,d=8,$fn=24);         // torsion-spring seat
    translate([-8,-3,-4]) rotate([0,90,0]) cylinder(h=8,d=1.8,$fn=12);      // spring-leg anchor
  }
}
module wing_knuckle(sx){                        // place fork on fuselage side, staggered
  translate([sx*(BW/2-2),0,wing_z+sx*stagger/2]) mirror([sx<0?1:0,0,0]) hinge_fork();
}
/* ---- COOLING: pusher works as an EXTRACTOR. Flush NACA inlets (submerged -> survive
   the tube) ram air into the bay; it washes FC->battery->ESC and exits aft louvers into
   the tail low-pressure zone; the motor breathes via boss slots + prop draft. Pre-launch
   (sealed tube, ZERO flow) the risk is SOAK -> gate the analog VTX + idle the Pi. */
inlet_w=11; inlet_l=26; inlet_z=135;
module naca_inlet(){                                                    // +X side; submerged ramp, opens AFT, breaks through wall at its aft end
  hull(){
    translate([BW/2-0.6, -inlet_w*0.12, inlet_z])          cube([2, inlet_w*0.24, 1]);   // fore: shallow, narrow (flush)
    translate([BW/2-wall-2, -inlet_w/2, inlet_z+inlet_l])  cube([wall+3, inlet_w, 1]);   // aft: full width, THROUGH the wall
  }
}
module exhaust_louvers(){ for(i=[0:2]) translate([0,0,392+i*11]) rotate([0,90,0]) cylinder(h=BW+4,d=5,$fn=16,center=true); }  // vent bay both sides at the ESC
module motor_cool_slots(){ for(a=[0:60:359]) rotate([0,0,a]) translate([motor_d/2-2,0,total-14]) rotate([0,90,0]) cylinder(h=10,d=3.5,$fn=12); }  // motor breather (prop draft pulls through)
module fuselage(){
  difference(){
    union(){ fuse_solid(); wing_knuckle(1); wing_knuckle(-1); }
    ogive_hull(wall);                                                                                           // nose cavity — CONFORMAL shell (tip stays attached; camera board sits at ogive base)
    translate([0,0,nose_len]) linear_extrude(body_len-wall) rrect(BW-2*wall,BH-2*wall,corner_r-1);              // body cavity (rear bulkhead before tail)
    translate([0,0,-2]) cylinder(h=32,d=cam_d);                                                                  // camera bore — FORWARD out the nose tip
    translate([-(BW/2-4),BH/2-wall-1,nose_len+20]) cube([BW-8,8,body_len-40]);                                   // top hatch
    translate([0,0,total-24]) cylinder(h=30,d=motor_d);                                                          // motor bore
    naca_inlet(); mirror([1,0,0]) naca_inlet();                                                                  // COOLING: flush ram-air inlets (survive the tube)
    exhaust_louvers();                                                                                           // COOLING: bay exhaust at the ESC
    motor_cool_slots();                                                                                          // COOLING: motor breather
  }
}

/* ---- NACA airfoil wing ---- */
function yt(x,t)=5*t*(0.2969*sqrt(x)-0.1260*x-0.3516*x*x+0.2843*pow(x,3)-0.1015*pow(x,4));
module airfoil(chord,t){
  n=20;
  polygon(concat([for(i=[0:n]) let(x=i/n)[x*chord, yt(x,t)*chord]],
                 [for(i=[n:-1:0]) let(x=i/n)[x*chord,-yt(x,t)*chord]]));
}
module wing_local(){                             // span +Z, chord +X, thick Y ; root TONGUE at Z<0
  spar_x = 15 + wing_rc*0.3;                      // spar at 30% chord (offset by tongue lead-in 15)
  difference(){
    union(){
      translate([15,0,0]) linear_extrude(height=wing_ss, scale=1) airfoil(wing_rc, wing_tpc);  // CONSTANT chord -> spar fits whole span
      translate([0,-tongue_t/2,-12]) cube([spar_x+8, tongue_t, 26]);   // SOLID tongue (mates fork; merged w/ airfoil root)
    }
    translate([7,-tongue_t/2-1,0]) rotate([-90,0,0]) cylinder(h=tongue_t+2,d=pin_d,$fn=20);  // pin bore Y (mates fork)
    translate([13,-tongue_t/2-1,0]) rotate([-90,0,0]) cylinder(h=tongue_t+2,d=3.2,$fn=16);   // latch lock hole
    translate([spar_x,0,-13]) cylinder(h=wing_ss+14,d=spar_d,$fn=20);                         // CF spar bore (roots in tongue)
  }
}
module wing_solid(){ wing_local(); }            // export: print orientation
module wing_R(){ translate([BW/2-6,0,wing_z+stagger/2]) rotate([0,90,0]) translate([-wing_rc/2,0,0]) wing_local(); }
module wing_L(){ mirror([1,0,0]) translate([BW/2-6,0,wing_z-stagger/2]) rotate([0,90,0]) translate([-wing_rc/2,0,0]) wing_local(); }

module panelZ(span,root,tip,th){ hull(){ translate([-th/2,0,0]) cube([th,0.1,root]); translate([-th/2,span,root*0.35]) cube([th,0.1,tip]); } }
module tailfins(){
  for(a=[90,270]) rotate([0,0,a]) translate([0,BW/2-2,fin_z-tail_root/2]) panelZ(tail_hspan,tail_root,tail_tip,tail_th);
  translate([0,BH/2-2,fin_z-tail_root/2]) panelZ(tail_vspan,tail_root,tail_tip,tail_th);
  translate([0,-(BH/2-2),fin_z-tail_root/2]) mirror([0,1,0]) panelZ(tail_vspan,tail_root,tail_tip,tail_th); // ventral guide
}
module motor_mount(){
  translate([0,0,total-wall]) difference(){
    cylinder(h=wall+4,d=motor_d+8); translate([0,0,-0.1]) cylinder(h=wall+5,d=motor_d-6);
    for(a=[0:90:359]) rotate([0,0,a]) translate([8,0,-0.1]) cylinder(h=wall+5,d=3.2);
  }
}

/* ---- DEPLOY LATCH: spring detent plunger, auto-locks the wing at 90 deg ----
   Wing swings out -> its edge cams the chamfered nose back against a small
   compression spring (bought, ~D3x10) -> at 90 deg the wing lock-hole aligns
   and the spring snaps the plunger in -> LOCKED. Press the tab to retract & fold. */
latch_d=3.0; latch_L=16;
module deploy_latch(){
  union(){
    cylinder(h=2.5, d1=latch_d-1.2, d2=latch_d, $fn=24);          // chamfered nose (cams over wing)
    translate([0,0,2.5]) cylinder(h=latch_L-2.5, d=latch_d, $fn=24);
    translate([0,0,latch_L]) cylinder(h=2, d=latch_d+2.2, $fn=24);   // spring shoulder
    translate([0,0,latch_L+2]) cylinder(h=2.5, d=latch_d+4.5, $fn=24); // release tab (press to unlock)
  }
}

/* ---- component placement blocks (real sizes; z = 270 - config_x) ---- */
COMPS=[["cam",25,24,9,252],["foxeer",19,19,20,248],["inert",42,40,34,220],["pi",65,30,6,205],
       ["fc",40,35,12,120],["rx",15,12,4,95],["batt",130,43,38,45],["esc",50,25,12,-110],
       ["servo",40,40,29,-200],["motor",28,28,30,-265]];
module components(){
  for(c=COMPS){ L=c[1]; W=c[2]; H=c[3]; z=270-c[4];
    color(c[0]=="batt"?[0.9,0.5,0.1]:[0.2,0.7,0.3])
      translate([-W/2,-H/2,z-L/2]) cube([W,H,L]); }
}

module assembly(){ fuselage(); wing_R(); wing_L(); tailfins(); motor_mount(); }
module layout(){ difference(){ fuselage(); translate([0,0,-1]) cube([100,100,total+2]); } components(); wing_R(); wing_L(); tailfins(); }
// FOLDED (stowed for the tube): wings sweep back about the vertical pin to span AFT (+Z),
// chord transverse (=65), lying over the fuselage; staggered + one flipped so they nest.
module folded(){
  fuselage(); tailfins(); motor_mount();
  translate([-wing_rc/2-8, 0, wing_z+stagger/2]) wing_local();                  // spans aft, thickness up
  translate([-wing_rc/2-8, 0, wing_z-stagger/2]) mirror([0,1,0]) wing_local();  // spans aft, thickness down (nests)
}

/* ---- SECTION SPLIT for printing: 540mm > any bed -> 3x 180mm sections, glued via
   INTEGRAL spigots (no extra parts). Fwd section's aft face grows a ring that inserts
   into the next section's open cavity; smear cyano, slide, done. ---- */
sec1=180; sec2=360; spig_len=18; spig_gap=0.35; spig_w=2.2;
module spigot(zc){                       // ring extruded AFT from cut plane, OD < cavity ID
  translate([0,0,zc]) linear_extrude(spig_len)
    difference(){ rrect(BW-2*wall-2*spig_gap, BH-2*wall-2*spig_gap, max(1,corner_r-1));
                  rrect(BW-2*wall-2*spig_gap-2*spig_w, BH-2*wall-2*spig_gap-2*spig_w, max(0.5,corner_r-1-spig_w)); }
}
module section(z0,z1){ intersection(){ fuselage(); translate([-100,-100,z0]) cube([200,200,z1-z0]); } }

/* ---- slide-out equipment tray (enters via top hatch): plate + rails + battery-strap slots ---- */
module equipment_tray(){
  tw=BW-2*wall-3; tl=body_len-70; th=2;
  difference(){
    union(){ cube([tw,tl,th]); for(sx=[0,tw-3]) translate([sx,0,0]) cube([3,tl,6]); }   // base + side rails
    for(zc=[40,tl-60]) translate([tw/2-9,zc,-0.1]) cube([18,3,th+0.2]);                  // strap slots
  }
}
/* ---- control surface (elevator/rudder): flat hinged trapezoid, print 2-3 ---- */
module control_surface(){ linear_extrude(3) polygon([[0,0],[38,0],[28,tail_hspan],[0,tail_hspan]]); }

part="assembly";
if(part=="assembly") assembly();
else if(part=="folded") folded();
else if(part=="layout") layout();
else if(part=="wing") wing_solid();
else if(part=="nose") { section(0,sec1); spigot(sec1); }
else if(part=="body") { section(sec1,sec2); spigot(sec2); }
else if(part=="tail") { section(sec2,total); tailfins(); motor_mount(); }
else if(part=="tray") equipment_tray();
else if(part=="control_surface") control_surface();
else if(part=="components") components();
else if(part=="pin") cylinder(h=20,d=pin_d-0.15,$fn=20);
else if(part=="latch") deploy_latch();
// ---- TEST COUPONS (print these first to validate the fold mechanism) ----
else if(part=="hinge_fuse"){ wing_knuckle(1); translate([BW/2-3,-16,wing_z+stagger/2-28]) cube([6,32,56]); }  // fuselage knuckle + backing
else if(part=="hinge_wing") intersection(){ wing_local(); translate([-60,-60,-20]) cube([160,120,90]); }        // wing root TONGUE + short span (spar bore + pin + lock hole)
