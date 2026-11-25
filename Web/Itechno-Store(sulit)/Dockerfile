FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SESSION_DIR=/tmp/itechno-store-sessions

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./src

RUN useradd -r -u 10001 ctf
USER ctf

EXPOSE 8000

CMD ["gunicorn", "-b", "0.0.0.0:8000", "app.challenge:app", "--workers", "2", "--threads", "4", "--access-logfile", "-", "--error-logfile", "-"]
