import numpy as np
import torch

from .utils.lama_util import prepare_img_and_mask


class LamaInpaint:
    def __init__(self, device, model_path):
        self.model = torch.jit.load(model_path, map_location=device).eval()
        self.device = device

    @torch.inference_mode()
    def inpaint(self, image, mask):
        height, width = image.shape[:2]
        image, mask = prepare_img_and_mask(image, mask, self.device)
        restored = self.model(image, mask)[0].permute(1, 2, 0).cpu().numpy()
        return np.clip(restored[:height, :width] * 255, 0, 255).astype(np.uint8)
