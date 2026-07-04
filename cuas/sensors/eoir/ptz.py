class PTZ:
    """ONVIF-обгортка PTZ-камери (заповнити creds/URL під конкретну камеру).
    hfov/vfov — поле зору поточного зуму (град)."""

    hfov = 6.0
    vfov = 3.4
    az = 0.0
    el = 0.0

    def __init__(self, url="rtsp://CAM/stream"):
        self._url = url

    def stream_url(self):
        return self._url

    def slew_to(self, az_deg):
        self.az = az_deg  # TODO: ONVIF AbsoluteMove

    def center_on(self, cx, cy):
        pass  # TODO: ONVIF ContinuousMove пропорційно похибці центру кадру
