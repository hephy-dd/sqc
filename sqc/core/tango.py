from comet.driver import Driver


class Tango(Driver):

    def __init__(self, resource):
        self.resource = resource

    def identify(self) -> str:
        return self.version

    @property
    def version(self) -> str:
        return self.resource.query("?version").strip()

    @property
    def statuslimit(self) -> str:
        return self.resource.query("?statuslimit").strip()

    def moa_x(self, x: float) -> None:
        self.resource.query(f"moa x {x:.3f}")

    @property
    def pos_x(self) -> float:
        return float(self.resource.query("?pos x"))
