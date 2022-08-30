import pytest

from sqc import measurements
from sqc.context import Context

from .test_station import FakeStation


@pytest.fixture
def context():
    return Context(FakeStation())


class TestMeasurement:

    def test_iv(self, context):
        m = measurements.IVMeasurement(context, "iv", "IV", "", {
            "voltage_end": "-800 V",
            "voltage_step": "10 V",
            "compliance": "40 uA",
            "waiting_time": "0 s",
        })
        m.initialize()
        m.acquire()
        m.finalize()
        data = context.data.get("").get("iv").get("IV")
        assert len(data) == 81

    def test_cv(self, context):
        m = measurements.CVMeasurement(context, "cv", "CV", "", {
            "voltage_end": "-800 V",
            "voltage_step": "20 V",
            "waiting_time": "0 s",
            "compliance": "40 uA",
        })
        m.initialize()
        m.acquire()
        m.finalize()
        data = context.data.get("").get("cv").get("CV")
        assert len(data) == 41

    def test_stripscan(self, context):
        m = measurements.StripscanMeasurement(context, "strips", "Strips", "", {
            "bias_voltage": "-800 V",
            "bias_compliance": "40 uA"
        })
        m.initialize()
        m.finalize()

    def test_istrip(self, context):
        m = measurements.IStripMeasurement(context, "istrip", "Istrip", "", {})
        m.initialize()
        m.finalize()

    def test_rpoly(self, context):
        m = measurements.RPolyMeasurement(context, "rpoly", "Rpoly", "", {
            "lv_channels_istrip": ["1A05"]
        })
        m.initialize()
        m.finalize()

    def test_idiel(self, context):
        m = measurements.IDielMeasurement(context, "idiel", "Idiel", "", {})
        m.initialize()
        m.finalize()

    def test_cac(self, context):
        m = measurements.CacMeasurement(context, "cac", "Cac", "", {})
        m.initialize()
        m.finalize()

    def test_cint(self, context):
        m = measurements.CIntMeasurement(context, "cint", "Cint", "", {})
        m.initialize()
        m.finalize()

    def test_rint(self, context):
        m = measurements.RIntMeasurement(context, "rint", "Rint", "", {})
        m.initialize()
        m.finalize()

    def test_idark(self, context):
        m = measurements.IDarkMeasurement(context, "idark", "Idark", "", {})
        m.initialize()
        m.finalize()
