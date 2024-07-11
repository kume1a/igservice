FROM python:3.10-slim

RUN apt update
RUN apt-get -y install make

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt
RUN make protogen
RUN mkdir upload

EXPOSE 50051

# ENTRYPOINT ["tail", "-f", "/dev/null"]

CMD ["make", "run"]