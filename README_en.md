# ComfyUI Video Subtitle Remover

[简体中文](README.md) | English

Remove hardcoded subtitles and watermarks in ComfyUI. Choose LaMa for frame-by-frame inpainting, STTN for inpainting with neighboring frames, or OpenCV for quick cleanup of small regions. Model weights are bundled.

## Install in a ComfyUI Pod

In the Pod terminal, change to the ComfyUI root directory. Use the same Python environment that runs ComfyUI.

```sh
git clone --depth 1 https://github.com/allenflux/ComfyUI-Video-Subtitle-Remover.git custom_nodes/video-subtitle-remover
python -m pip install -r custom_nodes/video-subtitle-remover/requirements.txt
```

Restart the ComfyUI service and search for `VSR Remove Subtitles` or `VSR Remove Watermark`. See the [ComfyUI installation guide](https://docs.comfy.org/installation/install_custom_node) for environment-specific instructions.

If the Pod can already import `cv2` or `onnxruntime`, install only the missing package from `requirements.txt` to avoid mixing OpenCV or ONNX Runtime variants in the same environment.

To update an existing checkout, run these commands from the ComfyUI root directory and restart the service.

```sh
git -C custom_nodes/video-subtitle-remover pull --ff-only
python -m pip install -r custom_nodes/video-subtitle-remover/requirements.txt
```

## Nodes and workflow

| Node | Usage |
| --- | --- |
| `VSR Remove Subtitles` | Takes images or video frames. By default it detects subtitles in the bottom quarter and returns restored frames and a subtitle mask. Adjust the search region and mask padding or choose `rectangle` to restore the entire selection. |
| `VSR Remove Watermark` | Takes images or video frames. Select a rectangle or connect a frame-sized `MASK`. Supply one shared mask or one per frame. A connected mask takes precedence over the rectangle. |

Rectangle coordinates start at the upper-left corner. Set `x`, `y`, `width`, and `height` as proportions of the frame dimensions. On first use, LaMa assembles its model parts in the model directory, which needs to be writable.

Drag the [example workflow](workflows/video_cleanup.json) into ComfyUI, then upload and select your own clip in `Load Video`. The example removes subtitles by default. Disable bypass on the watermark node to remove watermarks in the same run. `Create Video` receives the source audio and frame rate, and `Save Video` writes the result. The workflow loads the video as a batch of images, so start with a short clip to check the selected regions.

Based on [Video Subtitle Remover](https://github.com/YaoFANGUK/video-subtitle-remover) and distributed under the [Apache 2.0 license](LICENSE).
