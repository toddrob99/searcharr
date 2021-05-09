FROM python:3.9-alpine

LABEL Name=Searcharr Version=1.1

WORKDIR /app
ADD . /app

RUN apk add --no-cache --virtual .build-deps gcc musl-dev libffi-dev openssl-dev python3-dev rust cargo

RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install -r requirements.txt

RUN apk del .build-deps gcc musl-dev libffi-dev openssl-dev python3-dev rust cargo

CMD ["python3", "searcharr.py"]
