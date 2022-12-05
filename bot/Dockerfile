FROM python:3.11.0-slim

ADD tools /src/tools
ADD bot /src/bot

RUN /src/bot/ci/bootstrap.sh

RUN cd /src/tools && pip install --disable-pip-version-check --no-cache-dir --quiet .
RUN cd /src/bot && pip install --disable-pip-version-check --no-cache-dir --quiet .

CMD ["code-coverage-bot"]
