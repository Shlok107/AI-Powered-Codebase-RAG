# Build stage
FROM node:22.16-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build application
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built assets
COPY --chown=nginx:nginx --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

RUN sed -i -e '/^[[:space:]]*user[[:space:]]\+[^;]*;/d' \
           -e 's#^[[:space:]]*pid[[:space:]].*;#pid /tmp/nginx.pid;#' /etc/nginx/nginx.conf \
    && mkdir -p /tmp/client_temp /tmp/proxy_temp /tmp/fastcgi_temp /tmp/uwsgi_temp /tmp/scgi_temp \
    && chown -R nginx:nginx /tmp/client_temp /tmp/proxy_temp /tmp/fastcgi_temp /tmp/uwsgi_temp /tmp/scgi_temp

USER nginx

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
