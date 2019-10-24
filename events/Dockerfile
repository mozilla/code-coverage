FROM python:3.7-slim


ADD tools /src/tools
ADD events /src/events

RUN cd /src/tools && python --disable-pip-version-check --no-cache-dir --quiet  setup.py install
RUN cd /src/events && python --disable-pip-version-check --no-cache-dir --quiet  setup.py install

CMD ["code-coverage-events"]
