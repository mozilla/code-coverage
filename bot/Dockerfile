FROM python:3.7-slim

ADD tools /src/tools
ADD bot /src/bot

RUN /src/bot/ci/bootstrap.sh

RUN cd /src/tools && pip install --disable-pip-version-check --no-cache-dir --quiet  setup.py 
RUN cd /src/bot && pip install--disable-pip-version-check --no-cache-dir --quiet  setup.py 

CMD ["code-coverage-bot"]
