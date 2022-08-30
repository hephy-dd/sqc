import logging
import time
from typing import Dict, Callable

import numpy as np
from scipy import stats

from comet.parameter import Parameter
from comet.functions import LinearRange

from .core.functions import steady_state_check
from .core.formatting import format_metric
from .core.measurement import register_measurement, Measurement

__all__ = [
    "ComplianceError",
    "IVMeasurement",
    "CVMeasurement",
    "StripscanMeasurement",
    "IStripMeasurement",
    "RPolyMeasurement",
    "IDielMeasurement",
    "CacMeasurement",
    "CIntMeasurement",
    "RIntMeasurement",
    "IDarkMeasurement"
]

logger = logging.getLogger(__name__)


def median(callback: Callable, n_samples: int) -> float:
    """Return median of n_samples, reading data from function."""
    assert n_samples > 0, "n_sampels must be greater then zero"
    values = [callback() for _ in range(n_samples)]
    return np.median(values)


class ComplianceError(Exception):

    ...


class AnalysisError(Exception):

    ...


class BaseMeasurement(Measurement):

    hv_channels = Parameter([], type=list)
    lv_channels = Parameter([], type=list)

    def apply_switching(self):
        station = self.context.station
        station.hv_switch_apply(self.hv_channels)
        station.lv_switch_apply(self.lv_channels)

    def insert_data(self, values: dict, sortkey: str) -> None:
        snapshot = self.context.station.box_environment()
        chuck_temperature = snapshot.get("pt100_1", float("nan"))
        box_humidity = snapshot.get("box_humidity", float("nan"))
        data = {
            "timestamp": time.time(),
            "temperature": chuck_temperature,
            "humidity": box_humidity,
        }
        data.update(values)
        super().insert_data(data, sortkey)

    def check_valid_range(self, minimum: float, maximum: float, value: float, unit: str):
        if minimum and value < minimum:
            raise AnalysisError(f"Value out of bounds: {format_metric(value, unit)}, [{format_metric(minimum, unit)}, {format_metric(maximum, unit)}]")
        if maximum and value > maximum:
            raise AnalysisError(f"Value out of bounds: {format_metric(value, unit)}, [{format_metric(minimum, unit)}, {format_metric(maximum, unit)}]")


@register_measurement("iv")
class IVMeasurement(BaseMeasurement):

    voltage_begin = Parameter(default=0, unit="V", minimum=-1000, maximum=0)
    voltage_end = Parameter(unit="V", minimum=-1000, maximum=0)
    voltage_step = Parameter(default=1, unit="V", minimum=-100, maximum=+100)
    waiting_time = Parameter(default=1.0, unit="s")
    compliance = Parameter(unit="A", minimum=0)

    def initialize(self):
        station = self.context.station

        station.smu_recover_voltage()
        station.smu_set_output(False)

        station.bias_recover_voltage()
        station.bias_set_current_compliance(self.compliance)
        station.bias_set_output(True)

        self.apply_switching()

        if self.voltage_begin:

            def before_step(*args):
                self.handle_abort()

            station.bias_ramp_voltage(self.voltage_begin, before_step=before_step)

        station.bias_set_voltage_range(abs(self.voltage_end))

    def acquire(self):
        voltge_threshold = 0.25

        station = self.context.station

        voltage_range = LinearRange(self.voltage_begin, self.voltage_end, self.voltage_step)

        steps = len(voltage_range)
        for step, voltage in enumerate(voltage_range):
            self.handle_abort()

            self.set_progress(0, steps, step)
            self.set_message(f"Performing IV @{voltage} V")

            # Set voltage
            station.bias_set_voltage(voltage)

            # Wait
            time.sleep(self.waiting_time)

            # Measure current and voltage
            bias_smu_i = station.bias_read_current()
            bias_smu_v = station.bias_read_voltage()

            if abs(voltage - bias_smu_v) > voltge_threshold:
                logger.warning("Bias SMU voltage out of expected range: %g V", bias_smu_v)

            self.insert_data({
                "index": step,
                "bias_voltage": voltage,
                "bias_smu_v": bias_smu_v,
                "bias_smu_i": bias_smu_i,
            }, sortkey="index")

            if station.bias_compliance_tripped():
                raise ComplianceError("Bias SMU compliance tripped.")

            if self.compliance <= abs(bias_smu_i):
                raise ComplianceError("Bias SMU compliance tripped (software).")


@register_measurement("cv")
class CVMeasurement(BaseMeasurement):

    voltage_begin = Parameter(default=0, unit="V")
    voltage_end = Parameter(unit="V", minimum=-1000, maximum=0)
    voltage_step = Parameter(default=1, unit="V", minimum=-100, maximum=100)
    waiting_time = Parameter(default=1, unit="s", minimum=0, maximum=60)
    compliance = Parameter(unit="A", minimum=0)
    lcr_amplitude = Parameter(default=1, unit="V", minimum=0, maximum=10)
    lcr_frequency = Parameter(default="1 kHz", unit="Hz", minimum=0)
    open_correction = Parameter(default=False, type=bool)

    def initialize(self):
        station = self.context.station

        station.smu_recover_voltage()
        station.smu_set_output(False)

        station.bias_recover_voltage()
        station.bias_set_current_compliance(self.compliance)
        station.bias_set_output(True)

        self.handle_abort()

        # TODO
        if self.open_correction:
            self.set_message("Perform open correction...")
            self.set_progress(0, 0, 1)
            station.hv_switch_apply([])
            station.safe_discharge()
            self.apply_switching()
            station.lcr_perform_open_correction()
            station.lcr_enable_open_correction(True)
            self.set_message("")
        else:
            self.apply_switching()
            station.lcr_enable_open_correction(False)

        station.lcr_set_amplitude(self.lcr_amplitude)
        station.lcr_set_frequency(self.lcr_frequency)

        if self.voltage_begin:

            def before_step(*args):
                self.handle_abort()

            station.bias_ramp_voltage(self.voltage_begin, before_step=before_step)

        station.bias_set_voltage_range(abs(self.voltage_end))

    def acquire(self):
        voltge_threshold = 0.25

        station = self.context.station

        voltage_range = LinearRange(self.voltage_begin, self.voltage_end, self.voltage_step)

        steps = len(voltage_range)
        for step, voltage in enumerate(voltage_range):
            self.handle_abort()

            self.set_progress(0, steps, step)
            self.set_message(f"Performing CV @{voltage} V")

            # Set voltage
            station.bias_set_voltage(voltage)

            # Wait
            time.sleep(self.waiting_time)

            # Measure capacity, current and voltage
            lcr_cp, lcr_rp = station.lcr_acquire_filter_reading()
            bias_smu_i = station.bias_read_current()
            bias_smu_v = station.bias_read_voltage()

            if abs(voltage - bias_smu_v) > voltge_threshold:
                logger.warning("Bias SMU voltage out of expected range: %g V", bias_smu_v)

            self.insert_data({
                "index": step,
                "bias_voltage": voltage,
                "bias_smu_v": bias_smu_v,
                "bias_smu_i": bias_smu_i,
                "lcr_cp": lcr_cp,
                "lcr_rp": lcr_rp,
            }, sortkey="index")

            if station.bias_compliance_tripped():
                raise ComplianceError("Bias SMU compliance tripped.")

            if self.compliance <= abs(bias_smu_i):
                raise ComplianceError("Bias SMU compliance tripped (software).")

    def finalize(self) -> None:
        station = self.context.station
        station.bias_recover_voltage()
        station.safe_discharge()


@register_measurement("stripscan")
class StripscanMeasurement(BaseMeasurement):

    bias_voltage = Parameter(unit="V", minimum=-1000, maximum=0)
    bias_compliance = Parameter(unit="A", minimum=0)
    waiting_time = Parameter(default=1, unit="s", minimum=0, maximum=60)

    def check_bias_compliance(self):
        station = self.context.station

        if station.bias_compliance_tripped():
            raise ComplianceError("Bias SMU compliance tripped.")

    def before_strip(self) -> None:
        self.check_bias_compliance()

    def initialize(self) -> None:
        station = self.context.station

        station.smu_recover_voltage()
        station.smu_set_output(False)

        station.bias_recover_voltage()
        station.bias_set_output(True)
        station.bias_set_current_compliance(self.bias_compliance)

        station.needles_down()

        self.apply_switching()

        def before_step(*args):
            self.handle_abort()

        def after_step(*args):
            self.check_bias_compliance()

        station.bias_ramp_voltage(
            voltage_end=self.bias_voltage,
            waiting_time=self.waiting_time,
            before_step=before_step,
            after_step=after_step
        )


class SingleStripMeasurement(BaseMeasurement):

    def insert_strip_data(self, values: dict) -> None:
        strip = self.context.current_strip
        strip_index = self.context.padfile.index(strip)
        data = {
            "strip": strip,
            "strip_index": strip_index
        }
        data.update(values)
        super().insert_data(data, sortkey="strip_index")

    def initialize(self):
        self.apply_switching()


@register_measurement("istrip")
class IStripMeasurement(SingleStripMeasurement):

    istrip_i_minimum = Parameter(default=0, unit="A", minimum=0)
    istrip_i_maximum = Parameter(default=0, unit="A", minimum=0)
    n_samples = Parameter(default=5, type=int, minimum=1)

    def initialize(self):
        super().initialize()
        station = self.context.station

        station.elm_set_zero_check(False)

    def acquire(self):
        station = self.context.station

        logger.info("Steady state check...")
        r = steady_state_check(station.elm_read_current, n_samples=2, rsq=0.5, max_slope=1e-6, waiting_time=0)

        if not r:
            logger.error("Steady state check failed, skipping Istrip for strip %s", self.context.current_strip)
            return

        logger.info("Acquire data...")
        istrip_i = median(station.elm_read_current, n_samples=self.n_samples)

        self.insert_strip_data({"istrip_i": istrip_i})

        # TODO
        self.check_valid_range(self.istrip_i_minimum, self.istrip_i_maximum, abs(istrip_i), unit="A")

    def finalize(self):
        station = self.context.station
        station.elm_set_zero_check(True)

        super().finalize()


@register_measurement("rpoly")
class RPolyMeasurement(SingleStripMeasurement):
    """Note: this measurements requires an additional low-voltage switch setting
    `lv_channels_istrip` for measuring additional strip current.
    """

    lv_channels_istrip = Parameter(type=list)
    smu_compliance = Parameter(default="10 uA", unit="A", minimum=0)
    smu_voltage = Parameter(default=-5, unit="V", minimum=-24, maximum=24)
    rpoly_r_minimum = Parameter(default=0, unit="ohm", minimum=0)
    rpoly_r_maximum = Parameter(default=0, unit="ohm", minimum=0)
    n_samples = Parameter(default=5, type=int, minimum=1)

    def initialize(self):
        super().initialize()
        station = self.context.station
        station.smu_recover_voltage()
        station.smu_set_current_compliance(self.smu_compliance)
        station.smu_set_output(True)
        station.smu_set_voltage_range(abs(self.smu_voltage))
        station.smu_set_voltage(self.smu_voltage)
        station.smu_check_errors()

    def acquire(self):
        station = self.context.station

        logger.info("Steady state check...")
        r = steady_state_check(station.smu_read_current, n_samples=2, rsq=0.5, max_slope=1e-6, waiting_time=0)

        if not r:
            logger.error("Steady state check failed, skipping Rpoly for strip %s", self.context.current_strip)
            return

        if station.smu_compliance_tripped():
            logger.error("SMU2 compliance tripped.")

        logger.info("Acquire readings...")
        rpoly_i = median(station.smu_read_current, n_samples=self.n_samples)
        rpoly_u = station.smu_read_voltage()

        # Ramp down SMU
        station.smu_recover_voltage()
        station.smu_set_output(False)

        # Force LV switching for Istrip
        station.lv_switch_apply(self.lv_channels_istrip)  # TODO

        station.elm_set_zero_check(False)

        logger.info("Steady state check...")
        r = steady_state_check(station.elm_read_current, n_samples=2, rsq=0.5, max_slope=1e-6, waiting_time=0)

        if not r:
            logger.error("Steady state check failed, skipping Istrip for strip %s", self.context.current_strip)
            return

        logger.info("Acquire readings...")
        istrip_i = median(station.elm_read_current, n_samples=self.n_samples)

        # Calculate Rpoly_r

        rpoly_r = rpoly_u / (rpoly_i - istrip_i)

        logger.info("Calculated rpoly_r: %s", format_metric(rpoly_r, "Ohm"))

        self.insert_strip_data({
            "rpoly_r": rpoly_r,
            "rpoly_i": rpoly_i,
            "rpoly_istrip_i": istrip_i,
            "rpoly_u": rpoly_u
        })

        self.check_valid_range(self.rpoly_r_minimum, self.rpoly_r_maximum, abs(rpoly_r), unit="Ohm")

    def finalize(self):
        station = self.context.station

        station.elm_set_zero_check(True)

        station.smu_recover_voltage()
        station.smu_set_output(False)

        super().finalize()


@register_measurement("idiel")
class IDielMeasurement(SingleStripMeasurement):

    smu_compliance = Parameter(default="1 uA", unit="A", minimum=0)
    smu_voltage = Parameter(default=10, unit="V", minimum=-24, maximum=24)
    idiel_i_minimum = Parameter(default=0, unit="A", minimum=0)
    idiel_i_maximum = Parameter(default=0, unit="A", minimum=0)
    n_samples = Parameter(default=5, type=int, minimum=1)

    def initialize(self):
        super().initialize()
        station = self.context.station

        station.smu_recover_voltage()
        station.smu_set_current_compliance(self.smu_compliance)
        station.smu_set_voltage_range(abs(self.smu_voltage))
        station.smu_set_output(True)
        station.smu_set_voltage(self.smu_voltage)

    def acquire(self):
        station = self.context.station

        logger.info("Steady state check...")
        r = steady_state_check(station.smu_read_current, n_samples=2, rsq=0.3, max_slope=1e-6, waiting_time=0)

        if not r:
            logger.error("Steady state check failed, skipping Idiel for strip %s", self.context.current_strip)
            return

        logger.info("Acquire readings...")
        idiel_i = median(station.smu_read_current, n_samples=self.n_samples)

        self.insert_strip_data({"idiel_i": idiel_i})

        self.check_valid_range(self.idiel_i_minimum, self.idiel_i_maximum, abs(idiel_i), unit="A")

    def finalize(self):
        station = self.context.station
        station.smu_recover_voltage()
        station.smu_set_output(False)

        super().finalize()


@register_measurement("cac")
class CacMeasurement(SingleStripMeasurement):

    lcr_amplitude = Parameter(default=1, unit="V", minimum=0, maximum=10)
    lcr_frequency = Parameter(default="1 kHz", unit="Hz")
    cac_cp_minimum = Parameter(default=0, unit="F", minimum=0)
    cac_cp_maximum = Parameter(default=0, unit="F", minimum=0)
    n_samples = Parameter(default=5, type=int, minimum=1)

    def before_sequence(self) -> None:
        n_samples: int = 50
        # TODO
        self.set_message(f"Acquire open correction for {self.name}")
        station = self.context.station
        self.apply_switching()
        # station.lcr_enable_open_correction(False)
        # TODO
        station.lcr_perform_open_correction()
        station.lcr_enable_open_correction(True)
        #
        station.lcr_set_amplitude(self.lcr_amplitude)
        station.lcr_set_frequency(self.lcr_frequency)
        readings = []
        self.set_progress(0, n_samples, 0)
        for i in range(n_samples):
            readings.append(station.lcr_acquire_reading())
            self.set_progress(0, n_samples, i + 1)
        cp_corr = np.median([reading[0] for reading in readings])
        logger.info("Cac correction (median): %s F", cp_corr)
        self.context.set_open_correction(self.namespace, self.type, self.name, "cp", cp_corr)
        self.set_message("")

    def initialize(self):
        super().initialize()
        station = self.context.station

        station.lcr_set_amplitude(self.lcr_amplitude)
        station.lcr_set_frequency(self.lcr_frequency)
        station.lcr_enable_open_correction(True)

    def acquire(self):
        station = self.context.station

        def apply_correction(cp_value, rp_value):
            # TODO
            cp_corr = self.context.get_open_correction(self.namespace, self.type, self.name, "cp")
            logger.info("Cac cp correction: corr=%G, value=%G, (value-corr)=%G", cp_corr, cp_value, cp_value - cp_corr)
            return cp_value - cp_corr, rp_value

        def lcr_acquire_corr_reading():
            prim, sec = station.lcr_acquire_reading()
            return apply_correction(prim, sec)

        logger.info("Steady state check...")
        r = steady_state_check(lambda: lcr_acquire_corr_reading()[0], n_samples=2, rsq=0.5, max_slope=1e-6, waiting_time=0)

        if not r:
            logger.error("Steady state check failed, skipping Cac for strip %s", self.context.current_strip)
            return

        logger.info("Acquire readings...")
        readings = [lcr_acquire_corr_reading() for _ in range(self.n_samples)]

        cac_cp = np.median([reading[0] for reading in readings])
        cac_rp = np.median([reading[1] for reading in readings])

        self.insert_strip_data({"cac_cp": cac_cp, "cac_rp": cac_rp})

        self.check_valid_range(self.cac_cp_minimum, self.cac_cp_maximum, abs(cac_cp), unit="F")

    def finalize(self):
        station = self.context.station
        station.lcr_set_frequency(1e3)

        super().finalize()


@register_measurement("cint")
class CIntMeasurement(SingleStripMeasurement):

    lcr_amplitude = Parameter(default=1, unit="V", minimum=0, maximum=10)
    lcr_frequency = Parameter(default="1 MHz", unit="Hz")
    cint_cp_minimum = Parameter(default=0, unit="F", minimum=0)
    cint_cp_maximum = Parameter(default=0, unit="F", minimum=0)
    n_samples = Parameter(default=5, type=int, minimum=1)

    def before_sequence(self) -> None:
        n_samples: int = 50
        # TODO
        self.set_message(f"Acquire open correction for {self.name}")
        station = self.context.station
        self.apply_switching()
        # TODO
        station.lcr_perform_open_correction()
        station.lcr_enable_open_correction(True)
        #
        station.lcr_set_amplitude(self.lcr_amplitude)
        station.lcr_set_frequency(self.lcr_frequency)
        readings = []
        self.set_progress(0, n_samples, 0)
        for i in range(n_samples):
            readings.append(station.lcr_acquire_reading())
            self.set_progress(0, n_samples, i + 1)
        cp_corr = np.median([reading[0] for reading in readings])
        logger.info("Cint correction (median): %s F", cp_corr)
        self.context.set_open_correction(self.namespace, self.type, self.name, "cp", cp_corr)
        self.set_message("")

    def initialize(self):
        super().initialize()
        station = self.context.station

        station.needles_up()

        station.lcr_set_amplitude(self.lcr_amplitude)
        station.lcr_set_frequency(self.lcr_frequency)
        station.lcr_enable_open_correction(True)
        time.sleep(0.2)  # TODO?

    def acquire(self):
        station = self.context.station

        def apply_correction(cp_value, rp_value):
            # TODO
            cp_corr = self.context.get_open_correction(self.namespace, self.type, self.name, "cp")
            logger.info("CInt cp correction: corr=%G, value=%G, (value-corr)=%G", cp_corr, cp_value, cp_value - cp_corr)
            return cp_value - cp_corr, rp_value

        def lcr_acquire_corr_reading():
            prim, sec = station.lcr_acquire_reading()
            return apply_correction(prim, sec)

        logger.info("Steady state check...")
        r = steady_state_check(lambda: lcr_acquire_corr_reading()[0], n_samples=2, rsq=0.3, max_slope=1e-6, waiting_time=0)

        if not r:
            logger.error("Steady state check failed, skipping Cint for strip %s", self.context.current_strip)
            return

        logger.info("Acquire readings...")
        readings = [lcr_acquire_corr_reading() for _ in range(self.n_samples)]

        cint_cp = np.median([reading[0] for reading in readings])
        cint_rp = np.median([reading[1] for reading in readings])

        self.insert_strip_data({"cint_cp": cint_cp, "cint_rp": cint_rp})

        self.check_valid_range(self.cint_cp_minimum, self.cint_cp_maximum, abs(cint_cp), unit="F")

    def finalize(self):
        station = self.context.station
        station.lcr_set_frequency(1e3)

        station.needles_down()

        super().finalize()


@register_measurement("rint")
class RIntMeasurement(SingleStripMeasurement):

    smu_voltage_begin = Parameter(default=0, unit="V", minimum=-24, maximum=+24)
    smu_voltage_end = Parameter(default=5, unit="V", minimum=-24, maximum=+24)
    smu_voltage_step = Parameter(default=1, unit="V", minimum=-24, maximum=+24)
    smu_waiting_time = Parameter(default=0, unit="s", minimum=0, maximum=60)
    smu_compliance = Parameter(default="50 uA", unit="A", minimum=0, maximum="100 uA")
    rint_r_minimum = Parameter(default=0, unit="ohm", minimum=0)
    rint_r_maximum = Parameter(default=0, unit="ohm", minimum=0)
    n_samples = Parameter(default=5, type=int, minimum=1)

    def initialize(self):
        super().initialize()
        station = self.context.station
        station.smu_recover_voltage()
        station.smu_set_current_compliance(self.smu_compliance)
        station.smu_set_output(True)
        station.smu_ramp_voltage(
            voltage_end=self.smu_voltage_begin,
            voltage_step=self.smu_voltage_step
        )
        station.smu_check_errors()

        station.elm_set_zero_check(False)

    def acquire(self):
        station = self.context.station

        logger.info("Steady state check...")
        r = steady_state_check(station.elm_read_current, n_samples=2, rsq=0.3, max_slope=1e-2, waiting_time=0)

        if not r:
            logger.error("Steady state check failed, skipping Istrip for strip %s", self.context.current_strip)
            return

        if station.smu_compliance_tripped():
            logger.error("SMU2 compliance tripped.")

        rint_u = []
        rint_i = []

        def acquire_reading(_, voltage):
            if station.smu_compliance_tripped():
                raise ComplianceError("SMU2 compliance tripped.")

            elm_i = median(station.elm_read_current, n_samples=self.n_samples)
            rint_u.append(voltage)
            rint_i.append(elm_i)

        logger.info("Acquire readings...")
        station.smu_ramp_voltage(
            voltage_end=self.smu_voltage_end,
            voltage_step=self.smu_voltage_step,
            waiting_time=self.smu_waiting_time,
            after_step=acquire_reading
        )

        # Linear regression produces 1/res
        slope, *_ = stats.linregress(rint_u, rint_i)
        rint_r = 1.0 / slope

        logger.info("Calculated rint_r: %s", format_metric(rint_r, "Ohm"))

        self.insert_strip_data({"rint_r": rint_r, "rint_u": rint_u, "rint_i": rint_i})

        self.check_valid_range(self.rint_r_minimum, self.rint_r_maximum, abs(rint_r), unit="Ohm")

    def finalize(self):
        station = self.context.station

        station.elm_set_zero_check(True)

        station.smu_recover_voltage()
        station.smu_set_output(False)

        super().finalize()


@register_measurement("idark")
class IDarkMeasurement(SingleStripMeasurement):

    idark_i_minimum = Parameter(default=0, unit="A", minimum=0)
    idark_i_maximum = Parameter(default=0, unit="A", minimum=0)
    n_samples = Parameter(default=5, type=int, minimum=1)

    def acquire(self):
        station = self.context.station

        logger.info("Steady state check...")
        r = steady_state_check(station.bias_read_current, n_samples=2, rsq=0.5, max_slope=1e-6, waiting_time=0)

        if not r:
            logger.error("Steady state check failed, skipping Istrip for strip %s", self.context.current_strip)
            return

        logger.info("Acquire readings...")
        idark_i = median(station.bias_read_current, n_samples=self.n_samples)
        idark_v = station.bias_read_voltage()

        self.insert_strip_data({"idark_i": idark_i, "idark_v": idark_v})

        self.check_valid_range(self.idark_i_minimum, self.idark_i_maximum, abs(idark_i), unit="A")
