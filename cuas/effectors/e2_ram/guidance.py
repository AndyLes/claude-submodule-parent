def velocity_cmd(err_x: float, err_y: float, v_closing: float, k_yaw=1.5, k_climb=8.0):
    """err_x,err_y у [-1..1] від центру кадру (x праворуч +, y вниз +).
    Повертає (vx forward, vy, vz_up, yaw_rate). Lead-pursuit: тримати ціль у центрі, йти вперед."""
    yaw_rate = k_yaw * err_x
    vz_up = k_climb * (-err_y)          # ціль вище (err_y<0) -> набір
    vx = v_closing                       # завжди зближення вперед
    vy = 0.0
    return vx, vy, vz_up, yaw_rate
