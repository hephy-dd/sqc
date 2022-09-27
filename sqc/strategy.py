import logging
import time
from itertools import cycle
from typing import Dict, List

from comet.parameter import validate_parameters
from comet.estimate import Estimate

from .core.geometry import NeedlesGeometry
from .core.transformation import affine_transformation, transform
from .core.measurement import measurement_registry
from .core.utils import parse_strips, verify_position
from .measurements import ComplianceError, AnalysisError
from .settings import Settings
from .context import AbortRequested, Statistics

__all__ = ["SequenceStrategy"]

logger = logging.getLogger(__name__)


def enabled_items(items):
    """Return list of enabled items from list."""
    return [item for item in items if item.isEnabled()]


class SequenceController:

    def __init__(self, context):
        self.context = context
        self.contacts = ContactHandler(context.padfile)

    def initialize(self):
        self.context.set_message("Initialize...")
        self.context.create_timestamp()  # new timestamp for measurement!
        self.context.set_progress(0, 0, 0)
        self.context.set_current_item(None)
        self.context.set_current_strip(None)
        self.context.set_stripscan_progress(0, 0)

        station = self.context.station
        station.open_resources()
        station.box_set_test_running(True)
        station.safe_initialize()
        station.table_configure()

        self.safe_recover_table()

    def finalize(self):
        self.context.set_message("Finalize...")
        self.context.set_progress(0, 0, 0)
        self.context.set_current_item(None)
        self.context.set_current_strip(None)
        self.context.set_stripscan_progress(0, 0)

        self.safe_recover_table()

        station = self.context.station
        station.finalize()
        station.box_set_test_running(False)

        self.context.set_message("Done.")

    def safe_recover_table(self):
        if self.context.parameters.get("option_debug_no_table"):
            logger.info("Ignoring table movement (--debug-no-table)")
        else:
            offset = -800
            logger.info("Table move relative z: %f um", offset)
            station = self.context.station
            station.table_move_relative((0, 0, -abs(offset)))

    def safe_move_table(self, strip, position):
        if self.context.parameters.get("option_debug_no_table"):
            logger.info("Ignoring table movement (--debug-no-table)")
        else:
            logger.info("Contact strip: %s %s", strip, position)
            station = self.context.station
            #
            # TODO throttle contacting speed
            #
            z_approach = [20, 15, 10, 5]
            z_offset = sum(map(abs, z_approach))
            x, y, z = position
            station.table_safe_move_absolute((x, y, z - abs(z_offset)))
            for z in z_approach:
                time.sleep(.25)
                station.table_move_relative((0, 0, abs(z)))

            # station.table_safe_move_absolute(position)

            # Verify table position
            current_position = station.table_position()
            if not verify_position(position, current_position, threshold=1.0):
                raise RuntimeError(f"Table position mismatch, requested {position} but table returned {current_position}")


class ContactHandler:

    def __init__(self, padfile):
        self.padfile = padfile
        self.needles_geometry = NeedlesGeometry(padfile, 2)
        self.contact_positions = {}

    def strip_position(self, strip: str):
        if strip not in self.contact_positions:
            raise ValueError("No such strip in contact positions: %s", strip)
        pad, position = self.contact_positions.get(strip)
        if self.needles_geometry.is_pad_valid(pad):
            return position
        return None

    def calculate_positions(self):
        # TODO
        padfile = self.padfile
        if not padfile:
            raise ValueError("No padfile loaded.")
        alignment = Settings().alignment()[:3]
        if len(alignment) != 3:
            raise ValueError("No alignment available.")
        s1 = padfile.references[0].position
        s2 = padfile.references[1].position
        s3 = padfile.references[2].position
        t1, t2, t3 = alignment
        T, V0 = affine_transformation(s1, s2, s3, t1, t2, t3)
        logger.info("Transformation matrix: T=%s V0=%s", T, V0)
        self.contact_positions = {}
        for pad in padfile.pads.values():
            position = transform(T, V0, pad.position)
            self.contact_positions[pad.name] = (pad, position)
        logger.info("Transformed %d positions.", len(self.contact_positions))


class SequenceStrategy:

    def __init__(self, context):
        self.context = context
        self.controller = SequenceController(context)
        self.measurements = {}
        self.statistics = Statistics()

    def __call__(self, sequence):
        self.controller.contacts.calculate_positions()
        self.create_measurements(sequence)
        self.reset_sequence(sequence)
        self.validate_sequence(sequence)
        try:
            self.handle_sequence(sequence)
        except Exception as exc:
            logger.exception(exc)
            self.context.handle_exception(exc)
        finally:
            self.show_statistics()
            self.serialize_data()

    @property
    def remeasure_attempts(self) -> int:
        return self.context.parameters.get("remeasure_count", 0)

    @property
    def recontact_attempts(self) -> int:
        return self.context.parameters.get("recontact_count", 0)

    def calculate_strip_pattern(self, item) -> Dict[str, List[object]]:
        """Return dictionary containing strip measurements for every strip
        selected by strip range, interval and enabled state.
        """
        strips: Dict[str, List[object]] = {}
        all_strips: List[str] = list(self.context.padfile.pads.keys())
        enabled_strip_items: List = enabled_items(item.allChildren())

        # List of all strips selected by item
        selected_strips: List[str] = parse_strips(all_strips, item.strips())

        # Iterate over every strip to claculate interval pattern
        for index, strip in enumerate(all_strips):
            if strip in selected_strips:
                for strip_item in enabled_strip_items:
                    if index % strip_item.interval() == 0:
                        strips.setdefault(strip, []).append(strip_item)

        return strips

    # Validate items

    def validate_sequence(self, sequence):
        if not self.context.padfile:
            raise TypeError("No padfile loaded")

        output_path = self.context.parameters.get("output_path")
        if not output_path:
            raise ValueError("No output path given.")

        operator_name = self.context.parameters.get("operator_name")
        if not operator_name:
            raise ValueError("No operator name given.")

        for item in sequence:
            self.validate_item(item)
            for child in item.allChildren():
                self.validate_strip_item(item, child)

    def validate_item_strips(self, item):
        try:
            parse_strips(list(self.context.padfile.pads.keys()), item.strips())
        except Exception as exc:
            raise ValueError(f"Invalid strips expression for {item.fullName()} ({item.typeName()}): {item.strips()!r}, {exc}")

    def validate_item_interval(self, item):
        if item.interval() < 1:
            raise KeyError(f"Invalid interval for {item.fullName()}: {item.interval()}")

    def validate_item_parameters(self, item):
        handler = measurement_registry.get(item.typeName())
        if handler:
            try:
                validate_parameters(handler, item.parameters())
            except KeyError as exc:
                raise KeyError(f"Invalid parameter for {item.fullName()}: {exc}")
            except ValueError as exc:
                raise ValueError(f"Invalid parameter value for {item.fullName()}: {exc}")

    def validate_item(self, item):
        self.validate_item_strips(item)
        self.validate_item_parameters(item)

    def validate_strip_item(self, parent, item):
        self.validate_item_interval(item)
        self.validate_item_parameters(item)

    # Reset items

    def reset_sequence(self, sequence):
        for item in sequence:
            self.context.set_item_progress(item, 0, 0)
            self.reset_item_state(item)
            for strip_item in item.allChildren():
                self.reset_item_state(strip_item)

    def reset_item_state(self, item):
        parent = item.parent()
        if parent and not parent.isEnabled():
            state = item.IgnoredState
        else:
            if item.isEnabled():
                state = item.PendingState
            else:
                state = item.IgnoredState
        self.context.set_item_state(item, state)

    def create_measurement(self, item):
        key = item.typeName()
        handler = measurement_registry.get(key)
        if handler:
            self.validate_item_parameters(item)
            return handler(
                context=self.context,
                type=item.typeName(),
                name=item.fullName(),
                namespace=item.namespace(),
                parameters=item.parameters()
            )
        else:
            raise KeyError(f"No such measurement type: {key}")

    def create_measurements(self, sequence):
        for item in enabled_items(sequence):
            self.measurements[item.key()] = self.create_measurement(item)
            for child in enabled_items(item.allChildren()):
                self.measurements[child.key()] = self.create_measurement(child)

    def get_measurement(self, item):
        return self.measurements.get(item.key())

    def handle_suspend(self, item) -> None:
        if self.context.is_suspend_requested:
            self.context.set_item_state(item, item.HaltedState)
            self.context.handle_suspend()  # blocking
            self.context.set_item_state(item, item.ActiveState)

    def handle_abort(self, item) -> bool:
        if self.context.is_abort_requested:
            self.context.set_item_state(item, item.AbortedState)
            return True
        return False

    def handle_before_sequence(self, sequence):
        for item in enabled_items(sequence):
            if self.handle_abort(item):
                break

            self.get_measurement(item).before_sequence()

            for strip_item in enabled_items(item.allChildren()):
                if self.handle_abort(strip_item):
                    break

                self.get_measurement(strip_item).before_sequence()

                if self.handle_abort(strip_item):
                    break

            if self.handle_abort(item):
                break

    def handle_after_sequence(self, sequence):
        for item in enabled_items(sequence):
            if self.handle_abort(item):
                break

            self.get_measurement(item).after_sequence()

            for strip_item in enabled_items(item.allChildren()):
                if self.handle_abort(strip_item):
                    break

                self.get_measurement(strip_item).after_sequence()

                if self.handle_abort(strip_item):
                    break

            if self.handle_abort(item):
                break

    def handle_sequence(self, sequence):
        try:
            self.controller.initialize()

            self.handle_before_sequence(sequence)

            for item in enabled_items(sequence):

                # Halt on suspend request
                self.handle_suspend(item)

                if self.handle_abort(item):
                    break

                self.handle_sequence_item(item)

                if self.handle_abort(item):
                    break

            if not self.context.is_abort_requested:
                self.handle_after_sequence(sequence)

        except Exception as exc:
            logger.exception(exc)
            self.context.handle_exception(exc)
        finally:
            self.controller.finalize()

    def handle_sequence_item(self, item):
        self.context.set_current_strip(None)
        self.context.set_stripscan_progress(0, 0)
        self.context.set_message(item.fullName())
        self.context.set_current_item(item)
        self.context.set_item_state(item, item.ActiveState)

        logger.info("-------- %s --------", item.fullName())

        try:
            self.run_measurement(self.get_measurement(item))
        except ComplianceError:
            logger.error("Compliance tripped while running: %r with parameters %s", item.fullName(), item.parameters())
            self.context.set_item_state(item, item.ComplianceState)
            return
        except Exception:
            logger.error("Exception occured while running: %r with parameters %s", item.fullName(), item.parameters())
            self.context.set_item_state(item, item.FailedState)
            raise

        if self.handle_abort(item):
            return

        self.handle_strip_items(item)

        if self.context.is_abort_requested:
            self.context.set_item_state(item, item.AbortedState)
        else:
            self.context.set_item_state(item, item.SuccessState)

        self.context.set_message("")
        self.context.set_current_strip(None)
        self.context.set_stripscan_progress(0, 0)

    def handle_strip_items(self, item):
        selected_strips = self.calculate_strip_pattern(item)
        estimate = Estimate(len(selected_strips))
        passed_strips = 0

        self.context.set_progress(0, len(selected_strips), 0)

        for strip, strip_items in selected_strips.items():
            self.context.set_stripscan_progress(passed_strips + 1, len(selected_strips))
            self.context.set_item_progress(item, passed_strips + 1, len(selected_strips))
            self.context.set_item_state(item, item.ActiveState)

            # Halt on suspend request
            self.handle_suspend(item)

            # Check if position is valid contact
            position = self.controller.contacts.strip_position(strip)
            if position is None:
                logger.warning("Skipping invalid strip: %s", strip)
            else:
                # Reset strip item states
                for strip_item in item.allChildren():
                    if strip_item not in strip_items:
                        self.context.set_item_state(strip_item, strip_item.IgnoredState)
                    else:
                        self.reset_item_state(strip_item)

                # TODO
                x_offsets = cycle([0, +5, -5, +2, -2])

                for attempt in range(self.recontact_attempts + 1):

                    result = True

                    if attempt:
                        logger.warning("Remeasurement failed, recontacting strip %s (%d/%d)", strip, attempt, self.recontact_attempts)
                        self.increment_recontact_counter(strip, item.fullName())

                    # TODO
                    # Change recontact x position
                    x, y, z = position
                    x_offset = next(x_offsets)
                    x = x + x_offset
                    position = x, y, z
                    if x_offset:
                        logger.info("Applied recontact offset to x-position: %+G um", x_offset)

                    # Only once for every actual strip
                    self.get_measurement(item).before_strip()

                    # Contact strip
                    self.controller.safe_move_table(strip, position)

                    # Strip measurements
                    for strip_item in strip_items:

                        if self.handle_abort(strip_item):
                            break

                        result = self.handle_strip_item(strip_item, strip)

                        if self.handle_abort(strip_item):
                            break

                        # Re-measurements failed
                        if not result:
                            break

                    self.controller.safe_recover_table()
                    self.get_measurement(item).after_strip()

                    # If all ok
                    if result:
                        break

            if self.handle_abort(item):
                break

            passed_strips += 1

            estimate.advance()

            self.context.set_progress(0, len(selected_strips), passed_strips + 1)
            self.context.set_stripscan_progress(passed_strips + 1, len(selected_strips))
            self.context.set_stripscan_estimation(estimate.elapsed, estimate.remaining)

    def handle_strip_item(self, strip_item, strip) -> bool:
        """Return False if auto re-measurements failed."""
        self.context.set_current_strip(strip)
        self.context.set_current_item(strip_item)
        self.context.set_item_state(strip_item, strip_item.ActiveState)
        self.context.set_message(strip_item.fullName())

        logger.info("-------- #%s %s --------", strip, strip_item.fullName())

        try:
            result = self.auto_repeat_measurement(strip, strip_item)
        except ComplianceError:
            logger.error("Compliance tripped while running: %r with parameters %s", strip_item.fullName(), strip_item.parameters())
            self.context.set_item_state(strip_item, strip_item.ComplianceState)
        except Exception:
            logger.error("Exception occured while running: %r with parameters %s", strip_item.fullName(), strip_item.parameters())
            self.context.set_item_state(strip_item, strip_item.FailedState)
            raise
        else:
            if self.context.is_abort_requested:
                self.context.set_item_state(strip_item, strip_item.AbortedState)
            else:
                self.context.set_item_state(strip_item, strip_item.SuccessState)
        return result

    def auto_repeat_measurement(self, strip: str, item) -> bool:
        """Return False if all re-measurements failed."""
        attempts = self.remeasure_attempts
        for attempt in range(attempts + 1):
            if attempt:
                logger.warning("Analysis failed, repeating measurement %r in place (%d/%d)", item.fullName(), attempt, attempts)
                self.increment_remeasure_counter(strip, item.fullName())
            try:
                self.run_measurement(self.get_measurement(item))
                return True
            except AnalysisError as exc:
                logger.exception(exc)
                continue
        # Request recontact
        return False

    def run_measurement(self, measurement):
        """Run measurement and handle exceptions for context."""
        try:
            measurement.initialize()
            measurement.acquire()
        except AbortRequested:
            ...
        except ComplianceError:
            raise
        except AnalysisError:
            raise
        except Exception as exc:
            self.context.handle_exception(exc)
            raise
        finally:
            try:
                measurement.finalize()
            except AbortRequested:
                ...
            except Exception as exc:
                self.context.handle_exception(exc)
                raise

    def increment_remeasure_counter(self, strip, name):
        self.context.statistics.increment_remeasure_counter(strip, name)
        self.context.statistics_changed.emit()
        self.statistics.increment_remeasure_counter(strip, name)

    def increment_recontact_counter(self, strip, name):
        self.context.statistics.increment_recontact_counter(strip, name)
        self.context.statistics_changed.emit()
        self.statistics.increment_recontact_counter(strip, name)

    def serialize_data(self):
        header = self.context.parameters
        namespaces = self.context.data
        if namespaces:
            logger.info("Serialize data...")
            for namespace, data in namespaces.items():
                for writer in self.context.writers:
                    writer(namespace, header, data)
            logger.info("Serialize data... done.")

    def show_statistics(self):
        self.show_remeasure_statistics()
        self.show_recontact_statistics()

    def show_remeasure_statistics(self):
        remeasure_counter = self.statistics.remeasure_counter
        if remeasure_counter:
            all_remeasure_attempts = self.remeasure_attempts * (self.recontact_attempts + 1)
            logger.info("-------- Remeasurement Statistics --------")
            for strip, counter in remeasure_counter.items():
                for name, count in counter.items():
                    logger.info("Strip %r, %r: %d/%d", strip, name, count, all_remeasure_attempts)

    def show_recontact_statistics(self):
        recontact_counter = self.statistics.recontact_counter
        if recontact_counter:
            logger.info("-------- Recontact Statistics --------")
            for strip, counter in recontact_counter.items():
                for name, count in counter.items():
                    logger.info("Strip %r, %r: %d/%d", strip, name, count, self.recontact_attempts)
