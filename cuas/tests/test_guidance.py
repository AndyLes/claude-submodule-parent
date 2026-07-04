from cuas.effectors.e2_ram.guidance import velocity_cmd


def test_target_right_commands_right_yawrate():
    vx, vy, vz, yaw = velocity_cmd(err_x=0.5, err_y=0.0, v_closing=25.0)
    assert yaw > 0 and vx > 0


def test_target_high_commands_climb():
    _, _, vz, _ = velocity_cmd(err_x=0.0, err_y=-0.5, v_closing=25.0)  # ціль вище (y менший)
    assert vz > 0  # у нашій конвенції vz_up додатнє = набір
