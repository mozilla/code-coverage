FROM python:3.11.1-slim-bullseye

ADD tools /src/tools
ADD bot /src/bot

RUN /src/bot/ci/bootstrap.sh

RUN cd /src/bot/ && pip install -r requirements.txt -r requirements-dev.txt
RUN cd /src/bot/ && pip install -e .
RUN cd /src/bot/ && python3 ./setup.py install


RUN cd /src/tools && pip install --disable-pip-version-check --no-cache-dir --quiet .
#RUN cd /src/bot && pip install --disable-pip-version-check --no-cache-dir --quiet .

WORKDIR /src/bot

RUN mkdir -p build/cache
RUN mkdir -p build/work

# Thunderbird settings
ENV UPSTREAM="https://hg.mozilla.org/comm-central"
ENV REPOSITORY="https://hg.mozilla.org/comm-central"
ENV PROJECT="comm-central"
ENV NAMESPACE="comm"
ENV PREFIX="comm"

CMD ["code-coverage-cron-thunderbird", "--cache-root=build/cache", "--working-dir=build/work"]
