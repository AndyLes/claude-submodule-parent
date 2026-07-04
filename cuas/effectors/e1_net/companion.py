"""Бортовий цикл E1-сітка-дрона: зближення (повільніше за E2) -> скид сітки на
дистанції -> RTL (повернення, багаторазовість). Важкі деп — лениво."""
import math
import time

from cuas.effectors.e2_ram.guidance import velocity_cmd
from cuas.effectors.e1_net.mission import should_fire_net, net_servo_pwm


def bbox_range_m(bbox_h_px, H, target_size_m=0.35, vfov_deg=48.0):
    ang = (bbox_h_px / H) * math.radians(vfov_deg)
    return target_size_m / max(math.tan(ang / 2) * 2, 1e-3)


def run(conn="udp:127.0.0.1:14550", model="uav_yolo.pt", cam=0):
    from pymavlink import mavutil
    from ultralytics import YOLO

    m = mavutil.mavlink_connection(conn)
    m.wait_heartbeat()
    net = YOLO(model)
    for r in net.track(source=cam, stream=True, persist=True, verbose=False):
        if not r.boxes or len(r.boxes) == 0:
            continue
        b = r.boxes[int(r.boxes.conf.argmax())]
        H, W = r.orig_shape
        cx, cy, bw, bh = map(float, b.xywh[0])
        ex = (cx - W / 2) / (W / 2)
        ey = (cy - H / 2) / (H / 2)
        rng = bbox_range_m(bh, H)
        if should_fire_net(ex, ey, rng):
            m.mav.command_long_send(
                m.target_system, m.target_component,
                mavutil.mavlink.MAV_CMD_DO_SET_SERVO, 0, 9, net_servo_pwm(True), 0, 0, 0, 0, 0)
            time.sleep(0.5)
            m.set_mode("RTL")
            return
        vx, vy, vz_up, yaw = velocity_cmd(ex, ey, v_closing=12.0)  # повільніший, акуратний підхід
        m.mav.set_position_target_local_ned_send(
            0, m.target_system, m.target_component, mavutil.mavlink.MAV_FRAME_BODY_NED,
            0b0000011111000111, 0, 0, 0, vx, vy, -vz_up, 0, 0, 0, 0, yaw)
        time.sleep(0.05)
