FROM python:3.10-slim

RUN apt update
RUN apt-get -y install make

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir upload

EXPOSE 8080

# ENTRYPOINT ["tail", "-f", "/dev/null"]

COPY dockerentrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]