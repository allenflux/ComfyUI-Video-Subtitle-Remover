# ComfyUI Video Subtitle Remover

简体中文 | [English](README_en.md)

在 ComfyUI 中去除视频硬字幕和水印。支持 LaMa 逐帧修复、STTN 利用相邻帧修复，以及 OpenCV 快速修复小区域。模型权重随仓库提供。

## 安装到 ComfyUI Pod

在 Pod 终端进入 ComfyUI 根目录，用启动 ComfyUI 的同一个 Python 环境运行以下命令。

```sh
git clone --depth 1 https://github.com/allenflux/ComfyUI-Video-Subtitle-Remover.git custom_nodes/video-subtitle-remover
python -m pip install -r custom_nodes/video-subtitle-remover/requirements.txt
```

重启 ComfyUI 服务后，搜索 `VSR Remove Subtitles` 或 `VSR Remove Watermark`。可参考 [ComfyUI 官方安装说明](https://docs.comfy.org/installation/install_custom_node)。

若 Pod 已有可导入的 `cv2` 或 `onnxruntime`，按 `requirements.txt` 只安装缺少的包，以免同一环境混装不同版本的 OpenCV 或 ONNX Runtime。

如果已克隆过此仓库，在 ComfyUI 根目录运行以下命令，再重启服务。

```sh
git -C custom_nodes/video-subtitle-remover pull --ff-only
python -m pip install -r custom_nodes/video-subtitle-remover/requirements.txt
```

## 节点与工作流

| 节点 | 用法 |
| --- | --- |
| `VSR Remove Subtitles` | 接收图像或视频帧。默认在画面底部四分之一自动检测字幕，输出修复帧和字幕遮罩。可调整检测范围和遮罩扩张像素，或用 `rectangle` 修复整块选区。 |
| `VSR Remove Watermark` | 接收图像或视频帧。通过矩形框选水印，或连接与画面同尺寸的 `MASK`。可共用一张遮罩，也可逐帧提供。连接后优先使用遮罩。 |

矩形的 `x`、`y` 从画面左上角开始，与 `width`、`height` 一样按画面尺寸的比例填写。首次运行 LaMa 会在模型目录合并分片，因此该目录需要可写。

将[示例工作流](workflows/video_cleanup.json)拖入 ComfyUI，在 `Load Video` 中上传并选择自己的视频。示例默认去字幕，取消去水印节点的旁路后即可同时处理水印。`Create Video` 接回原音频和帧率，再由 `Save Video` 保存。工作流将视频拆成一批图像，可先用短视频确认选区和效果。

## 集群部署

- 在所有会执行此工作流的 ComfyUI worker 上使用同一节点提交。可以把节点目录和 Python 依赖加入现有 ComfyUI 镜像，然后用该镜像部署各 Pod。
- 模型权重随节点目录分发。使用 LaMa 时，确保每个 worker 能在模型目录合并分片，或在镜像构建时预先合并。
- 输入视频必须能在接收任务的 worker 的 ComfyUI `input` 目录读取。使用 Pod 本地文件时，把输入、任务提交和结果查询交给同一 worker。使用共享输出目录时，为每个任务设置唯一的 `SaveVideo.inputs.filename_prefix`。

节点随现有 ComfyUI 进程加载，任务由 ComfyUI 的原生工作流队列执行。

## 通过工作流触发

1. 在 ComfyUI 中打开示例工作流，选好输入视频和处理节点，再通过 `Export (API)` 导出为 `workflow_api.json`。仓库里的 `video_cleanup.json` 是画布文件，用来在界面中打开。
2. 每次提交前，将 API JSON 中 `class_type` 为 `LoadVideo` 的节点的 `inputs.file` 设置为目标 worker 的 `input` 目录中的文件名，例如 `job-001.mp4`。
3. 把 API JSON 放进 `prompt` 字段，提交到目标 worker 的 `POST /prompt`。用返回的 `prompt_id` 向同一 worker 查询 `GET /history/{prompt_id}`。完成后可从输出目录取文件，或用 `SaveVideo` 输出记录的 `filename`、`subfolder` 和 `type` 调用 `GET /view` 下载。[ComfyUI 原生 API 文档](https://docs.comfy.org/development/comfyui-server/comms_routes)

```sh
COMFYUI_URL=http://127.0.0.1:8188
python -c 'import json, sys; print(json.dumps({"prompt": json.load(sys.stdin)}))' \
  < workflow_api.json | curl -fsS "$COMFYUI_URL/prompt" \
  -H 'Content-Type: application/json' --data-binary @-
```

本项目基于 [Video Subtitle Remover](https://github.com/YaoFANGUK/video-subtitle-remover)，按 [Apache 2.0](LICENSE) 许可发布。
