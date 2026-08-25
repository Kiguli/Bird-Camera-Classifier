"""BioCLIP 2 zero-shot species classifier.

Loads open_clip's BioCLIP 2, precomputes normalized text features for the fixed
candidate list once at startup, then scores each crop against them. BioCLIP was
trained on taxonomic captions, so SCIENTIFIC binomials are used in the prompts;
the common name is carried alongside for humans.

Load is wrapped so a missing dep/weights degrades gracefully (available=False).
"""
import logging

log = logging.getLogger("classifier")


def load_species(path: str):
    """Parse 'Common Name | Scientific name' lines into [(common, scientific)]."""
    species = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            common = parts[0]
            scientific = parts[1] if len(parts) > 1 and parts[1] else common
            species.append((common, scientific))
    if not species:
        raise ValueError(f"No species parsed from {path}")
    return species


class Classifier:
    def __init__(self, model_id: str, species, num_threads: int = 0):
        self.species = species
        self.model = None
        self._torch = None
        self._preprocess = None
        self._txt_features = None
        try:
            import torch
            import open_clip
            self._torch = torch
            if num_threads and num_threads > 0:
                torch.set_num_threads(num_threads)
            model, _, preprocess = open_clip.create_model_and_transforms(model_id)
            model = model.to("cpu").eval()
            tokenizer = open_clip.get_tokenizer(model_id)
            prompts = [f"a photo of {sci}." for (_c, sci) in species]
            with torch.no_grad():
                txt = tokenizer(prompts)
                feats = model.encode_text(txt)
                self._txt_features = torch.nn.functional.normalize(feats, dim=-1)
            self.model = model
            self._preprocess = preprocess
            log.info("BioCLIP 2 loaded (%d candidate species)", len(species))
        except Exception as e:  # noqa: BLE001
            log.error("BioCLIP unavailable (%s: %s) - species ID disabled",
                      type(e).__name__, e)
            self.model = None

    @property
    def available(self) -> bool:
        return self.model is not None

    def classify(self, pil_img, k: int = 3):
        """Return [(common, scientific, score), ...] top-k, or [] if unavailable."""
        if not self.available:
            return []
        try:
            torch = self._torch
            img = self._preprocess(pil_img.convert("RGB")).unsqueeze(0)
            with torch.no_grad():
                img_f = torch.nn.functional.normalize(self.model.encode_image(img), dim=-1)
                logits = self.model.logit_scale.exp() * img_f @ self._txt_features.T
                probs = logits.softmax(dim=-1)[0]
            k = min(k, len(self.species))
            top_p, top_i = probs.topk(k)
            return [
                (self.species[int(i)][0], self.species[int(i)][1], float(p))
                for p, i in zip(top_p, top_i)
            ]
        except Exception as e:  # noqa: BLE001
            log.error("classification failed (%s: %s)", type(e).__name__, e)
            return []
