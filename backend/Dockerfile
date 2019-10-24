FROM python:3.7-slim

ADD tools /src/tools
ADD backend /src/backend

RUN cd /src/tools && python --disable-pip-version-check --no-cache-dir --quiet  setup.py install
RUN cd /src/backend && python --disable-pip-version-check --no-cache-dir --quiet  setup.py install

CMD ["gunicorn", "code_coverage_backend.flask:app", "--timeout", "30"]
