FROM python:3.11-slim

# libgl1 / libglib2.0-0 are needed by opencv (pulled transitively via
# ultralytics/supervision inside PytorchWildlife).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Optional: pre-cache model weights into the image for offline deploy boxes.
# Leaving these commented downloads weights on first run into the mounted caches
# instead (needs internet once).
# RUN python -c "from PytorchWildlife.models import detection as d; d.MegaDetectorV6(device='cpu')"
# RUN python -c "import open_clip; open_clip.create_model_and_transforms('hf-hub:imageomics/bioclip-2')"

CMD ["python", "-u", "main.py"]
