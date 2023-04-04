FROM nginx:latest

ADD frontend /src/frontend

WORKDIR /src/frontend

# Install some essentials
RUN apt-get update && apt-get install -y build-essential python python-dev

# Install node
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - &&\
apt-get install -y nodejs

ENV BACKEND_URL=http://localhost:8001
ENV REPOSITORY=https://hg.mozilla.org/comm-central
ENV PROJECT=comm-central
ENV ZERO_COVERAGE_REPORT=/assets/zero_coverage_report.json

RUN npm install
RUN npm run build

RUN cp -r /src/frontend/dist/* /usr/share/nginx/html/

#CMD "nginx -g daemon off;"