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

本项目基于 [Video Subtitle Remover](https://github.com/YaoFANGUK/video-subtitle-remover)，按 [Apache 2.0](LICENSE) 许可发布。
