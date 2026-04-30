FROM nginx:1.27-alpine
RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/nginx.conf
COPY conf.d/docsis.conf /etc/nginx/conf.d/docsis.conf
EXPOSE 80
