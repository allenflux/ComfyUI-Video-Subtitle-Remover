import cv2


class OpenCVInpaint:
    @staticmethod
    def inpaint(frame, mask):
        return cv2.inpaint(frame, mask, 3, cv2.INPAINT_TELEA)
