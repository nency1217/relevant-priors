FROM python:3.12-slim

WORKDIR /app

# System deps kept minimal — no compilation needed for our pure-python code.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8000
EXPOSE 8000

# Single worker keeps the in-process cache hot. Switch to gunicorn + multiple
# workers + a shared cache (e.g. Redis) if you need horizontal scale.
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
