FROM node:20-slim AS build

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

ARG VITE_AGENT_URL=http://localhost:8080
ARG VITE_BACKEND_URL=http://localhost:3000
ARG VITE_AGENT_API_KEY=
ENV VITE_AGENT_URL=$VITE_AGENT_URL
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL
ENV VITE_AGENT_API_KEY=$VITE_AGENT_API_KEY
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD wget -q -O /dev/null http://127.0.0.1/healthz || exit 1
