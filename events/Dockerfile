FROM python:3.7-slim


ADD tools /src/tools
ADD events /src/events

RUN cd /src/tools && pip install --disable-pip-version-check --no-cache-dir --quiet .
RUN cd /src/events && pip install --disable-pip-version-check --no-cache-dir --quiet .

CMD ["code-coverage-events"]
