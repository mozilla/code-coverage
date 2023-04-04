FROM python:3.11.1-slim

ADD tools /src/tools
ADD backend /src/backend

RUN cd /src/tools && pip install --disable-pip-version-check --no-cache-dir --quiet .
RUN cd /src/backend && pip install --disable-pip-version-check --no-cache-dir --quiet .

ENV LOCAL_CONFIGURATION=/src/backend/code-coverage-conf.yml
ENV REPOSITORY=comm-central

CMD "/src/backend/tb-run.sh"
#CMD ["gunicorn", "code_coverage_backend.flask:app", "--timeout", "30"]
