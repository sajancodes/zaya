import cv2
import numpy as np


class FrameDiff:
    """Compare small blurred images; ignore isolated cursor/antialiasing noise."""
    def __init__(self):
        self.previous = None

    def update(self, frame, origin=(0, 0)):
        height, width = frame.shape[:2]
        thumb = cv2.GaussianBlur(cv2.resize(frame[:, :, :3], (320, 180)), (5, 5), 0)
        old, self.previous = self.previous, thumb
        if old is None:
            return ((origin[0], origin[1], width, height),)
        mask = (np.max(cv2.absdiff(old, thumb), axis=2) > 24).astype('uint8') * 255
        # Join nearby changed glyphs into a useful OCR region; individual
        # blinking carets still remain below the minimum contour area.
        mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((3,7),dtype='uint8'))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        regions = []
        for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:16]:
            if cv2.contourArea(contour) < 90:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            regions.append((origin[0] + int(x * width / 320), origin[1] + int(y * height / 180),
                            max(1, int(w * width / 320)), max(1, int(h * height / 180))))
        return tuple(regions)
