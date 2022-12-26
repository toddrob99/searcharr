FROM python:slim

LABEL org.opencontainers.image.source="https://github.com/toddrob99/searcharr"
LABEL org.opencontainers.image.description="Docker for SEARCHARR"
LABEL Name=Searcharr Version="v1.2-beta"

ARG TARGETPLATFORM BUILDPLATFORM


WORKDIR /app

RUN chmod -R 777 /app && \
    chmod -R +x /app && \
    chmod -R 705 /app

ADD . /app

RUN apt-get update -y && \
    apt-get upgrade -y

RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install -r requirements.txt && \
    apt-get autoremove -y

CMD ["python3", "searcharr.py"]
