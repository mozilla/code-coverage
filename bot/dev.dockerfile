FROM python:3.11.1-slim-bullseye

#RUN apt-get update && apt-get install -y mercurial

#COPY bot/ci/hgrc /etc/mercurial/hgrc

ADD tools /src/tools
ADD bot /src/bot

RUN /src/bot/ci/bootstrap.sh

RUN cd /src/bot/ && pip install -r requirements.txt -r requirements-dev.txt
RUN cd /src/bot/ && pip install -e .
RUN cd /src/bot/ && python3 ./setup.py install
#RUN pre-commit install
#RUN pre-commit run -a
#RUN pytest -v


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

#CMD "cd /src/bot && code-coverage-cron"
#CMD "code-coverage-cron --cache-root=build/cache --working-dir=build/work --local-configuration=code-coverage.yml"
#CMD ["python3 /src/bot/code-coverage-bot"]
CMD ["code-coverage-cron", "--cache-root=build/cache", "--working-dir=build/work", "--local-configuration=code-coverage.yml"]