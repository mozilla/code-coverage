FROM python:3.7-slim

ADD tools /src/tools
ADD backend /src/backend

RUN cd /src/tools && pip install --disable-pip-version-check --no-cache-dir --quiet  setup.py 
RUN cd /src/backend && pip install --disable-pip-version-check --no-cache-dir --quiet  setup.py 

CMD ["gunicorn", "code_coverage_backend.flask:app", "--timeout", "30"]
