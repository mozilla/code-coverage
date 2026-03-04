FROM python:3.14.3-slim

ADD bot /src/bot

RUN /src/bot/ci/bootstrap.sh

RUN cd /src/bot && pip install --disable-pip-version-check --no-cache-dir --quiet .

CMD ["code-coverage-bot"]
