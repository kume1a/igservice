FROM python:3.14-slim

RUN apt-get update && apt-get -y install --no-install-recommends make dos2unix \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p upload

EXPOSE 8080

RUN dos2unix ./dockerentrypoint.sh && chmod +x ./dockerentrypoint.sh

# ENTRYPOINT ["tail", "-f", "/dev/null"]

ENTRYPOINT ["./dockerentrypoint.sh"]