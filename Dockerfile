FROM python:3.11

RUN apt-get update && \
    apt-get install -y --no-install-recommends alsa-utils vlc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /

RUN pip install --no-cache -r requirements.txt

COPY server.py /app

WORKDIR /app

ENTRYPOINT ["python", "server.py"]
