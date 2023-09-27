import logging

from sqc.core.camera import camera_registry
from sqc.plugins import Plugin

__all__ = ["UEyeCameraPlugin"]

logger = logging.getLogger(__name__)


def load_camera_cls():
    try:
        from .camera import UEyeCamera
    except Exception as exc:
        UEyeCamera = None
        logger.exception(exc)
        logger.error("Failed to load ueye camera, check if UEye drivers are installed.")
    return UEyeCamera


class UEyeCameraPlugin(Plugin):

    def create_camera(self, config):
        return load_camera_cls()(config)

    def install(self, window):
        if load_camera_cls() is not None:
            camera_registry["ueye"] = self.create_camera

    def uninstall(self, window):
        if "ueye" in camera_registry:
            del camera_registry["ueye"]
