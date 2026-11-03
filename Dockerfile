FROM python:3.13-slim

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY mediciones ./mediciones

ENV PYTHONUNBUFFERED=1

# Forma exec: Python queda como PID 1 y recibe el SIGTERM. Con la forma shell, PID 1
# sería /bin/sh, que no reenvía la señal, y llegaría SIGKILL sin volcado.
CMD ["python", "-m", "app.main"]
