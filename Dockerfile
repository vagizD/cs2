FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1 \
    MPLCONFIGDIR=/tmp/matplotlib
WORKDIR /app

FROM base AS runtime
COPY requirements/runtime.txt /tmp/runtime.txt
RUN python -m pip install --no-cache-dir -r /tmp/runtime.txt
COPY config.yaml ./
COPY ml/__init__.py ml/config.py ml/features.py ml/model_artifact.py ml/predict.py ml/snapshot.py ./ml/
COPY ml/sql ./ml/sql
COPY api ./api
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=4s --start-period=10s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8080') + '/health', timeout=3).close()"
CMD ["sh", "-c", "exec python -m uvicorn api.main:app --host 0.0.0.0 --port \"${PORT:-8080}\""]

FROM runtime AS serving
COPY artifacts/deploy/config.yaml /app/config.yaml
COPY artifacts/deploy/hltv_database.db artifacts/deploy/hltv_database.db.manifest.json /app/serving-data/
COPY artifacts/deploy/model/pipeline.joblib artifacts/deploy/model/metadata.json /app/serving-data/model/

FROM base AS training
COPY requirements/training.txt /tmp/training.txt
RUN python -m pip install --no-cache-dir -r /tmp/training.txt
COPY config.yaml ./
COPY ml ./ml
COPY scripts/download_data.py scripts/upload_snapshot.py ./scripts/
COPY data/processed/hltv_database.db ./data/processed/
ARG GIT_COMMIT
ENV GIT_COMMIT=${GIT_COMMIT}
CMD ["python", "-m", "ml.train", "--config", "config.yaml"]
