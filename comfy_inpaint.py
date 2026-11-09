import csv
import os
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile

import cv2
import numpy as np
import torch

from .backend.inpaint.opencv_inpaint import OpenCVInpaint
from .model_paths import MODELS_DIR_ENV, model_path, require_model_file


STTN_WINDOW = 16


def _lama_model_path():
    directory = model_path("big-lama")
    model = directory / "big-lama.pt"
    manifest_path = require_model_file(directory / "fs_manifest.csv", "LaMa model manifest")
    with manifest_path.open(newline="", encoding="utf-8") as manifest:
        parts = [(directory / row["filename"], int(row["filesize"])) for row in csv.DictReader(manifest)]
    if model.is_file() and model.stat().st_size == sum(size for _, size in parts):
        return model

    temporary_path = None
    try:
        with NamedTemporaryFile(dir=directory, prefix=".big-lama-", suffix=".tmp", delete=False) as merged:
            temporary_path = Path(merged.name)
            for part, size in parts:
                if not part.is_file() or part.stat().st_size != size:
                    raise FileNotFoundError(
                        f"Missing or incomplete LaMa model part: {part}. "
                        f"Set {MODELS_DIR_ENV} to the model repository directory."
                    )
                with part.open("rb") as stream:
                    shutil.copyfileobj(stream, merged)
        os.replace(temporary_path, model)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return model


def _load_inpainter(method):
    if method == "OpenCV":
        return OpenCVInpaint()

    from comfy.model_management import get_torch_device

    device = get_torch_device()
    if method == "LaMa":
        from .backend.inpaint.lama_inpaint import LamaInpaint

        return LamaInpaint(device, str(_lama_model_path()))
    if method == "STTN":
        from .backend.inpaint.sttn_det_inpaint import STTNDetInpaint

        path = require_model_file(
            model_path("sttn-det", "sttn.pth"), "STTN model weights"
        )
        return STTNDetInpaint(device, path)
    raise ValueError(f"Unknown VSR inpainting method: {method}")


def _rgb_frame(image):
    pixels = image.detach().to(device="cpu", dtype=torch.float32).numpy()
    return np.rint(np.clip(pixels, 0, 1) * 255).astype(np.uint8)


def bgr_frame(image):
    return cv2.cvtColor(_rgb_frame(image), cv2.COLOR_RGB2BGR)


def _sttn_frames(inpainter, images, masks):
    height, width = masks.shape[1:]
    model_size = (inpainter.model_input_width, inpainter.model_input_height)
    resized_frames = [cv2.resize(bgr_frame(image), model_size) for image in images]
    resized_masks = [
        (cv2.resize(mask, model_size, interpolation=cv2.INTER_AREA) > 0).astype(np.uint8) * 255
        for mask in masks
    ]
    return [
        cv2.resize(frame.astype(np.uint8), (width, height))
        for frame in inpainter.inpaint(resized_frames, resized_masks)
    ]


def _inpaint_image(inpainter, method, image, mask):
    frame = _rgb_frame(image)
    height, width = mask.shape
    if method == "LaMa" and min(height, width) < 9:
        # LaMa pads to a multiple of eight and needs at least 16 pixels per axis.
        padding = ((0, max(0, 16 - height)), (0, max(0, 16 - width)))
        frame = np.pad(frame, (*padding, (0, 0)), mode="symmetric")
        mask = np.pad(mask, padding, mode="symmetric")
    return inpainter.inpaint(frame, mask)[:height, :width]


@torch.inference_mode()
def inpaint_frames(images, masks, method, progress=None):
    from comfy.model_management import throw_exception_if_processing_interrupted
    from comfy.utils import ProgressBar

    frame_count, height, width, _ = images.shape
    masks = np.broadcast_to(masks, (frame_count, height, width))
    if progress is None:
        progress = ProgressBar(frame_count)
    window = STTN_WINDOW if method == "STTN" else 1
    margin = 8 if method == "OpenCV" else max(32, min(height, width) // 8)
    result = images
    inpainter = None
    for start in range(0, frame_count, window):
        throw_exception_if_processing_interrupted()
        end = min(start + window, frame_count)
        chunk_masks = masks[start:end]
        x, y, mask_width, mask_height = cv2.boundingRect(np.bitwise_or.reduce(chunk_masks))
        if mask_width and mask_height:
            if inpainter is None:
                inpainter = _load_inpainter(method)
                result = images.clone()
            rows = slice(max(0, y - margin), min(height, y + mask_height + margin))
            columns = slice(max(0, x - margin), min(width, x + mask_width + margin))
            cropped_images = images[start:end, rows, columns]
            cropped_masks = chunk_masks[:, rows, columns]
            if method == "STTN":
                restored = _sttn_frames(inpainter, cropped_images, cropped_masks)
            else:
                restored = [_inpaint_image(inpainter, method, cropped_images[0], cropped_masks[0])]

            for index, frame in enumerate(restored):
                mask = torch.from_numpy(cropped_masks[index] > 0).to(images.device)
                pixels = torch.from_numpy(frame).to(device=images.device, dtype=images.dtype).div_(255)
                output = result[start + index, rows, columns]
                output.copy_(torch.where(mask.unsqueeze(-1), pixels, output))
        progress.update(end - start)
    return result
