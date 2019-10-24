FROM python:3.7-slim

ADD tools /src/tools
ADD bot /src/bot

RUN /src/bot/ci/bootstrap.sh

RUN cd /src/tools && python --disable-pip-version-check --no-cache-dir --quiet  setup.py install
RUN cd /src/bot && python --disable-pip-version-check --no-cache-dir --quiet  setup.py install

CMD ["code-coverage-bot"]
