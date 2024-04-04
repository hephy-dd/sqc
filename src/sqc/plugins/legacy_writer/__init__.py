import logging
import math
import time
import os
from typing import Any, Dict, Iterable, List
from collections import namedtuple

from comet.utils import make_iso, safe_filename

from sqc import __version__

__all__ = ["LegacyWriterPlugin"]

logger = logging.getLogger(__name__)


def get_first_frame(data, key):
    items = list(data.get(key, {}).values())
    if items:
        return items[0]
    return []


def join_ivc(iv, cv):
    rows = []
    cv_data = {}
    for data in cv:
        key = data.get("bias_voltage")
        cv_data[key] = data
    for data in iv:
        key = data.get("bias_voltage")
        data["lcr_cp"] = cv_data.get(key, {}).get("lcr_cp", float("nan"))
        data["lcr_rp"] = cv_data.get(key, {}).get("lcr_rp", float("nan"))
        rows.append(data.copy())
    return rows


class LegacyWriterPlugin:

    def install(self, window) -> None:
        context = window.context
        context.add_writer(LegacyWriter(context))

    def uninstall(self, window) -> None:
        ...


class LegacyWriter:

    def __init__(self, context):
        self.context = context

    def __call__(self, namespace: str, parameters: Dict[str, Any], data: Dict[str, Any]) -> None:
        parameters.setdefault("timestamp", time.time())

        # Serialze first IV/CV dataframe
        iv = get_first_frame(data, "iv")
        cv = get_first_frame(data, "cv")
        if iv or cv:
            filename = self.create_filename(namespace, parameters, "IVC_")
            self.create_path(filename)
            self.write_ivc_file(filename, parameters, iv, cv)

        # Serialze first stripscan dataframe
        stripscan = self.merge_stripscan(data)
        if stripscan:
            strips = self.context.padfile.pads.keys()
            filename = self.create_filename(namespace, parameters, "Str_")
            self.create_path(filename)
            self.write_str_file(filename, parameters, stripscan, strips)

    def create_filename(self, namespace, parameters, prefix):
        timestamp = parameters.get("timestamp", time.time())
        sensor_name = parameters.get("sensor_name")
        output_path = os.path.realpath(parameters.get("output_path", os.getcwd()))
        output_path = os.path.join(output_path, safe_filename(sensor_name))
        suffix = make_iso(timestamp)
        if namespace:
            suffix = f"{suffix}_{namespace}"
        basename = safe_filename(f"{prefix}{sensor_name}-{suffix}.txt")
        return os.path.join(output_path, basename)

    def create_path(self, filename) -> None:
        path = os.path.dirname(filename)
        if not os.path.exists(path):
            logger.info("Creating directory: %s", path)
            os.makedirs(path)

    def merge_stripscan(self, data) -> Dict[str, Any]:
        stripscan: Dict[str, Any] = {}
        for item in get_first_frame(data, "istrip"):
            stripscan.setdefault(item.get("strip"), {}).update({"istrip_i": item.get("istrip_i")})
            stripscan.setdefault(item.get("strip"), {}).update({"temperature": item.get("temperature")})
            stripscan.setdefault(item.get("strip"), {}).update({"humidity": item.get("humidity")})
        for item in get_first_frame(data, "rpoly"):
            stripscan.setdefault(item.get("strip"), {}).update({"rpoly_r": item.get("rpoly_r")})
            stripscan.setdefault(item.get("strip"), {}).update({"temperature": item.get("temperature")})
            stripscan.setdefault(item.get("strip"), {}).update({"humidity": item.get("humidity")})
        for item in get_first_frame(data, "cac"):
            stripscan.setdefault(item.get("strip"), {}).update({"cac_cp": item.get("cac_cp")})
            stripscan.setdefault(item.get("strip"), {}).update({"cac_rp": item.get("cac_rp")})
            stripscan.setdefault(item.get("strip"), {}).update({"temperature": item.get("temperature")})
            stripscan.setdefault(item.get("strip"), {}).update({"humidity": item.get("humidity")})
        for item in get_first_frame(data, "idiel"):
            stripscan.setdefault(item.get("strip"), {}).update({"idiel_i": item.get("idiel_i")})
            stripscan.setdefault(item.get("strip"), {}).update({"temperature": item.get("temperature")})
            stripscan.setdefault(item.get("strip"), {}).update({"humidity": item.get("humidity")})
        for item in get_first_frame(data, "cint"):
            stripscan.setdefault(item.get("strip"), {}).update({"cint_cp": item.get("cint_cp")})
            stripscan.setdefault(item.get("strip"), {}).update({"cint_rp": item.get("cint_rp")})
            stripscan.setdefault(item.get("strip"), {}).update({"temperature": item.get("temperature")})
            stripscan.setdefault(item.get("strip"), {}).update({"humidity": item.get("humidity")})
        for item in get_first_frame(data, "idark"):
            stripscan.setdefault(item.get("strip"), {}).update({"idark_i": item.get("idark_i")})
            stripscan.setdefault(item.get("strip"), {}).update({"temperature": item.get("temperature")})
            stripscan.setdefault(item.get("strip"), {}).update({"humidity": item.get("humidity")})
        for item in get_first_frame(data, "rint"):
            stripscan.setdefault(item.get("strip"), {}).update({"rint_r": item.get("rint_r")})
            stripscan.setdefault(item.get("strip"), {}).update({"temperature": item.get("temperature")})
            stripscan.setdefault(item.get("strip"), {}).update({"humidity": item.get("humidity")})
        return stripscan

    def write_ivc_file(self, filename: str, parameters: Dict[str, Any], iv: List, cv: List) -> None:
        try:
            logger.info("Writing to %s...", filename)
            with open(filename, "w") as fp:
                writer = LegacyIVCWriter(fp)
                writer.write_header(parameters)
                writer.write_table(iv, cv)
        except Exception as exc:
            raise RuntimeError(f"Failed to write IVC file: {filename}") from exc

    def write_str_file(self, filename: str, parameters: Dict[str, Any], stripscan: Dict[str, Any], strips: Iterable[str]) -> None:
        try:
            logger.info("Writing to %s...", filename)
            with open(filename, "w") as fp:
                writer = LegacyStrWriter(fp)
                writer.write_header(parameters)
                writer.write_table_header()
                writer.write_table_rows(parameters, stripscan, strips)
        except Exception as exc:
            raise RuntimeError(f"Failed to write Str file: {filename}") from exc


class LegacyBaseWriter:

    def __init__(self, fp) -> None:
        self.fp = fp
        self.linesep = "\n"
        self.colum_width = 24

    def write_line(self, text) -> None:
        self.fp.write(f"{text}{self.linesep}")

    def write_row(self, row: List[Any]) -> None:
        width = self.colum_width
        self.write_line("".join(f"{format(item):<{width}}" for item in row))

    def write_header(self, data: Dict[str, Any]) -> None:
        project = data.get("project", "")
        sensor_type = data.get("sensor_type", "")
        sensor_name = data.get("sensor_name", "")
        operator_name = data.get("operator_name", "")
        asctime = time.asctime(time.localtime(data.get("timestamp", 0)))
        self.write_line("# Measurement file: ")
        self.write_line(f" # Project: {project}")
        self.write_line(f" # Sensor Type: {sensor_type}")
        self.write_line(f" # ID: {sensor_name}")
        self.write_line(f" # Operator: {operator_name}")
        self.write_line(f" # Date: {asctime}")
        self.write_line("")
        self.write_line("")


class LegacyIVCWriter(LegacyBaseWriter):

    IVCColumn = namedtuple("IVCColumn", ("header", "key"))

    columns = [
        IVCColumn("Voltage [V]", "bias_smu_v"),
        IVCColumn("current [A]", "bias_smu_i"),
        IVCColumn("capacitance [F]", "lcr_cp"),
        IVCColumn("temperature [deg]", "temperature"),
        IVCColumn("humidity [%]", "humidity"),
    ]

    def write_table(self, iv, cv):
        if iv and cv:
            rows = join_ivc(iv, cv)
        elif iv:
            rows = iv
        else:
            rows = cv
        self.write_row([column.header for column in type(self).columns])
        keys = [column.key for column in type(self).columns]
        for row in rows:
            self.write_row([row.get(key, float("nan")) for key in keys])


class LegacyStrWriter(LegacyBaseWriter):

    StrColumn = namedtuple("StrColumn", ("header", "caption", "key"))

    columns = [
        StrColumn("Pad", "#", "strip"),
        StrColumn("Istrip", "current[A]", "istrip_i"),
        StrColumn("Rpoly", "res[Ohm]", "rpoly_r"),
        StrColumn("Cac", "Cp[F]", "cac_cp"),
        StrColumn("Cac_Rp", "Rp[Ohm]", "cac_rp"),
        StrColumn("Idiel", "current[A]", "idiel_i"),
        StrColumn("Cint", "Cp[F]", "cint_cp"),
        StrColumn("Cint_Rp", "Rp[Ohm]", "cint_rp"),
        StrColumn("Idark", "current[A]", "idark_i"),
        StrColumn("Rint", "res[Ohm]", "rint_r"),
        StrColumn("Temperature", "degree[C]", "temperature"),
        StrColumn("Humidity", "rel. percent[rel%]", "humidity"),
    ]

    def write_header(self, data: Dict[str, Any]) -> None:
        super().write_header(data)
        pads = data.get("geometry", {}).get("properties", {})  # TODO
        campaign = pads.get("campaign", "")
        reference_pad = pads.get("reference_pad", "")
        second_side_start = pads.get("second_side_start", "")
        implant_length = pads.get("implant_length", "")
        metal_width = pads.get("metal_width", "")
        implant_width = pads.get("implant_width", "")
        metal_length = pads.get("metal_length", "")
        pitch = pads.get("pitch", "")
        thickness = pads.get("thickness", "")
        type = pads.get("type", "")
        self.write_line(f"# Campaign: {campaign}")
        self.write_line(f"# Creator: SQC {__version__}")
        self.write_line(f"# reference pad: {reference_pad}")
        self.write_line(f"# second_side_start: {second_side_start}")
        self.write_line(f"# implant_length: {implant_length}")
        self.write_line(f"# metal_width: {metal_width}")
        self.write_line(f"# implant_width: {implant_width}")
        self.write_line(f"# metal_length: {metal_length}")
        self.write_line(f"# pitch: {pitch}")
        self.write_line(f"# thickness: {thickness}")
        self.write_line(f"# type: {type}")
        self.write_line("")
        self.write_line("")

    def write_table_header(self) -> None:
        self.write_row([column.header for column in type(self).columns])
        self.write_row([column.caption for column in type(self).columns])

    def write_table_rows(self, parameters: Dict[str, Any], data: Dict[str, Any], strips: Iterable[str]) -> None:
        placeholder = "--"

        def get_value(row, key):
            """Return valid value or placeholder."""
            value = row.get(key)
            if isinstance(value, float):
                if math.isfinite(value):
                    return value
            if isinstance(value, str) and value:
                return value
            return placeholder

        keys = [column.key for column in type(self).columns]

        # For every strip defined by padfile
        for strip in strips:
            row = data.get(strip, {})
            row["strip"] = strip
            self.write_row([get_value(row, key) for key in keys])


def test_legacy_writer(context, output_path):
    namespace = "test"
    parameters = {
        "campaign": "Hamamatsu",
        "sensor_name": "Unnamed",
        "output_path": "/tmp/sqc_plugins/legacy_writer_test",
        "timestamp": time.time(),
    }
    data = {
        "iv": {
            "IV": [
                {"bias_voltage": 0, "bias_smu_v": 0, "bias_smu_i": 1.23e-11},
                {"bias_voltage": 1, "bias_smu_v": 1.001, "bias_smu_i": 1.24e-11},
                {"bias_voltage": 2, "bias_smu_v": 2.025, "bias_smu_i": 1.23e-11, "temperature": 22.5},
                {"bias_voltage": 3, "bias_smu_v": 3.01, "bias_smu_i": 1.25e-11}
            ],
            "ignored": [
                {"bias_voltage": 0, "bias_smu_v": 0, "bias_smu_i": 1.13e-11},
                {"bias_voltage": 1, "bias_smu_v": 1.018, "bias_smu_i": 1.14e-11},
                {"bias_voltage": 2, "bias_smu_v": 2.003, "bias_smu_i": 1.13e-11},
                {"bias_voltage": 3, "bias_smu_v": 2.998, "bias_smu_i": 1.15e-11}
            ]
        },
        "istrip": {
            "IStrip": [
                {"strip": "A1", "rpoly_r": 1.10e-8, "istrip_i": 2.23e-11},
                {"strip": "A3", "rpoly_r": 1.11e-8, "istrip_i": 2.24e-11, "temperature": 26.1},
                {"strip": "A5", "rpoly_r": 1.12e-8, "istrip_i": 2.23e-11, "humidity": 10.4},
                {"strip": "A7", "rpoly_r": 1.13e-8, "istrip_i": 2.25e-11, "rint_r": 3.45e-3}
            ],
            "ignored": [
                {"strip": "A1", "istrip_i": 2.12e-11},
                {"strip": "A2", "istrip_i": 2.13e-11},
                {"strip": "A3", "istrip_i": 2.12e-11},
                {"strip": "A4", "istrip_i": 2.11e-11}
            ]
        }
    }
    LegacyWriter(context)(namespace, parameters, data)


def main():
    from sqc.core.geometry import Padfile

    class Context:
        ...

    padfile = Padfile()
    for i in range(8):
        padfile.add_pad(f"A{i+1}", 0, i, 0)

    context = Context()
    context.padfile = padfile

    test_legacy_writer(padfile, "/tmp/sqc_plugins/legacy_writer_test")


if __name__ == "__main__":
    main()
