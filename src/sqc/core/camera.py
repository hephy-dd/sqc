import logging
import threading
import time
from typing import Callable, Dict

import numpy as np

__all__ = ["camera_registry", "Camera", "DummyCamera"]

camera_registry: Dict[str, Callable] = {}


def generate_noise_with_exposure(height, width, exposure=1.0):
    """Generate random noise in RGB format and adjust its brightness based on
    exposure.

    Parameters:
    - height: The height of the image.
    - width: The width of the image.
    - exposure: Exposure setting (multiplier to adjust brightness).
                > 1.0 makes the image brighter, < 1.0 makes it darker.

    Returns:
    - A numpy array representing the noise image with adjusted brightness.
    """

    # Generate random values between 0 and 255 for an RGB image
    noise_image = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8).astype(np.float32)

    # Adjust the brightness based on the exposure setting (in-place operation)
    np.multiply(noise_image, exposure, out=noise_image)

    # Clip values to be within the [0, 255] range and convert to uint8 (in-place when possible)
    return np.clip(noise_image, 0, 255, out=noise_image).astype(np.uint8)



def exposure_to_multiplier(exposure: float) -> float:
    """Convert an exposure value in the range [0, 250] to a brightness multiplier.

    Parameters:
    - exposure: Exposure value in the range [0, 250]

    Returns:
    - Brightness multiplier.
    """
    # Define the minimum and maximum multipliers
    min_multiplier = 0.5
    max_multiplier = 2.0

    # Linearly interpolate between the minimum and maximum multipliers
    multiplier = min_multiplier + (exposure/250.0) * (max_multiplier - min_multiplier)

    return multiplier


class Camera:

    def __init__(self, config: dict) -> None:
        self.frame_handlers: list = []

    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def set_exposure(self, exposure: float) -> None:
        ...

    def add_frame_handler(self, handler) -> None:
        self.frame_handlers.append(handler)

    def handle_frame(self, image_data) -> None:
        for handler in self.frame_handlers:
            handler(image_data)

    def shutdown(self):
        ...


class DummyCamera(Camera):

    def __init__(self, config):
        super().__init__(config)
        self.free_running = False
        self.frame_thread = None
        self.exposure = 30

    def start(self):
        self.free_running = True
        self.frame_thread = threading.Thread(target=self.capture_frames)
        self.frame_thread.start()

    def stop(self):
        self.free_running = False

    def set_exposure(self, exposure):
        self.exposure = exposure

    def shutdown(self):
        self.free_running = False
        if self.frame_thread:
            self.frame_thread.join()

    def capture_frames(self):
        try:
            target_frame_rate = 20.0
            while self.free_running:
                t = time.monotonic()
                width = 768 * 4
                height = 512 * 4
                exposure = exposure_to_multiplier(self.exposure)
                image_data = generate_noise_with_exposure(height, width, exposure)
                self.handle_frame(image_data)
                waiting_time = max((1 / target_frame_rate) - (time.monotonic() - t), 0)
                time.sleep(waiting_time)
        except Exception as exc:
            logging.exception(exc)
