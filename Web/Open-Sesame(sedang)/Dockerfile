FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

RUN useradd -u 10001 -m -s /usr/sbin/nologin ctf
WORKDIR /app
COPY src/app.py /app/app.py

USER ctf
EXPOSE 8080
HEALTHCHECK --interval=20s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2).read()"

CMD ["python", "/app/app.py"]
