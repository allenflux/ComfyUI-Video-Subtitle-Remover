import numpy as np
import torch


# Source https://github.com/advimman/lama
def pad_img_to_modulo(image, modulo):
    height, width = image.shape[-2:]
    return np.pad(
        image,
        ((0, 0), (0, -height % modulo), (0, -width % modulo)),
        mode="symmetric",
    )


def prepare_img_and_mask(image, mask, device):
    image = pad_img_to_modulo(image.transpose(2, 0, 1).astype(np.float32) / 255, 8)
    mask = pad_img_to_modulo((mask[None] > 0).astype(np.int64), 8)
    image = torch.from_numpy(image).unsqueeze(0).to(device)
    mask = torch.from_numpy(mask).unsqueeze(0).to(device)
    return image, mask
