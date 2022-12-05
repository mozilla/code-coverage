FROM python:3.11.0-slim

ADD tools /src/tools
ADD backend /src/backend

RUN cd /src/tools && pip install --disable-pip-version-check --no-cache-dir --quiet .
RUN cd /src/backend && pip install --disable-pip-version-check --no-cache-dir --quiet .

CMD ["gunicorn", "code_coverage_backend.flask:app", "--timeout", "30"]
