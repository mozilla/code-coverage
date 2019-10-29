FROM python:3.8.0-slim

ADD tools /src/tools
ADD bot /src/bot

RUN /src/bot/ci/bootstrap.sh

RUN cd /src/tools && python setup.py install
RUN cd /src/bot && python setup.py install

CMD ["code-coverage-bot"]
