FROM node:20-slim AS build

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

ARG VITE_AGENT_URL=/agent
ARG VITE_BACKEND_URL=http://localhost:3000
ARG VITE_DEMO_NAMESPACE=local-demo
ENV VITE_AGENT_URL=$VITE_AGENT_URL
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL
ENV VITE_DEMO_NAMESPACE=$VITE_DEMO_NAMESPACE
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD wget -q -O /dev/null http://127.0.0.1/healthz || exit 1
