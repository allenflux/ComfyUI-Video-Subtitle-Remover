from .comfy_nodes import VSRRemoveSubtitles, VSRRemoveWatermark

NODE_CLASS_MAPPINGS = {
    "VSRRemoveSubtitles": VSRRemoveSubtitles,
    "VSRRemoveWatermark": VSRRemoveWatermark,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VSRRemoveSubtitles": "VSR Remove Subtitles",
    "VSRRemoveWatermark": "VSR Remove Watermark",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
