// E3 folding-wing pusher interceptor — ASSEMBLY-CORRECT rebuild.
// Real mating features: wing pin-hinge (fork+knuckle+pin) with CF-spar bore and a
// deploy LOCK (drop-pin); section spigots; hatch wider than tray. Control is on the
// TAIL (elevator+rudder) so the FOLDING wing needs no wires across the fold.
// Render: openscad -D 'part="assembly"' -o out/e3_assembly.stl cad/e3_missile.scad
// parts: nose | body | tail | tray | wing | pin | lockpin | assembly

/* ---- fuselage ---- */
bw=46; bh=40; corner_r=8; wall=2.4;
nose_len=120; body_len=300; tail_len=120; motor_d=30; cam_d=6; $fn=40;
spar_d=8.2;            // CF spar bore
pin_d=4.2;             // hinge pin (steel)
lock_d=3.2;            // deploy lock pin
spig=10;               // section spigot length

// folding wing (lift only; control on tail)
wing_semispan=230; wing_root_c=130; wing_tip_c=80; wing_th=12; wing_dih=4;
// conventional tail, sized to fit the tube (semi-span<= (tube-body)/2)
tail_hspan=42; tail_vspan=40; tail_root=70; tail_tip=45; tail_th=5;

total_len=nose_len+body_len+tail_len;
wing_z=nose_len+body_len*0.45;
fin_z=nose_len+body_len+tail_len*0.5;
kn_h=10;               // knuckle height (along Y = fold axis)

module rrect(w,h,r){ hull() for(sx=[-1,1],sy=[-1,1]) translate([sx*(w/2-r),sy*(h/2-r)]) circle(r=r,$fn=24); }

module fuse_solid(){
  hull() for(i=[0:5]) let(z=i/5*nose_len, s=sqrt(max(0.05,1-pow((nose_len-z)/nose_len,2))))
    translate([0,0,z]) linear_extrude(0.6) rrect(max(3,bw*s),max(3,bh*s),max(1.5,corner_r*s));
  translate([0,0,nose_len]) linear_extrude(body_len) rrect(bw,bh,corner_r);
  hull(){ translate([0,0,nose_len+body_len]) linear_extrude(0.6) rrect(bw,bh,corner_r);
          translate([0,0,total_len]) linear_extrude(0.6) rrect(motor_d+8,motor_d+8,8); }
}

// central knuckle on fuselage side at wing root (axis Y); wing fork straddles it
module fuse_knuckle(side){
  translate([side*(bw/2-2),0,wing_z]){
    difference(){
      union(){
        translate([0,-kn_h/2,0]) rotate([-90,0,0]) cylinder(h=kn_h,d=12,$fn=28);
        translate([-6,-kn_h/2,-8]) cube([8,kn_h,16]);                 // web into fuselage
        translate([2,-9,-14]) cube([6,18,5]);                         // deploy STOP (wing rests at 90 deg)
      }
      translate([0,-kn_h/2-1,0]) rotate([-90,0,0]) cylinder(h=kn_h+2,d=pin_d,$fn=20);  // pin bore Y
      translate([6,-12,0]) rotate([-90,0,0]) cylinder(h=24,d=lock_d,$fn=16);           // LOCK-pin hole (deployed)
    }
  }
}

module fuselage(){
  difference(){
    union(){ fuse_solid(); fuse_knuckle(1); fuse_knuckle(-1); }
    translate([0,0,nose_len*0.5]) linear_extrude(body_len+nose_len*0.5+1) rrect(bw-2*wall,bh-2*wall,corner_r-1); // bay
    translate([0,0,nose_len-8]) cylinder(h=40,d=cam_d);                                                          // camera bore
    translate([-(bw/2-3),bh/2-wall-1,nose_len+30]) cube([bw-6,8,body_len-70]);                                   // TOP HATCH (bw-6=40 > tray 33)
    translate([0,0,total_len-24]) cylinder(h=30,d=motor_d);                                                      // motor bore
    // section spigot SOCKETS (recess so next section's spigot plugs in)
    translate([0,0,nose_len-spig]) linear_extrude(spig+0.2) rrect(bw-2*wall+1.2,bh-2*wall+1.2,corner_r-1);
    translate([0,0,nose_len+body_len-spig]) linear_extrude(spig+0.2) rrect(bw-2*wall+1.2,bh-2*wall+1.2,corner_r-1);
  }
}

// wing extends +X (span X, chord Z, thickness Y); lift only
module wing_panel(){
  hull(){ translate([0,-wing_th/2,0]) cube([0.1,wing_th,wing_root_c]);
          translate([wing_semispan,-wing_th/2,wing_root_c*0.3]) cube([0.1,wing_th,wing_tip_c]); }
}
module wing_solid(){
  difference(){
    union(){
      wing_panel();
      // root FORK: two knuckles straddling the fuselage knuckle
      for(sy=[-1,1]) translate([-8,sy*(kn_h/2+2.5)-2.5,wing_root_c/2]) rotate([-90,0,0]) cylinder(h=5,d=12,$fn=28);
      translate([-10,-kn_h/2-5,wing_root_c/2-6]) cube([12,kn_h+10,12]);     // fork web
    }
    translate([-8,-20,wing_root_c/2]) rotate([-90,0,0]) cylinder(h=40,d=pin_d,$fn=20);   // pin bore Y
    translate([-2,-20,wing_root_c/2]) rotate([-90,0,0]) cylinder(h=40,d=lock_d,$fn=16);  // lock hole (aligns deployed)
    translate([10,-wing_th/2-1,wing_root_c/2]) rotate([0,90,0]) cylinder(h=wing_semispan-20,d=spar_d,$fn=20);  // CF spar bore
  }
}
// placed on the airframe (deployed): +X and -X, with dihedral
module wings(){
  translate([bw/2-8,0,0]) rotate([wing_dih,0,0]) translate([0,0,wing_z-wing_root_c/2]) wing_solid();
  mirror([1,0,0]) translate([bw/2-8,0,0]) rotate([wing_dih,0,0]) translate([0,0,wing_z-wing_root_c/2]) wing_solid();
}

module panelZ(span,root,tip,th){ hull(){ translate([-th/2,0,0]) cube([th,0.1,root]); translate([-th/2,span,root*0.35]) cube([th,0.1,tip]); } }
module tail(){   // conventional, small (fits tube); +ventral guide fin -> 4-wall guide in square tube
  for(a=[90,270]) rotate([0,0,a]) translate([0,bw/2-2,fin_z-tail_root/2]) panelZ(tail_hspan,tail_root,tail_tip,tail_th); // horiz stab
  translate([0,bh/2-2,fin_z-tail_root/2]) panelZ(tail_vspan,tail_root,tail_tip,tail_th);                                 // vert fin (rudder)
  translate([0,-(bh/2-2),fin_z-tail_root/2]) mirror([0,1,0]) panelZ(tail_vspan*0.7,tail_root,tail_tip,tail_th);          // ventral guide fin
}

module motor_mount(){
  translate([0,0,total_len-wall]) difference(){
    cylinder(h=wall+4,d=motor_d+8);
    translate([0,0,-0.1]) cylinder(h=wall+5,d=motor_d-6);
    for(a=[0:90:359]) rotate([0,0,a]) translate([8,0,-0.1]) cylinder(h=wall+5,d=3.2);
  }
}

// section spigot (added to the FORWARD face of body/tail to plug the socket behind)
module spigot_ring(){ linear_extrude(spig) difference(){ rrect(bw-2*wall,bh-2*wall,corner_r-1); rrect(bw-2*wall-4,bh-2*wall-4,corner_r-2); } }

module tray(){
  tw=bw-2*wall-8; base=2.5; tl=body_len-60;                 // tw=33.2 < hatch 40 -> fits
  difference(){
    union(){ translate([-tw/2,0,0]) cube([tw,base,tl]);
      translate([-15,base,30]) tbay(30,30,6); translate([-14,base,80]) tbay(28,40,5); translate([-15,base,150]) tbay(30,66,6); }
    for(z=[tl-70,tl-20]) translate([-tw/2-1,-1,z]) cube([tw+2,base+2,4]);
  }
}
module tbay(w,l,h){ difference(){ cube([w,h,l]); translate([2,-1,2]) cube([w-4,h+2,l-4]); } }
module bay(w,l,h){ tbay(w,l,h); }

module assembly(){ fuselage(); wings(); tail(); motor_mount(); }

/* selector */
part="assembly";
if(part=="assembly") assembly();
else if(part=="nose") intersection(){ fuselage(); translate([-100,-100,0]) cube([200,200,nose_len]); }
else if(part=="body"){ intersection(){ fuselage(); translate([-100,-100,nose_len]) cube([200,200,body_len]); } translate([0,0,nose_len-spig]) spigot_ring(); }
else if(part=="tail"){ intersection(){ fuselage(); translate([-100,-100,nose_len+body_len]) cube([200,200,tail_len]); } tail(); motor_mount(); translate([0,0,nose_len+body_len-spig]) spigot_ring(); }
else if(part=="tray") tray();
else if(part=="wing") wing_solid();
else if(part=="pin") cylinder(h=kn_h+9,d=pin_d-0.15,$fn=20);
else if(part=="lockpin") cylinder(h=22,d=lock_d-0.15,$fn=16);
