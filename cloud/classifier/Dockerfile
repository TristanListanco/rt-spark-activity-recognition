# Build context is the repository root (see docker-compose.yml), so the image
# can include the exported model from ml/models. Dockerfile.dockerignore limits
# the context to the few files used here.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MODEL_DIR=/srv/model

RUN useradd --system --uid 10001 --no-create-home app
WORKDIR /srv

COPY cloud/classifier/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ml/models/model.onnx ml/models/model_meta.json /srv/model/
COPY cloud/classifier/*.py ./

USER app
CMD ["python", "main.py"]
