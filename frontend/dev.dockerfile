FROM nginx:latest

ADD frontend /src/frontend

WORKDIR /src/frontend

# Install some essentials
RUN apt-get update && apt-get install -y build-essential python python-dev

# Install node
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - &&\
apt-get install -y nodejs

ENV BACKEND_URL=http://localhost:8080
ENV REPOSITORY=https://hg.mozilla.org/comm-central
ENV PROJECT=comm-central
ENV ZERO_COVERAGE_REPORT=http://localhost:8080/v2/zero-coverage-report
ENV USE_ISO_DATE=true

RUN npm install
RUN npm run build

RUN cp -r /src/frontend/dist/* /usr/share/nginx/html/

#CMD "nginx -g daemon off;"