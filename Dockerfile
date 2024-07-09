FROM ubuntu

RUN apt update
RUN apt install python3-pip -y

WORKDIR /app

COPY . .

RUN make install

CMD ["make", "run"]