import logging
import statistics
import time
from typing import Any, Callable, Dict, Generator, Iterable, Tuple, Optional

from comet.filters import std_mean_filter
from comet.functions import LinearRange
from comet.utils import ureg

from .controller.environ import EnvironController
from .controller.table import Table
from .core.event import Event
from .core.formatting import format_channels, format_metric, format_switch
from .core.resource import Resource, create_driver, Driver
from .core.timer import Timer
from .settings import Settings

__all__ = ["Station"]

logger = logging.getLogger(__name__)


def identify(instr) -> str:
    if hasattr(instr, "identify"):
        return instr.identify()
    return "n/a"


def iter_errors(instr) -> Generator[Any, None, None]:
    while True:
        error = instr.next_error()
        if error is None:
            break
        yield error


def wait_until(callback, timeout=60.0, interval=0.250) -> None:
    """Block until callback function return `True`."""
    t = Timer()
    while True:
        if t.delta() > timeout:
            raise TimeoutError()
        time.sleep(interval)
        if callback():
            break


class Station:

    def __init__(self) -> None:
        self._resources: Dict[str, Driver] = {}
        self.registered_resources = [
            "hv_switch",
            "lv_switch",
            "smu",
            "bias_smu",
            "lcr",
            "elm",
            "table",
            "tango"
        ]

        self.bias_voltage_changed: Event = Event()
        self.box_light_changed: Event = Event()

        self.environ: EnvironController = EnvironController()
        self.environ.start()

    def get_resource(self, name: str) -> Driver:
        self.open_resource(name)
        return self._resources[name]

    def open_resource(self, name: str) -> None:
        if name not in self._resources:
            resource = Settings().createResource(name)
            self._resources[name] = create_driver(resource.model)(resource.__enter__())
            logger.info("Opened resource: %s %s", resource.model, resource.address)

    def close_resource(self, name: str) -> None:
        resource = self.get_resource(name)
        if resource is not None:
            resource.resource.__exit__()
            logger.info("Closed resource: %s %s", resource.resource.model, resource.resource.address)
            del self._resources[name]

    def open_resources(self) -> None:
        for name in self.registered_resources:
            self.open_resource(name)

    def close_resources(self) -> None:
        for name in list(self._resources.keys()):
            self.close_resource(name)

    def clear_visa_bus(self) -> None:
        for resource in self._resources.values():
            try:
                resource.resource.clear()
            except Exception as exc:
                logger.exception(exc)
                logger.error("Failed to clear VISA bus for resource: %r", resource.resource)

    def finalize(self) -> None:
        logger.info("Finalizing measurements...")
        # Bring down active sources.
        self.safe_recover_smu()
        self.safe_recover_bias_smu()
        self.hv_switch_release()
        self.lv_switch_release()
        self.safe_discharge()
        self.close_resources()
        logger.info("Finalizing measurements... done.")

    def shutdown(self) -> None:
        self.environ.shutdown()
        self.close_resources()

    def safe_initialize(self) -> None:
        logger.info("Safe initialize SQC...")
        self.check_identities()
        self.safe_recover_box()
        self.safe_recover_smu()
        self.safe_recover_bias_smu()
        self.hv_switch_release()
        self.lv_switch_release()
        self.safe_initialize_smu()
        self.safe_initialize_bias_smu()
        self.safe_initialize_lcr()
        self.safe_initialize_elm()
        self.safe_discharge()
        self.box_validate_state()
        logger.info("Safe initialize SQC... done.")

    def check_identities(self) -> None:
        for name in self.registered_resources:
            instr = self.get_resource(name)
            if instr is None:
                raise ValueError(f"No such resource: {name!r}")
            logger.info("Identified %s: %s", name, identify(instr))

    def safe_discharge(self) -> None:
        self.safe_recover_bias_smu()
        logger.info("Discharge capacitor...")
        CapacitorDischarge(self)()
        logger.info("Discharge capacitor... done.")

    # HV Switch

    def hv_switch_release(self) -> None:
        logger.info("Release all HV switch channels.")
        hv_switch = self.get_resource("hv_switch")

        hv_switch.open_all_channels()

        closed_channels = hv_switch.closed_channels
        if closed_channels:
            raise RuntimeError(f"Failed to release HV switch channels: {closed_channels}")

    def hv_switch_apply(self, channels: Iterable[str]) -> None:
        logger.info("Apply HV switch channels: %s", format_channels(channels))
        hv_switch = self.get_resource("hv_switch")

        open_channels = set(hv_switch.closed_channels) - set(channels)
        if open_channels:  # only open removed channels
            logger.info("Open HV switch channels: %s", format_channels(open_channels))
            hv_switch.open_channels(open_channels)

        close_channels = set(channels) - set(hv_switch.closed_channels)
        if close_channels:  # only close open channels
            logger.info("Close HV switch channels: %s", format_channels(close_channels))
            hv_switch.close_channels(close_channels)

        if set(hv_switch.closed_channels) != set(channels):
            raise RuntimeError("Failed to apply HV switch channels")

    # LV Switch

    def lv_switch_release(self) -> None:
        logger.info("Release all LV switch channels.")
        lv_switch = self.get_resource("lv_switch")

        lv_switch.open_all_channels()

        closed_channels = lv_switch.closed_channels
        if closed_channels:
            raise RuntimeError(f"Failed to release LV channels: {closed_channels}")

    def lv_switch_apply(self, channels: Iterable[str]) -> None:
        logger.info("Apply LV switch channels: %s", format_channels(channels))
        lv_switch = self.get_resource("lv_switch")

        open_channels = set(lv_switch.closed_channels) - set(channels)
        if open_channels:  # only open removed channels
            logger.info("Open LV switch channels: %s", format_channels(open_channels))
            lv_switch.open_channels(open_channels)

        close_channels = set(channels) - set(lv_switch.closed_channels)
        if close_channels:  # only close open channels
            logger.info("Close LV switch channels: %s", format_channels(close_channels))
            lv_switch.close_channels(close_channels)

        if set(lv_switch.closed_channels) != set(channels):
            raise RuntimeError("Failed to apply LV switch channels")


    # Box

    def box_validate_state(self) -> None:
        logger.info("Checking box state...")
        environ = self.environ

        box_door_state = environ.get_box_door_state()
        if box_door_state:  # False = closed, true = open
            raise RuntimeError("Box door not closed.")
        logger.info("Box door closed.")

        box_light_state = environ.get_box_light_state()
        if box_light_state:
            raise RuntimeError("Box light is switched on.")
        logger.info("Box light switched off.")

        box_lux = environ.get_box_lux()
        if box_lux > 0:
            raise RuntimeError(f"Box light is present ({box_lux:} Lux).")
        logger.info("Box is dimmed.")

        data = environ.snapshot()

        chuck_temperature = data.get("pt100_1", float("nan"))
        logger.info("Chuck temperature: %s degC", chuck_temperature)

        chuck_block_temperature = data.get("pt100_2", float("nan"))
        logger.info("Chuck block temperature: %s degC", chuck_block_temperature)

        box_humidity = data.get("box_humidity", float("nan"))
        logger.info("Box box_humidity: %s rel%%", box_humidity)

        logger.info("Checking box state... done.")

    def box_environment(self) -> Dict[str, Any]:
        return self.environ.snapshot()

    def safe_recover_box(self) -> None:
        logger.info("Dimming box lights.")
        environ = self.environ
        environ.set_box_light_state(False)
        environ.set_microscope_light_state(False)
        self.box_light_changed(False)

    def box_set_light_enabled(self, state: bool) -> None:
        logger.info("Switching box and microscope lights: %s.", "ON" if state else "OFF")
        environ = self.environ
        environ.set_box_light_state(state)
        environ.set_microscope_light_state(state)
        self.box_light_changed(state)

    def box_set_test_running(self, state: bool) -> None:
        logger.info("Set box test running: %s", state)
        environ = self.environ
        environ.set_test_led_state(state)

    # SMU

    def safe_recover_smu(self) -> None:
        logger.info("Safe recover SMU...")
        smu = self.get_resource("smu")
        output = smu.output
        if output == smu.OUTPUT_ON:
            logger.info("SMU output is active...")
            function = smu.function
            if function == smu.FUNCTION_VOLTAGE:
                voltage = smu.voltage_level
                if voltage:
                    logger.info("Ramping SMU to zero...")
                    voltage_ramp = LinearRange(voltage, 0, 25)
                    for voltage in voltage_ramp:
                        smu.voltage_level = voltage
                        time.sleep(.5)
                    logger.info("Ramping SMU to zero... done.")
            elif function == smu.FUNCTION_CURRENT:
                current = smu.current_level
                if current:
                    logger.info("Ramping SMU to zero...")
                    current_ramp = LinearRange(current, 0, 2.5e-03)
                    for current in current_ramp:
                        smu.current_level = current
                        time.sleep(.5)
                    logger.info("Ramping SMU to zero... done.")
            time.sleep(1.)
            smu.output = smu.OUTPUT_OFF
        smu.function = smu.FUNCTION_VOLTAGE
        smu.voltage_level = 0
        logger.info("Safe recover SMU... done.")

    def safe_initialize_smu(self) -> None:
        logger.info("Safe initialize SMU...")
        smu = self.get_resource("smu")
        logger.info("Reset SMU...")
        smu.reset()
        smu.clear()
        logger.info("Configure SMU...")
        smu.route_terminal = smu.ROUTE_TERMINAL_REAR
        smu.beeper = smu.BEEPER_OFF
        for error in iter_errors(smu):
            raise RuntimeError(f"SMU Error: {error.code}, {error.message}")
        logger.info("Safe initialize SMU... done.")

    def smu_check_errors(self) -> None:
        smu = self.get_resource("smu")
        for error in iter_errors(smu):
            raise RuntimeError(f"SMU Error: {error.code}, {error.message}")

    def smu_output(self) -> bool:
        smu = self.get_resource("smu")
        return smu.output

    def smu_set_output(self, state: bool) -> None:
        smu = self.get_resource("smu")
        smu.output = state

    def smu_voltage(self) -> float:
        smu = self.get_resource("smu")
        return smu.voltage_level

    def smu_set_voltage(self, level: float) -> None:
        logger.info("Set SMU2 voltage: %s", format_metric(level, "V"))
        smu = self.get_resource("smu")
        smu.voltage_level = level

    def smu_set_voltage_range(self, level: float) -> None:
        level_abs = abs(level)
        logger.info("Set SMU2 voltage range: %s", format_metric(level_abs, "V"))
        smu = self.get_resource("smu")
        smu.voltage_range = level_abs

    def smu_set_current_compliance(self, level: float) -> None:
        logger.info("Set SMU2 current compliance: %s", format_metric(level, "A"))
        smu = self.get_resource("smu")
        smu.current_compliance = level

    def smu_read_current(self) -> float:
        smu = self.get_resource("smu")
        value = smu.measure_current()
        logger.info("Read SMU2 current: %s", format_metric(value, "A"))
        return value

    def smu_read_voltage(self) -> float:
        smu = self.get_resource("smu")
        value = smu.measure_voltage()
        logger.info("Read SMU2 voltage: %s", format_metric(value, "V"))
        return value

    def smu_compliance_tripped(self) -> bool:
        smu = self.get_resource("smu")
        return smu.compliance_tripped

    def smu_recover_voltage(self, voltage_step: float = 10.0, waiting_time: float = 0.25) -> None:
        """Recover voltage level to zero without changing output state."""
        output = self.smu_output()
        if output:
            voltage = self.smu_voltage()
            if voltage:
                voltage_range = LinearRange(voltage, 0, voltage_step)
                for step, voltage in enumerate(voltage_range):
                    self.smu_set_voltage(voltage)
                    time.sleep(waiting_time)
        else:
            self.smu_set_voltage(0)

    def smu_ramp_voltage(self, voltage_end: float, *, voltage_step: float = 10.0,
                         waiting_time: float = 0.25, before_step: Optional[Callable] = None,
                         after_step: Optional[Callable] = None) -> None:
        """Ramp voltage to `voltage_end` in `voltage_step`s providing callbacks
        to be executed for every step before and after applying the next voltage
        step."""
        voltage_begin = self.smu_voltage()
        voltage_range = LinearRange(voltage_begin, voltage_end, voltage_step)

        if abs(voltage_end) >= abs(voltage_begin):
            self.smu_set_voltage_range(voltage_end)

        # Ramp to end voltage
        for step, voltage in enumerate(voltage_range):

            # Call custom callback
            if callable(before_step):
                before_step(step, voltage)

            self.smu_set_voltage(voltage)
            time.sleep(waiting_time)

            # Call custom callback
            if callable(after_step):
                after_step(step, voltage)

        self.smu_set_voltage_range(voltage_end)

    # Bias SMU

    def safe_recover_bias_smu(self) -> None:
        logger.info("Safe recover Bias SMU...")
        smu = self.get_resource("bias_smu")
        output = smu.output
        if output == smu.OUTPUT_ON:
            logger.info("Bias SMU output is active...")
            function = smu.function
            if function == smu.FUNCTION_VOLTAGE:
                voltage = smu.voltage_level
                if voltage:
                    logger.info("Ramping Bias SMU to zero...")
                    voltage_ramp = LinearRange(voltage, 0, 25)
                    for voltage in voltage_ramp:
                        smu.voltage_level = voltage
                        self.bias_voltage_changed(voltage)
                        time.sleep(.5)
                    logger.info("Ramping Bias SMU to zero... done.")
            elif function == smu.FUNCTION_CURRENT:
                current = smu.current_level
                if current:
                    logger.info("Ramping Bias SMU to zero...")
                    current_ramp = LinearRange(current, 0, 25)
                    for current in current_ramp:
                        smu.current_level = current
                        time.sleep(.5)
                    logger.info("Ramping Bias SMU to zero... done.")
            time.sleep(1.)
            smu.output = smu.OUTPUT_OFF
            smu.function = smu.FUNCTION_VOLTAGE
            smu.voltage_level = 0
            self.bias_voltage_changed(0)
        else:
            smu.function = smu.FUNCTION_VOLTAGE
            smu.voltage_level = 0
            self.bias_voltage_changed(0)

        logger.info("Safe recover Bias SMU... done.")

    def safe_initialize_bias_smu(self) -> None:
        logger.info("Safe initialize Bias SMU...")
        bias_smu = self.get_resource("bias_smu")
        logger.info("Reset Bias SMU...")
        bias_smu.reset()
        time.sleep(.50)
        logger.info("Configure Bias SMU...")
        bias_smu.function = bias_smu.FUNCTION_VOLTAGE
        bias_smu.beeper = bias_smu.BEEPER_OFF
        for error in iter_errors(bias_smu):
            raise RuntimeError(f"Bias SMU Error: {error.code}, {error.message}")
        logger.info("Safe initialize Bias SMU... done.")

    def bias_output(self) -> bool:
        bias_smu = self.get_resource("bias_smu")
        return bias_smu.output

    def bias_set_output(self, state: bool) -> None:
        bias_smu = self.get_resource("bias_smu")
        bias_smu.output = state

    def bias_voltage(self) -> float:
        bias_smu = self.get_resource("bias_smu")
        return bias_smu.voltage_level

    def bias_set_voltage(self, level: float) -> None:
        logger.info("Set Bias voltage: %s", format_metric(level, "V"))
        bias_smu = self.get_resource("bias_smu")
        bias_smu.voltage_level = level
        self.bias_voltage_changed(level)

    def bias_set_voltage_range(self, level: float) -> None:
        level_abs = abs(level)
        logger.info("Set Bias voltage range: %s", format_metric(level_abs, "V"))
        bias_smu = self.get_resource("bias_smu")
        bias_smu.voltage_range = level_abs

    def bias_set_current_compliance(self, level: float) -> None:
        logger.info("Set Bias current compliance: %s", format_metric(level, "A"))
        bias_smu = self.get_resource("bias_smu")
        bias_smu.current_compliance = level

    def bias_read_current(self) -> float:
        bias_smu = self.get_resource("bias_smu")
        value = bias_smu.measure_current()
        logger.info("Read Bias current: %s", format_metric(value, "A"))
        return value

    def bias_read_voltage(self) -> float:
        bias_smu = self.get_resource("bias_smu")
        value = bias_smu.measure_voltage()
        logger.info("Read Bias voltage: %s", format_metric(value, "V"))
        return value

    def bias_compliance_tripped(self) -> None:
        bias_smu = self.get_resource("bias_smu")
        return bias_smu.compliance_tripped

    def bias_recover_voltage(self, voltage_step: float = 10.0, waiting_time: float = 0.25) -> None:
        """Recover voltage level to zero without changing output state."""
        output = self.bias_output()
        if output:
            voltage = self.bias_voltage()
            if voltage:
                voltage_range = LinearRange(voltage, 0, voltage_step)
                for step, voltage in enumerate(voltage_range):
                    self.bias_set_voltage(voltage)
                    time.sleep(waiting_time)
        else:
            self.bias_set_voltage(0)

    def bias_ramp_voltage(self, voltage_end: float, *, voltage_step: float = 10.0,
                          waiting_time: float = 0.25, before_step: Optional[Callable] = None,
                          after_step: Optional[Callable] = None) -> None:
        """Ramp voltage to `voltage_end` in `voltage_step`s providing callbacks
        to be executed for every step before and after applying the next voltage
        step."""
        voltage_begin = self.bias_voltage()
        voltage_range = LinearRange(voltage_begin, voltage_end, voltage_step)

        if abs(voltage_end) >= abs(voltage_begin):
            self.bias_set_voltage_range(voltage_end)

        # Ramp to end voltage
        for step, voltage in enumerate(voltage_range):

            # Call custom callback
            if callable(before_step):
                before_step(step, voltage)

            self.bias_set_voltage(voltage)
            time.sleep(waiting_time)

            # Call custom callback
            if callable(after_step):
                after_step(step, voltage)

        self.bias_set_voltage_range(voltage_end)

    # LCR

    def safe_initialize_lcr(self) -> None:
        lcr = self.get_resource("lcr")
        logger.info("Safe initialize LCR Meter...")
        logger.info("Reset LCR Meter...")
        lcr.reset()
        time.sleep(.50)
        logger.info("Configure LCR Meter...")
        logger.info("Set LCR Meter function: CPRP")
        lcr.function = lcr.FUNCTION_CPRP
        logger.info("Set LCR Meter measurement time: LONG")
        lcr.set_measurement_time("LONG")
        logger.info("Set LCR Meter correction length: 4 m")
        lcr.correction_length = 4
        # TODO add to generic LCR driver!
        lcr.write(":INIT:CONT OFF")
        lcr.write(":TRIG:SOUR BUS")
        lcr.write(":CORR:OPEN:STAT OFF")
        lcr.write(":CORR:SHORT:STAT OFF")
        lcr.write(":CORR:LOAD:STAT OFF")
        for error in iter_errors(lcr):
            raise RuntimeError(f"LCR Error: {error.code}, {error.message}")
        logger.info("Safe initialize LCR Meter... done.")

    def lcr_set_amplitude(self, level: float) -> None:
        logger.info("Set LCR Meter amplitude: %s", format_metric(level, "V"))
        lcr = self.get_resource("lcr")
        lcr.amplitude = level

    def lcr_set_frequency(self, frequency: float) -> None:
        logger.info("Set LCR Meter frequency: %s", format_metric(frequency, "Hz"))
        lcr = self.get_resource("lcr")
        lcr.frequency = frequency

    def lcr_enable_open_correction(self, state: bool) -> None:
        lcr = self.get_resource("lcr")
        lcr.write(f":CORR:OPEN:STAT {state:d}")
        assert bool(int(lcr.query(":CORR:OPEN:STAT?"))) == state

    def lcr_perform_open_correction(self, timeout: float = 16.0) -> None:
        logger.info("Perform LCR Meter open correction...")
        lcr = self.get_resource("lcr")
        lcr.resource.write(":CORR:OPEN")
        t = Timer()
        while t.delta() < timeout:
            try:
                lcr.resource.query("*OPC?")
            except Exception:
                ...
            else:
                logger.info("Perform LCR Meter open correction... done.")
                return
            time.sleep(.5)
        logger.error("Perform LCR Meter open correction... failed.")
        raise RuntimeError("LCR Meter open correction failed.")

        #lcr.write(":CORR:OPEN:STAT ON")
        #lcr.query("*OPC?")

    def lcr_acquire_reading(self) -> Tuple[float, float]:
        """Return primary and secondary LCR reading."""
        lcr = self.get_resource("lcr")
        lcr.write("TRIG:IMM")
        # prim, sec = list(map(float, lcr.query("FETC?").split(",")))[:2]
        prim, sec = lcr.measure_impedance()
        logger.info("LCR Meter reading: %s, %s", format_metric(prim, "F"), format_metric(sec, "Ohm"))
        return prim, sec

    def lcr_acquire_filter_reading(self, *, maximum: int = 64, threshold: float = 0.005,
                                   size: int = 3, delay: float = 0.1) -> Tuple[float, float]:
        """Aquire readings until standard deviation (sample) / mean < threshold.
        Size is the number of samples to be used for filter calculation.
        """
        samples = []
        prim, sec = 0., 0.
        for _ in range(maximum):
            prim, sec = self.lcr_acquire_reading()
            samples.append(prim)
            samples = samples[-size:]
            if len(samples) >= size:
                if std_mean_filter(samples, threshold):
                    return prim, sec
            time.sleep(delay)
        logger.warning("Maximum LCR Meter sample count reached: %d", maximum)
        return prim, sec

    # Electrometer

    def safe_initialize_elm(self) -> None:
        elm = self.get_resource("elm")
        logger.info("Safe initialize Electrometer...")
        logger.info("Reset Electrometer...")
        elm.reset()
        time.sleep(.50)
        logger.info("Configure Electrometer...")

        # TODO
        elm.write(":SENS:CURR:RANG:AUTO ON")
        elm.write(":SENS:CURR:NPLC 10")
        elm.write(":SENS:CURR:RANG:AUTO:LLIM 2E-9")
        elm.write(":SENS:CURR:RANG:AUTO:ULIM 200E-6")
        elm.write(":SENS:CURR:RANG 2E-9")
        elm.write(":SENS:FUNC 'CURR'")
        elm.write(":SYST:ZCH ON")
        elm.write(":SYST:ZCOR ON")
        elm.write(":FORM:ELEM READ")
        elm.write(":SENS:CURR:RANG:AUTO ON")
        elm.query("*OPC?")

        for error in iter_errors(elm):
            raise RuntimeError(f"Electrometer Error: {error.code}, {error.message}")
        logger.info("Safe initialize Electrometer... done.")

    def elm_set_zero_check(self, enabled: bool) -> None:
        elm = self.get_resource("elm")
        logger.info("Set Electrometer zero check: %s", format_switch(enabled))
        elm.write(f":SYST:ZCH {enabled:d}")
        elm.query("*OPC?")

    def elm_read_current(self) -> float:
        elm = self.get_resource("elm")
        value = float(elm.query(":READ?"))
        logger.info("Read Electrometer current: %s", format_metric(value, "A"))
        return value

    # Table

    def table_configure(self) -> None:
        table = Table(self.get_resource("table"))
        table.configure()

    def table_abort(self) -> None:
        table = Table(self.get_resource("table"))
        table.abort()

    def table_apply_profile(self, name: str) -> None:
        table = Table(self.get_resource("table"))

        profile = Settings().tableProfile(name)
        if not profile:
            raise KeyError("No such table profile: %r", name)

        logger.info("Applying table profile: %r", name)

        accel = profile.get("accel")
        if accel is not None:
            table.set_accel(int(accel))
            logger.info("Set table acceleration: %G", accel)

        vel = profile.get("vel")
        if vel is not None:
            table.set_vel(int(vel))
            logger.info("Set table velocity: %G", vel)

    def table_position(self) -> Tuple[float, float, float]:
        table = Table(self.get_resource("table"))
        return table.position()

    def table_move_relative(self, position: Tuple[float, float, float]) -> None:
        table = Table(self.get_resource("table"))
        table.move_relative(position)

    def table_move_absolute(self, position: Tuple[float, float, float]) -> None:
        table = Table(self.get_resource("table"))
        table.move_absolute(position)

    def table_safe_move_absolute(self, position: Tuple[float, float, float]) -> None:
        table = Table(self.get_resource("table"))
        table.safe_move_absolute(position)


    # Needles

    needles_axis: int = 0
    needles_up_position: float = 1000.
    needles_down_position: float = 0.

    def needles_verify_position(self, position: float, decimals: int = 3) -> None:
        tango = self.get_resource("tango")
        pos_x = tango[type(self).needles_axis].position
        if round(pos_x, decimals) != round(position, decimals):
            raise RuntimeError(f"TANGO position mismatch: {pos_x} != {position}")

    def needles_verify_calibration(self) -> None:
        tango = self.get_resource("tango")
        if not tango[type(self).needles_axis].is_calibrated:
            raise RuntimeError(f"TANGO axis requires calibration.")

    def needles_calibrate(self) -> None:
        logger.info("Calibrate TANGO...")
        tango = self.get_resource("tango")
        tango[type(self).needles_axis].calibrate()
        logger.info("Calibrate TANGO... done.")

    def needles_range_measure(self) -> None:
        logger.info("Range measure TANGO...")
        tango = self.get_resource("tango")
        tango[type(self).needles_axis].range_measure()
        logger.info("Range measure TANGO... done.")

    def needles_move_absolute(self, position: float) -> None:
        tango = self.get_resource("tango")
        tango[type(self).needles_axis].move_absolute(position)

    def needles_wait_movement_finished(self) -> None:
        tango = self.get_resource("tango")
        def condition():
            return not tango.is_moving
        try:
            wait_until(condition)
        except TimeoutError as exc:
            raise TimeoutError("Needle movement timeout.") from exc

    def needles_up(self) -> None:
        logger.info("Moving needles up...")
        position = type(self).needles_up_position
        self.needles_verify_calibration()
        self.needles_move_absolute(position)
        self.needles_wait_movement_finished()
        self.needles_verify_position(position)
        logger.info("Moving needles up... done.")

    def needles_down(self) -> None:
        logger.info("Moving needles down...")
        position = type(self).needles_down_position
        self.needles_verify_calibration()
        self.needles_move_absolute(position)
        self.needles_wait_movement_finished()
        self.needles_verify_position(position)
        logger.info("Moving needles down... done.")


class CapacitorDischarge:

    def __init__(self, station: Station) -> None:
        self.station: Station = station
        self.sample_count: int = 8
        self.sample_interval: float = 0.25
        self.threshold_voltage: float = 0.3  # Volt
        self.timeout: float = 10.0  # Seconds
        self.settle_time: float = 1.0

    def check_discharged_state(self) -> bool:
        samples = []
        smu = self.station.get_resource("smu")
        for _ in range(self.sample_count):
            voltage = smu.measure_voltage()
            samples.append(voltage)
            time.sleep(self.sample_interval)

        mean_voltage = statistics.mean(samples)

        return mean_voltage <= self.threshold_voltage

    def __call__(self) -> bool:
        environ = self.station.environ
        environ.set_discharge(True)

        smu = self.station.get_resource("smu")
        smu.route_terminal = smu.ROUTE_TERMINAL_FRONT
        smu.function = smu.FUNCTION_CURRENT
        smu.output = smu.OUTPUT_ON

        time.sleep(self.settle_time)

        success = False
        t = Timer()

        while True:
            success = self.check_discharged_state()

            if success:
                break

            if t.delta() > self.timeout:
                logger.error("Capacitor discarge timeout (%.1f s).", self.timeout)
                break

        smu.output = smu.OUTPUT_OFF
        smu.function = smu.FUNCTION_VOLTAGE
        smu.route_terminal = smu.ROUTE_TERMINAL_REAR

        environ.set_discharge(False)

        time.sleep(self.settle_time)

        return success
