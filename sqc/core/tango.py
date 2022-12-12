from comet.driver import Driver


class Tango(Driver):
    """Driver for the TANGO instruction set."""

    def __init__(self, resource) -> None:
        self.resource = resource

    def identify(self) -> str:
        return self.version

    @property
    def version(self) -> str:
        """Return version information."""
        return self.resource.query("?version").strip()

    @property
    def status(self) -> str:
        """Return 'OK' or 'ERR n' in case of an error."""
        return self.resource.query("?status").strip()

    @property
    def statuslimit(self) -> str:
        """Return axes state as 16 character string."""
        return self.resource.query("?statuslimit").strip()

    def moa_x(self, x: float) -> None:
        """Absolute move x axis to position."""
        self.resource.query(f"moa x {x:.3f}")

    @property
    def pos_x(self) -> float:
        """Return absolute position of a axis."""
        return float(self.resource.query("?pos x"))

    @property
    def calst_x(self) -> int:
        """Return 3 if cal and rm are executed."""
        return int(self.resource.query("?calst x"))

    @property
    def statusaxis_x(self) -> str:
        """Return 'M' if axis is moving."""
        return self.resource.query("?statusaxis x").strip()
