import math

import numpy as np
import torch


CATEGORY = "video/video-subtitle-remover"
METHODS = ["LaMa", "STTN", "OpenCV"]


def _rectangle_inputs(defaults):
    return {
        name: ("FLOAT", {"default": value, "min": 0.0, "max": 1.0, "step": 0.001})
        for name, value in zip(("x", "y", "width", "height"), defaults)
    }


def _image_shape(images):
    if images.ndim != 4 or images.shape[-1] != 3 or min(images.shape) == 0:
        raise ValueError("Expected a nonempty IMAGE batch with shape [frames, height, width, 3].")
    return images.shape[:3]


def _rectangle(image_width, image_height, x, y, width, height):
    if not (0 <= x < 1 and 0 <= y < 1 and 0 < width <= 1 and 0 < height <= 1):
        raise ValueError("Use a normalized rectangle with its top-left corner inside the image and a positive size.")
    left = math.floor(x * image_width)
    top = math.floor(y * image_height)
    right = min(image_width, math.ceil((x + width) * image_width))
    bottom = min(image_height, math.ceil((y + height) * image_height))
    return slice(top, bottom), slice(left, right)


def _rectangle_mask(image_shape, rectangle):
    mask = np.zeros((1, *image_shape), dtype=np.uint8)
    rows, columns = rectangle
    mask[0, rows, columns] = 255
    return mask


class VSRRemoveWatermark:
    CATEGORY = CATEGORY
    FUNCTION = "remove"
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    DESCRIPTION = "Remove a logo or watermark from image or video frames using a rectangle or mask."

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "method": (METHODS,),
                **_rectangle_inputs((0.8, 0.0, 0.2, 0.2)),
            },
            "optional": {"mask": ("MASK",)},
        }

    def remove(self, images, method, x, y, width, height, mask=None):
        from .comfy_inpaint import inpaint_frames

        frame_count, image_height, image_width = _image_shape(images)
        if mask is None:
            rectangle = _rectangle(image_width, image_height, x, y, width, height)
            masks = _rectangle_mask((image_height, image_width), rectangle)
        else:
            if mask.ndim == 2:
                mask = mask.unsqueeze(0)
            if (mask.ndim != 3 or mask.shape[0] not in (1, frame_count)
                    or mask.shape[-2:] != (image_height, image_width)):
                raise ValueError(
                    f"MASK must match the image size ({image_width}x{image_height}) "
                    f"and contain 1 mask or {frame_count} masks."
                )
            masks = (mask > 0.5).cpu().numpy().astype(np.uint8) * 255
        return (inpaint_frames(images, masks, method),)


class VSRRemoveSubtitles:
    CATEGORY = CATEGORY
    FUNCTION = "remove"
    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("images", "mask")
    DESCRIPTION = "Remove burned-in subtitles by detecting text inside a search rectangle or masking the rectangle."

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "method": (METHODS,),
                "detection": (["auto", "rectangle"],),
                **_rectangle_inputs((0.0, 0.75, 1.0, 0.25)),
                "padding": ("INT", {"default": 8, "min": 0, "max": 128}),
            },
        }

    def remove(self, images, method, detection, x, y, width, height, padding):
        from comfy.model_management import throw_exception_if_processing_interrupted
        from comfy.utils import ProgressBar
        from .comfy_inpaint import bgr_frame, inpaint_frames

        frame_count, image_height, image_width = _image_shape(images)
        rectangle = _rectangle(image_width, image_height, x, y, width, height)
        if detection == "auto":
            from .comfy_ocr import detect_text_mask

            masks = np.zeros((frame_count, image_height, image_width), dtype=np.uint8)
            rows, columns = rectangle
            progress = ProgressBar(frame_count * 2)
            for index, image in enumerate(images):
                throw_exception_if_processing_interrupted()
                masks[index, rows, columns] = detect_text_mask(bgr_frame(image[rows, columns]), padding)
                progress.update(1)
        else:
            masks = _rectangle_mask((image_height, image_width), rectangle)
            progress = ProgressBar(frame_count)

        result = inpaint_frames(images, masks, method, progress)
        mask_output = torch.from_numpy(masks).float().div_(255)
        return result, mask_output.expand(frame_count, -1, -1)
