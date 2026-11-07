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

## Deploy to a ComfyUI cluster

- Pin the same repository commit and ComfyUI version on every worker eligible to run the workflow. Install the node and its dependencies in the worker image, or mount the same checkout under `custom_nodes` and install its Python dependencies on every worker. After restart, check for `VSRRemoveSubtitles` and `VSRRemoveWatermark` at `GET /object_info`.
- Make the source video available in the executing worker's ComfyUI input directory. Use a shared volume or stage the file on the worker before submission. The workflow extracts audio from that same video. Configure persistent output storage or collect the video from the worker before the Pod is replaced. With shared output storage, assign a unique `SaveVideo.inputs.filename_prefix` to each job.
- Send submission and history requests to the same ComfyUI worker because the queue and history belong to that instance. For read-only node mounts, assemble the LaMa model in the image before deployment or give the model directory writable storage.

The nodes load in the existing ComfyUI process and run through its built-in workflow queue.

## Submit a workflow through the API

1. Open `workflows/video_cleanup.json` in the editor, select a source video, and choose **File → Export (API)**. Save the export as `workflow_api.json`. For each job, set the `LoadVideo` node's `inputs.file` to the video available on the worker.
2. Wrap the exported node map in a `prompt` field and submit it to the ComfyUI worker. Replace the URL below with the worker's endpoint.

   ```sh
   COMFYUI_URL=http://127.0.0.1:8188
   python -c 'import json, sys; print(json.dumps({"prompt": json.load(sys.stdin)}))' \
     < workflow_api.json | curl -fsS "$COMFYUI_URL/prompt" \
     -H 'Content-Type: application/json' --data-binary @-
   ```

3. Use the returned `prompt_id` with `GET /history/{prompt_id}` to check completion. Use the `SaveVideo` output's `filename`, `subfolder`, and `type` with `GET /view` to download the file, or retrieve it from the output volume. [ComfyUI server routes](https://docs.comfy.org/development/comfyui-server/comms_routes)

Based on [Video Subtitle Remover](https://github.com/YaoFANGUK/video-subtitle-remover) and distributed under the [Apache 2.0 license](LICENSE).
