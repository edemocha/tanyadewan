# Hugging Face Space (Docker, free CPU). Built from the bundle made by scripts/make_space_bundle.py.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 user
USER user
ENV PATH=/home/user/.local/bin:$PATH PYTHONPATH=/home/user/app/src PYTHONUNBUFFERED=1 \
    TANYADEWAN_OVERRIDE=config.prod.yaml PUBLIC_MODE=1
WORKDIR /home/user/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Model weights are fetched at build time (about 1.2 GB), so the Space repo stays small.
RUN mkdir -p models/bge-m3 models/bge-reranker-v2-m3 \
 && curl -fsSL -o models/bge-m3/model_int8.onnx https://huggingface.co/Xenova/bge-m3/resolve/main/onnx/model_int8.onnx \
 && curl -fsSL -o models/bge-m3/tokenizer.json https://huggingface.co/Xenova/bge-m3/resolve/main/tokenizer.json \
 && curl -fsSL -o models/bge-reranker-v2-m3/model_int8.onnx https://huggingface.co/onnx-community/bge-reranker-v2-m3-ONNX/resolve/main/onnx/model_int8.onnx \
 && curl -fsSL -o models/bge-reranker-v2-m3/tokenizer.json https://huggingface.co/onnx-community/bge-reranker-v2-m3-ONNX/resolve/main/tokenizer.json

COPY --chown=user . .
EXPOSE 7860
CMD ["uvicorn", "tanyadewan.api.main:app", "--host", "0.0.0.0", "--port", "7860", "--log-level", "warning"]
