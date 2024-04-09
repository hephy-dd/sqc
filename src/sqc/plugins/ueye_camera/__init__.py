import logging

from sqc.core.camera import camera_registry

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


def create_camera(config):
    return load_camera_cls()(config)


class UEyeCameraPlugin:

    def install(self, window) -> None:
        if load_camera_cls() is not None:
            camera_registry["ueye"] = create_camera

    def uninstall(self, window) -> None:
        if "ueye" in camera_registry:
            del camera_registry["ueye"]

    def beforePreferences(self, dialog) -> None:
        dialog.cameraWidget.addCamera("ueye")
