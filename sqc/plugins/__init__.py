__all__ = ["PluginManager"]


class PluginManager:

    def __init__(self) -> None:
        self.plugins: list = []

    def register_plugin(self, plugin: object) -> None:
        self.plugins.append(plugin)

    def install_plugins(self) -> None:
        for plugin in self.plugins:
            if hasattr(plugin, "install"):
                plugin.install()

    def uninstall_plugins(self) -> None:
        for plugin in self.plugins:
            if hasattr(plugin, "uninstall"):
                plugin.uninstall()

    def handle(self, event_name: str, *args, **kwargs) -> None:
        for plugin in self.plugins:
            if hasattr(plugin, event_name):
                getattr(plugin.event_name)(*args, **kwargs)
