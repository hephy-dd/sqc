import random

from sqc.station import Event


class FakeStation:

    _bias_voltage = 0.
    _bias_current_compliance = 0.

    def __init__(self):
        self.bias_voltage_changed = Event()

    def __getattr__(self, name):
        return lambda *args, **kwargs: None

    def bias_set_current_compliance(self, level):
        self._bias_current_compliance = level

    def bias_set_voltage(self, level):
        self._bias_voltage = level

    def bias_read_current(self):
        return random.uniform(0, self._bias_current_compliance)

    def bias_read_voltage(self):
        return random.uniform(self._bias_voltage - 0.025, self._bias_voltage + 0.025)

    def bias_compliance_tripped(self):
        return False

    def smu_read_current(self):
        return 4.2e-12

    def smu_read_voltage(self):
        return 4.2e-3

    def elm_read_current(self):
        return 4.2e-13

    def lcr_acquire_filter_reading(self):
        return random.random(), random.random()

    def box_environment(self):
        return {}
