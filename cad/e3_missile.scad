// E3 compact tube interceptor — REAL geometry: NACA airfoil wing, fuselage sized to the
// 6S-3500 battery, ALL electronics placed, staggered folding wings, verified tube fit.
// parts: assembly | layout | wing | nose | body | tail | tray | pin | tube
// Units: mm.  (mirrors cuas/design/e3_config.py; layout x = 270 - z_from_nose)

/* fuselage — sized by battery (6S3500 43x38): internal >=45x40 -> external 52x46 */
BW=52; BH=46; corner_r=9; wall=2.4;
nose_len=120; body_len=300; tail_len=120; total=nose_len+body_len+tail_len;
motor_d=30; cam_d=10; $fn=48;
spar_d=8.2; pin_d=4.2;

/* wing — compact, real NACA ~10% airfoil, folding */
wing_ss=373; wing_rc=72; wing_tc=48; wing_tpc=0.10;
wing_z=240;                 // wing station (config x=30 -> z=270-30=240)
stagger=42;                 // L/R roots offset in Z so they DON'T collide when folded

/* small tail (fits tube) + guide */
tail_root=60; tail_tip=40; tail_th=5; tail_hspan=30; tail_vspan=30;
fin_z=nose_len+body_len+tail_len*0.5;
tube_id=115;                // >= folded envelope 112

module rrect(w,h,r){ hull() for(sx=[-1,1],sy=[-1,1]) translate([sx*(w/2-r),sy*(h/2-r)]) circle(r=r,$fn=24); }

/* ---- fuselage ---- */
module fuse_solid(){
  hull() for(i=[0:5]) let(z=i/5*nose_len, s=sqrt(max(0.05,1-pow((nose_len-z)/nose_len,2))))
    translate([0,0,z]) linear_extrude(0.6) rrect(max(3,BW*s),max(3,BH*s),max(1.5,corner_r*s));
  translate([0,0,nose_len]) linear_extrude(body_len) rrect(BW,BH,corner_r);
  hull(){ translate([0,0,nose_len+body_len]) linear_extrude(0.6) rrect(BW,BH,corner_r);
          translate([0,0,total]) linear_extrude(0.6) rrect(motor_d+8,motor_d+8,8); }
}
module wing_knuckle(sx){                       // fuselage side knuckle (axis Y), staggered per side
  zc = wing_z + sx*stagger/2;
  translate([sx*(BW/2-2),0,zc]) difference(){
    union(){ translate([0,-6,0]) rotate([-90,0,0]) cylinder(h=12,d=12,$fn=28);
             translate([-6,-6,-8]) cube([8,12,16]);
             translate([2,-9,-14]) cube([6,18,5]); }             // deploy stop
    translate([0,-8,0]) rotate([-90,0,0]) cylinder(h=16,d=pin_d,$fn=20);       // pin bore
    translate([6,-12,0]) rotate([-90,0,0]) cylinder(h=24,d=3.2,$fn=16);        // lock detent seat
  }
}
module fuselage(){
  difference(){
    union(){ fuse_solid(); wing_knuckle(1); wing_knuckle(-1); }
    translate([0,0,nose_len*0.5]) linear_extrude(body_len+nose_len*0.5+1) rrect(BW-2*wall,BH-2*wall,corner_r-1); // bay
    translate([0,0,nose_len-8]) cylinder(h=40,d=cam_d);                                                          // camera bore
    translate([-(BW/2-4),BH/2-wall-1,nose_len+20]) cube([BW-8,8,body_len-40]);                                   // top hatch
    translate([0,0,total-24]) cylinder(h=30,d=motor_d);                                                          // motor bore
  }
}

/* ---- NACA airfoil wing ---- */
function yt(x,t)=5*t*(0.2969*sqrt(x)-0.1260*x-0.3516*x*x+0.2843*pow(x,3)-0.1015*pow(x,4));
module airfoil(chord,t){
  n=20;
  polygon(concat([for(i=[0:n]) let(x=i/n)[x*chord, yt(x,t)*chord]],
                 [for(i=[n:-1:0]) let(x=i/n)[x*chord,-yt(x,t)*chord]]));
}
module wing_local(){                            // span +Z, chord +X, thick Y ; root at Z=0
  difference(){
    linear_extrude(height=wing_ss, scale=wing_tc/wing_rc) airfoil(wing_rc, wing_tpc);
    translate([wing_rc*0.3,0,-1]) cylinder(h=wing_ss+2,d=spar_d,$fn=20);      // CF spar bore (30% chord)
  }
  // root hinge fork (two knuckles straddling fuselage knuckle)
  for(sy=[-1,1]) translate([wing_rc*0.3, sy*8, -5]) rotate([0,0,0]) rotate([-90,0,0]) cylinder(h=4,d=12,$fn=24);
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

part="assembly";
if(part=="assembly") assembly();
else if(part=="layout") layout();
else if(part=="wing") wing_solid();
else if(part=="tail") { intersection(){ fuselage(); translate([-100,-100,nose_len+body_len]) cube([200,200,tail_len]); } tailfins(); motor_mount(); }
else if(part=="components") components();
else if(part=="pin") cylinder(h=20,d=pin_d-0.15,$fn=20);
