FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY src/ /app/src/

RUN useradd -r -u 10001 stars
USER stars

EXPOSE 8000 9000

CMD ["python3", "/app/src/frontend.py"]
