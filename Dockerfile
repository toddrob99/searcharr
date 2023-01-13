FROM python:3.11-slim

LABEL Name=Searcharr Version=1.2

WORKDIR /app
ADD . /app

RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install -r requirements.txt

CMD ["python3", "searcharr.py"]
