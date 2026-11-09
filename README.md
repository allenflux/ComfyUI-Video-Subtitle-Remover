# ComfyUI Video Subtitle Remover

简体中文 | [English](README_en.md)

在 ComfyUI 中去除视频硬字幕和水印。支持 LaMa 逐帧修复、STTN 利用相邻帧修复，以及 OpenCV 快速修复小区域。模型权重由独立的 `video-subtitle-remover-models` 项目提供。

## 安装到 ComfyUI Pod

在 Pod 终端进入 ComfyUI 根目录，用启动 ComfyUI 的同一个 Python 环境克隆节点，并把独立模型项目克隆到默认模型目录。请将 `<models-repository-url>` 替换为模型项目创建后的实际地址。

```sh
git clone --depth 1 https://github.com/allenflux/ComfyUI-Video-Subtitle-Remover.git custom_nodes/video-subtitle-remover
git clone --depth 1 <models-repository-url> /app/ComfyUI/models/video-subtitle-remover-models
```

默认从 `/app/ComfyUI/models/video-subtitle-remover-models` 加载权重。如果模型项目安装在其他位置，请在启动 ComfyUI 前设置 `VSR_MODELS_DIR`，其值应为模型项目的根目录。

```sh
export VSR_MODELS_DIR=/path/to/video-subtitle-remover-models
```

如果镜像尚未安装 OpenCV 或 ONNX Runtime，按 `requirements.txt` 安装缺少的依赖。两个都缺时可以运行以下命令。

```sh
python -m pip install -r custom_nodes/video-subtitle-remover/requirements.txt
```

重启 ComfyUI 服务后，搜索 `VSR Remove Subtitles` 或 `VSR Remove Watermark`。可参考 [ComfyUI 官方安装说明](https://docs.comfy.org/installation/install_custom_node)。

如果已经安装过节点和模型项目，在 ComfyUI 根目录分别更新两者，补齐缺少的依赖后重启服务。使用 `VSR_MODELS_DIR` 时，请把第二条命令的路径替换为实际模型目录。

```sh
git -C custom_nodes/video-subtitle-remover pull --ff-only
git -C /app/ComfyUI/models/video-subtitle-remover-models pull --ff-only
```

### 与 InsightFace 共用 Python 环境

InsightFace 2.0 的依赖声明要求 `opencv-python`。共用环境时，本插件和 InsightFace 都可以使用 `opencv-python` 提供的 `cv2`，并按需单独安装 `onnxruntime>=1.20`。OpenCV 的多个发行包共用同一个 `cv2` 命名空间，每个环境只保留一个。[InsightFace 依赖](https://pypi.org/pypi/insightface/2.0/json) · [OpenCV 安装说明](https://pypi.org/project/opencv-python-headless/)

如果环境已经装了 `opencv-python-headless`，先用 `python -m pip show opencv-python-headless` 查看 `Version` 和 `Required-by`。如果其他节点没有明确依赖 headless 包，可先卸载它，再安装同版本的 `opencv-python`。运行下面的命令验证两个库和依赖声明。

```sh
python -c 'import cv2, onnxruntime; print(cv2.__version__, onnxruntime.__version__)'
python -m pip check
```

## 节点与工作流

| 节点 | 用法 |
| --- | --- |
| `VSR Remove Subtitles` | 接收图像或视频帧。默认在画面底部四分之一自动检测字幕，输出修复帧和字幕遮罩。可调整检测范围和遮罩扩张像素，或用 `rectangle` 修复整块选区。 |
| `VSR Remove Watermark` | 接收图像或视频帧。通过矩形框选水印，或连接与画面同尺寸的 `MASK`。可共用一张遮罩，也可逐帧提供。连接后优先使用遮罩。 |

矩形的 `x`、`y` 从画面左上角开始，与 `width`、`height` 一样按画面尺寸的比例填写。首次运行 LaMa 会在独立模型项目的 `big-lama` 目录合并分片，因此模型目录需要对 ComfyUI 进程可写。

将[示例工作流](workflows/video_cleanup.json)拖入 ComfyUI，在 `Load Video` 中上传并选择自己的视频。示例默认去字幕，取消去水印节点的旁路后即可同时处理水印。`Create Video` 接回原音频和帧率，再由 `Save Video` 保存。工作流将视频拆成一批图像，可先用短视频确认选区和效果。

## 集群部署

- 在所有会执行此工作流的 ComfyUI worker 上固定相同的节点项目和 `video-subtitle-remover-models` 项目版本。可以把节点目录、Python 依赖和模型项目加入现有 ComfyUI 镜像，然后用该镜像部署各 Pod。
- 在每个 worker 上把模型项目放在 `/app/ComfyUI/models/video-subtitle-remover-models`，或设置相同的 `VSR_MODELS_DIR` 指向挂载目录。使用 LaMa 时，确保 ComfyUI 进程能在模型目录合并分片，或在镜像构建时预先合并。
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
