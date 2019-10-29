FROM python:3.8.0-slim

ADD tools /src/tools
ADD backend /src/backend

RUN cd /src/tools && python setup.py install
RUN cd /src/backend && python setup.py install

CMD ["gunicorn", "code_coverage_backend.flask:app", "--timeout", "30"]
