FROM python:3.12-slim

RUN apt-get update \
  && apt-get install -y postgresql postgresql-contrib default-mysql-client \
  && apt-get install sudo \
  && apt-get clean \
  && rm -rf /var/lib/apt/* /tmp/* /var/tmp/*

COPY ./app /app
WORKDIR /app

RUN pip install --no-cache-dir -r requirements.txt

CMD ["bash"]
