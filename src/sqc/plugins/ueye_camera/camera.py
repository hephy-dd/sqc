import ctypes
import logging
import threading
import time

import numpy as np
from pyueye import ueye

from sqc.core.camera import Camera as BaseCamera

__all__ = ["UEyeCamera"]


def get_bits_per_pixel(color_mode):
    """
    returns the number of bits per pixel for the given color mode
    raises exception if color mode is not is not in dict
    """

    return {
        ueye.IS_CM_SENSOR_RAW8: 8,
        ueye.IS_CM_SENSOR_RAW10: 16,
        ueye.IS_CM_SENSOR_RAW12: 16,
        ueye.IS_CM_SENSOR_RAW16: 16,
        ueye.IS_CM_MONO8: 8,
        ueye.IS_CM_RGB8_PACKED: 24,
        ueye.IS_CM_BGR8_PACKED: 24,
        ueye.IS_CM_RGBA8_PACKED: 32,
        ueye.IS_CM_BGRA8_PACKED: 32,
        ueye.IS_CM_BGR10_PACKED: 32,
        ueye.IS_CM_RGB10_PACKED: 32,
        ueye.IS_CM_BGRA12_UNPACKED: 64,
        ueye.IS_CM_BGR12_UNPACKED: 48,
        ueye.IS_CM_BGRY8_PACKED: 32,
        ueye.IS_CM_BGR565_PACKED: 16,
        ueye.IS_CM_BGR5_PACKED: 16,
        ueye.IS_CM_UYVY_PACKED: 16,
        ueye.IS_CM_UYVY_MONO_PACKED: 16,
        ueye.IS_CM_UYVY_BAYER_PACKED: 16,
        ueye.IS_CM_CBYCRY_PACKED: 16,
    }[color_mode]


def check(ret):
    if ret != ueye.IS_SUCCESS:
        raise RuntimeError(ret)


class ImageBuffer:
    def __init__(self):
        self.mem_ptr = ueye.c_mem_p()
        self.mem_id = ueye.int()


class Rect:
    def __init__(self, x=0, y=0, width=0, height=0):
        self.x = x
        self.y = y
        self.width = width
        self.height = height


class CameraInfo:

    def __init__(self, info):
        self.SerNo = info.SerNo.decode("utf-8")
        self.ID = info.ID.decode("utf-8")
        self.Version = info.Version.decode("utf-8")
        self.Date = info.Date.decode("utf-8")
        self.Select = int(format(info.Select))
        self.Type = int(format(info.Type))
        self.Reserved = info.Reserved.decode("utf-8")


class SensorInfo:

    def __init__(self, info):
        self.SensorID = int(info.SensorID)
        self.strSensorName = info.strSensorName.decode("utf-8")
        self.nColorMode = int.from_bytes(info.nColorMode, "big")
        self.nMaxWidth = info.nMaxWidth.value
        self.nMaxHeight = info.nMaxHeight.value
        self.bMasterGain = info.bMasterGain.value
        self.bRGain = info.bRGain.value
        self.bGGain = info.bGGain.value
        self.bBGain = info.bBGain.value
        self.bGlobShutter = info.bGlobShutter.value
        self.wPixelSize = info.wPixelSize.value
        self.nUpperLeftBayerPixel = int.from_bytes(info.nUpperLeftBayerPixel, "big")
        self.Reserved = info.Reserved.decode("utf-8")


class MemoryInfo:
    def __init__(self, h_cam, img_buff):
        self.x = ueye.int()
        self.y = ueye.int()
        self.bits = ueye.int()
        self.pitch = ueye.int()
        self.img_buff = img_buff

        rect_aoi = ueye.IS_RECT()
        check(ueye.is_AOI(h_cam, ueye.IS_AOI_IMAGE_GET_AOI, rect_aoi, ueye.sizeof(rect_aoi)))
        self.width = rect_aoi.s32Width.value
        self.height = rect_aoi.s32Height.value

        check(ueye.is_InquireImageMem(
            h_cam,
            self.img_buff.mem_ptr,
            self.img_buff.mem_id,
            self.x,
            self.y,
            self.bits,
            self.pitch,
        ))


class ImageData:
    def __init__(self, h_cam, img_buff):
        self.h_cam = h_cam
        self.img_buff = img_buff
        self.mem_info = MemoryInfo(h_cam, img_buff)
        self.color_mode = ueye.is_SetColorMode(h_cam, ueye.IS_GET_COLOR_MODE)
        self.bits_per_pixel = get_bits_per_pixel(self.color_mode)
        self.array = ueye.get_data(
            self.img_buff.mem_ptr,
            self.mem_info.width,
            self.mem_info.height,
            self.mem_info.bits,
            self.mem_info.pitch,
            True,
        )

    def as_1d_image(self):
        channels = int((7 + self.bits_per_pixel) / 8)
        if channels > 1:
            return np.reshape(self.array, (self.mem_info.height, self.mem_info.width, channels))
        else:
            return np.reshape(self.array, (self.mem_info.height, self.mem_info.width))

    def unlock(self):
        check(ueye.is_UnlockSeqBuf(self.h_cam, self.img_buff.mem_id, self.img_buff.mem_ptr))


class Camera:

    def __init__(self, device_id=0):
        self.h_cam = ueye.HIDS(device_id)
        self.img_buffers = []

    def handle(self):
        return self.h_cam

    def init(self):
        check(ueye.is_InitCamera(self.h_cam, None))

    def exit(self):
        check(ueye.is_ExitCamera(self.h_cam))
        self.h_cam = None

    def alloc(self, buffer_count=3):
        rect = self.get_aoi()
        bpp = get_bits_per_pixel(self.get_colormode())

        for buff in self.img_buffers:
            check(ueye.is_FreeImageMem(self.h_cam, buff.mem_ptr, buff.mem_id))

        self.img_buffers.clear()

        for i in range(buffer_count):
            buff = ImageBuffer()
            ueye.is_AllocImageMem(self.h_cam, rect.width, rect.height, bpp, buff.mem_ptr, buff.mem_id)

            check(ueye.is_AddToSequence(self.h_cam, buff.mem_ptr, buff.mem_id))

            self.img_buffers.append(buff)

        ueye.is_InitImageQueue(self.h_cam, 0)

    def get_camera_info(self):
        info = ueye.CAMINFO()
        check(ueye.is_GetCameraInfo(self.h_cam, info))
        return CameraInfo(info)

    def get_sensor_info(self):
        info = ueye.SENSORINFO()
        check(ueye.is_GetSensorInfo(self.h_cam, info))
        return SensorInfo(info)

    def reset_to_default(self):
        check(ueye.is_ResetToDefault(self.h_cam))

    def set_auto_parameter(self, param):
        check(ueye.is_SetAutoParameter(
            self.h_cam,
            ctypes.c_int(param),
            ctypes.c_double(1),
            ctypes.c_double(0)
        ))

    def get_aoi(self):
        rect_aoi = ueye.IS_RECT()
        check(ueye.is_AOI(self.h_cam, ueye.IS_AOI_IMAGE_GET_AOI, rect_aoi, ueye.sizeof(rect_aoi)))

        return Rect(
            rect_aoi.s32X.value,
            rect_aoi.s32Y.value,
            rect_aoi.s32Width.value,
            rect_aoi.s32Height.value,
        )

    def set_aoi(self, x, y, width, height):
        rect_aoi = ueye.IS_RECT()
        rect_aoi.s32X = ueye.int(x)
        rect_aoi.s32Y = ueye.int(y)
        rect_aoi.s32Width = ueye.int(width)
        rect_aoi.s32Height = ueye.int(height)

        check(ueye.is_AOI(self.h_cam, ueye.IS_AOI_IMAGE_SET_AOI, rect_aoi, ueye.sizeof(rect_aoi)))

    def set_binning(self, mode):
        check(ueye.is_SetBinning(self.h_cam, mode))

    def set_fps(self, fps):
        # checking available fps
        mini, maxi = self.get_fps_range()
        fps = min(maxi, max(mini, fps))
        fps = ueye.c_double(fps)
        new_fps = ueye.c_double()
        check(ueye.is_SetFrameRate(self.h_cam, fps, new_fps))
        return float(new_fps)

    def get_fps(self):
        fps = ueye.c_double()
        check(ueye.is_GetFramesPerSecond(self.h_cam, fps))
        return float(fps)

    def get_fps_range(self):
        mini = ueye.c_double()
        maxi = ueye.c_double()
        interv = ueye.c_double()
        check(ueye.is_GetFrameTimeRange(self.h_cam, mini, maxi, interv))
        return [float(1 / maxi), float(1 / mini)]

    def set_exposure(self, exposure):
        new_exposure = ueye.c_double(exposure)
        check(ueye.is_Exposure(self.h_cam, ueye.IS_EXPOSURE_CMD_SET_EXPOSURE, new_exposure, 8))
        return float(new_exposure)

    def get_exposure(self):
        exposure = ueye.c_double()
        check(ueye.is_Exposure(self.h_cam, ueye.IS_EXPOSURE_CMD_GET_EXPOSURE, exposure, 8))
        return float(exposure)

    def set_exposure_auto(self, toggle):
        value = ueye.c_double(toggle)
        value_to_return = ueye.c_double()
        check(ueye.is_SetAutoParameter(self.h_cam, ueye.IS_SET_ENABLE_AUTO_SHUTTER, value, value_to_return))

    def capture_video(self, wait=False):
        wait_param = ueye.IS_WAIT if wait else ueye.IS_DONT_WAIT
        return ueye.is_CaptureVideo(self.h_cam, wait_param)

    def stop_video(self):
        return ueye.is_StopLiveVideo(self.h_cam, ueye.IS_FORCE_VIDEO_STOP)

    def freeze_video(self, wait=False):
        wait_param = ueye.IS_WAIT if wait else ueye.IS_DONT_WAIT
        return ueye.is_FreezeVideo(self.h_cam, wait_param)

    def set_colormode(self, colormode):
        check(ueye.is_SetColorMode(self.h_cam, colormode))

    def get_colormode(self):
        ret = ueye.is_SetColorMode(self.h_cam, ueye.IS_GET_COLOR_MODE)
        return ret

    def get_format_list(self):
        count = ueye.UINT()
        check(
            ueye.is_ImageFormat(
                self.h_cam, ueye.IMGFRMT_CMD_GET_NUM_ENTRIES, count, ueye.sizeof(count)
            )
        )
        format_list = ueye.IMAGE_FORMAT_LIST(ueye.IMAGE_FORMAT_INFO * count.value)
        format_list.nSizeOfListEntry = ueye.sizeof(ueye.IMAGE_FORMAT_INFO)
        format_list.nNumListElements = count.value
        check(
            ueye.is_ImageFormat(
                self.h_cam,
                ueye.IMGFRMT_CMD_GET_LIST,
                format_list,
                ueye.sizeof(format_list),
            )
        )
        return format_list

    def configure(self):
        sensor_info = self.get_sensor_info()
        self.reset_to_default()
        self.set_colormode(ueye.IS_CM_BGR8_PACKED)
        self.set_aoi(0, 0, sensor_info.nMaxWidth, sensor_info.nMaxHeight)
        self.set_binning(ueye.IS_BINNING_2X_VERTICAL | ueye.IS_BINNING_2X_HORIZONTAL)
        fmin, fmax = self.get_fps_range()
        self.set_fps(min(fmax, 25))
        self.set_auto_parameter(ueye.IS_SET_ENABLE_AUTO_WHITEBALANCE)
        self.set_auto_parameter(ueye.IS_SET_AUTO_WB_AOI)
        self.set_auto_parameter(ueye.IS_SET_AUTO_BRIGHT_AOI)


class UEyeCamera(BaseCamera):

    def __init__(self, config) -> None:
        super().__init__(config)
        self.free_running: bool = False
        self.timeout: int = 1000
        self.camera = Camera(config.get("device_id", 0))
        self.camera.init()
        self.camera.configure()
        self.camera.alloc()
        self.frame_thread = threading.Thread(target=self.capture_frames)

    def start(self) -> None:
        self.free_running = True
        self.camera.capture_video()
        self.frame_thread.start()

    def stop(self) -> None:
        self.camera.stop_video()
        self.free_running = False

    def set_exposure(self, exposure: float) -> None:
        self.camera.set_exposure(exposure)

    def shutdown(self) -> None:
        self.free_running = False
        self.camera.exit()

    def capture_frames(self) -> None:
        while self.free_running:
            try:
                img_buffer = ImageBuffer()
                ret = ueye.is_WaitForNextImage(
                    self.camera.handle(), self.timeout, img_buffer.mem_ptr, img_buffer.mem_id
                )
                if ret == ueye.IS_SUCCESS:
                    image_data = ImageData(self.camera.handle(), img_buffer)
                    frame_data = image_data.as_1d_image()
                    image_data.unlock()
                    self.handle_frame(frame_data)
            except Exception as exc:
                logging.exception(exc)
                time.sleep(1.0)  # throttle in case of error
