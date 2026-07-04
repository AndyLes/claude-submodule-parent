from cuas.sensors.eoir.tracker import pixel_to_azel


def test_center_pixel_maps_to_ptz_pose():
    az, el = pixel_to_azel(cx=960, cy=540, W=1920, H=1080, ptz_az=100.0, ptz_el=5.0, hfov=6.0, vfov=3.4)
    assert abs(az - 100.0) < 1e-6 and abs(el - 5.0) < 1e-6


def test_right_offset_increases_az():
    az, _ = pixel_to_azel(1920, 540, 1920, 1080, 100.0, 5.0, 6.0, 3.4)
    assert az > 100.0
