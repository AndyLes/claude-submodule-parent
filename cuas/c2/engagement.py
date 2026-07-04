class Engagement:
    """Автомат одного заручення. Оператор дає єдину дію: OK (пуск) або ABORT.
    Тримається окремо від server.py, щоб бути тестованим без MQTT-брокера."""

    def __init__(self, solution):
        self.sol = solution
        self.state = "AWAIT_OK"
        self._cmd = None

    def operator_ok(self):
        if self.state == "AWAIT_OK":
            self.state = "LAUNCHED"
            self._cmd = {"type": "LAUNCH", **self.sol}

    def operator_abort(self):
        self.state = "ABORTED"
        self._cmd = {"type": "ABORT"}

    def command(self):
        return self._cmd
