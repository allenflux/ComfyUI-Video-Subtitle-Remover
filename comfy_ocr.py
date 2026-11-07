from functools import cache
from pathlib import Path

import cv2
import numpy as np


MODEL_PATH = Path(__file__).resolve().parent / "backend/models/V4/ch_det_fast/inference.onnx"
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


@cache
def _detector_session():
    try:
        import onnxruntime
    except ImportError as error:
        raise RuntimeError("Automatic text detection requires onnxruntime in the ComfyUI environment.") from error

    if not MODEL_PATH.is_file():
        raise FileNotFoundError(f"Missing PP-OCRv4 text detector weights: {MODEL_PATH}")
    options = onnxruntime.SessionOptions()
    options.intra_op_num_threads = 2
    session = onnxruntime.InferenceSession(
        str(MODEL_PATH), sess_options=options, providers=["CPUExecutionProvider"]
    )
    return session, session.get_inputs()[0].name


def _box_score(probability, box):
    height, width = probability.shape
    left, top = np.maximum(np.floor(box.min(axis=0)).astype(int), (0, 0))
    right, bottom = np.minimum(np.ceil(box.max(axis=0)).astype(int), (width - 1, height - 1))
    interior = np.zeros((bottom - top + 1, right - left + 1), dtype=np.uint8)
    cv2.fillConvexPoly(interior, (box - (left, top)).astype(np.int32), 1)
    return cv2.mean(probability[top:bottom + 1, left:right + 1], mask=interior)[0]


def detect_text_mask(bgr_crop, padding):
    """Return an H×W uint8 mask with 255 over detected text and 0 elsewhere."""
    height, width = bgr_crop.shape[:2]
    mask = np.zeros((height, width), dtype=np.uint8)
    if not mask.size:
        return mask

    # PP-OCRv4 uses a 32-pixel stride and PaddleOCR's DB inference defaults.
    ratio = min(1.0, 960 / max(height, width))
    resize_width = max(32, round(width * ratio / 32) * 32)
    resize_height = max(32, round(height * ratio / 32) * 32)
    resized = cv2.resize(bgr_crop, (resize_width, resize_height))
    normalized = (resized.astype(np.float32) / 255 - MEAN) / STD
    input_tensor = np.ascontiguousarray(normalized.transpose(2, 0, 1)[None])

    session, input_name = _detector_session()
    probability = session.run(None, {input_name: input_tensor})[0][0, 0]
    contours, _ = cv2.findContours(
        (probability > 0.3).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE
    )
    map_height, map_width = probability.shape
    scale = np.array([width / map_width, height / map_height], dtype=np.float32)
    for contour in contours[:1000]:
        center, (box_width, box_height), angle = cv2.minAreaRect(contour)
        if min(box_width, box_height) < 3:
            continue
        box = cv2.boxPoints((center, (box_width, box_height), angle))
        if _box_score(probability, box) < 0.6:
            continue

        # DB offsets the min-area rectangle by 1.5 × area / perimeter and
        # takes its enclosing rectangle. Each side grows by twice that distance.
        growth = 1.5 * box_width * box_height / (box_width + box_height)
        expanded_size = (box_width + growth, box_height + growth)
        if min(expanded_size) >= 5:
            expanded_box = cv2.boxPoints((center, expanded_size, angle))
            cv2.fillConvexPoly(mask, np.rint(expanded_box * scale).astype(np.int32), 255)

    if padding and mask.any():
        diameter = 2 * padding + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (diameter, diameter))
        mask = cv2.dilate(mask, kernel)
    return mask
