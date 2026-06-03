FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    nodejs \
    npm \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY . /app/
WORKDIR /app/

RUN pip install -r requirements.txt

CMD bash start
