# ── builder stage：裝相依 + 編 bcrypt 等 native bindings ──
FROM python:3.13-alpine AS builder

RUN apk add --no-cache gcc musl-dev libffi-dev

WORKDIR /build
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt


# ── runtime stage：只帶執行需要的東西 ──
FROM python:3.13-alpine

# 安全：非 root user 跑
RUN adduser -D -u 10001 appuser

COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

WORKDIR /app
COPY app/ ./app/

RUN python -m compileall -q app/

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--log-level", "info"]
