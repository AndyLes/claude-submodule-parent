"""Бортовий цикл E2-авто-тарана: камера -> YOLO -> MAVLink offboard velocity.
Важкі деп (pymavlink, ultralytics) — лениво, лише коли ефектор реально летить."""
import time

from cuas.effectors.e2_ram.guidance import velocity_cmd


def run(conn="udp:127.0.0.1:14550", model="uav_yolo.pt", cam=0, v_closing=25.0):
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
        cx, cy = map(float, b.xywh[0][:2])
        ex = (cx - W / 2) / (W / 2)
        ey = (cy - H / 2) / (H / 2)
        vx, vy, vz_up, yaw = velocity_cmd(ex, ey, v_closing)
        m.mav.set_position_target_local_ned_send(
            0, m.target_system, m.target_component, mavutil.mavlink.MAV_FRAME_BODY_NED,
            0b0000011111000111, 0, 0, 0, vx, vy, -vz_up, 0, 0, 0, 0, yaw)  # NED: down +, тож up = -vz
        time.sleep(0.05)
