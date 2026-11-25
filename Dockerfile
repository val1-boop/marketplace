FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

# La demostración usa un DynamoDB simulado en memoria: SOLO un proceso.
ENV GUNICORN_WORKERS=1
EXPOSE 8000
CMD ["gunicorn", "-c", "gunicorn.conf.py", "tools.demo_wsgi:app"]
