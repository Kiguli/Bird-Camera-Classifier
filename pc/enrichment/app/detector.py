"""MegaDetector v6 (CPU) wrapper: crop the highest-confidence animal from a frame.

Import and model load are deferred and wrapped so the service still runs if the
heavy deps or weights are missing - callers get (None, None) and degrade to
classifying the full frame (see main.py).
"""
import logging

log = logging.getLogger("detector")
ANIMAL_CLASS_ID = 0  # MegaDetector: 0=animal, 1=person, 2=vehicle


class Detector:
    def __init__(self, version: str, conf_thres: float):
        self.conf_thres = conf_thres
        self.model = None
        self._np = None
        try:
            import numpy as np
            from PytorchWildlife.models import detection as pw_detection
            self._np = np
            try:
                self.model = pw_detection.MegaDetectorV6(
                    device="cpu", pretrained=True, version=version
                )
            except Exception as e:  # bad version string on an older pin
                log.warning("version=%r rejected (%s); retrying version-agnostic", version, e)
                self.model = pw_detection.MegaDetectorV6(device="cpu", pretrained=True)
            log.info("MegaDetector v6 loaded (version=%s)", version)
        except Exception as e:  # noqa: BLE001
            log.error("MegaDetector unavailable (%s: %s) - will classify full frames",
                      type(e).__name__, e)
            self.model = None

    @property
    def available(self) -> bool:
        return self.model is not None

    def crop_best_animal(self, pil_img):
        """Return (PIL crop, confidence) for the top animal, or (None, None)."""
        if not self.available:
            return None, None
        try:
            img_rgb = self._np.array(pil_img.convert("RGB"))  # raw RGB for V6
            result = self.model.single_image_detection(img_rgb, det_conf_thres=self.conf_thres)
            det = result["detections"]  # supervision Detections: .xyxy .confidence .class_id
            best_box, best_conf = None, -1.0
            for xyxy, conf, cid in zip(det.xyxy, det.confidence, det.class_id):
                if int(cid) == ANIMAL_CLASS_ID and float(conf) > best_conf:
                    best_conf, best_box = float(conf), xyxy
            if best_box is None:
                return None, None
            x1, y1, x2, y2 = (int(round(float(v))) for v in best_box)
            # clamp to image bounds
            w, h = pil_img.size
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            if x2 <= x1 or y2 <= y1:
                return None, None
            return pil_img.crop((x1, y1, x2, y2)), best_conf
        except Exception as e:  # noqa: BLE001
            log.error("detection failed (%s: %s)", type(e).__name__, e)
            return None, None
