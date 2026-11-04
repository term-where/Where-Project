
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN groupadd --system appgroup \
    && useradd --system --gid appgroup \
       --home-dir /app appuser

COPY --chown=appuser:appgroup . .

USER appuser

EXPOSE 8080

CMD ["python", "app.py"]
