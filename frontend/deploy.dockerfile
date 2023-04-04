FROM nginx:latest

ADD frontend /src/frontend

WORKDIR /src/frontend

# Install some essentials
RUN apt-get update && apt-get install -y build-essential python python-dev

# Install node
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - &&\
apt-get install -y nodejs

# Backend is proxy'd
ENV BACKEND_URL=https://coverage.thunderbird.net
ENV REPOSITORY=https://hg.mozilla.org/comm-central
ENV PROJECT=comm-central
# TODO: Figure out zero coverage report location
ENV ZERO_COVERAGE_REPORT=https://coverage.thunderbird.net/zero_coverage_report.json

RUN npm install
RUN npm run build

# Use our custom nginx config
RUN rm /etc/nginx/conf.d/default.conf
COPY frontend/docker/etc/nginx/conf.d/coverage.conf /etc/nginx/conf.d/default.conf

RUN cp -r /src/frontend/dist/* /usr/share/nginx/html/

#CMD "nginx -g daemon off;"