FROM node:20-slim AS build

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

ARG VITE_AGENT_URL=/agent
ARG VITE_BACKEND_URL=http://localhost:3000
ARG VITE_ADSPILOT_URL=https://adspilot.pawgrammers.io.vn
ARG VITE_ANALYTICS_URL=https://analytics.pawgrammers.io.vn
ARG VITE_DEMO_NAMESPACE=local-demo
ARG VITE_ZALO_OA_ID=2224936774907333597
ARG VITE_ZALO_OA_NAME=IOT Generation
ARG VITE_ZALO_OA_QR_IMAGE=/zalo-oa-qr.jpg
ARG VITE_ZNEWS_URL=https://znews.pawgrammers.io.vn
ARG VITE_BAOMOI_URL=https://baomoi.pawgrammers.io.vn
ARG VITE_ZINGMP3_URL=https://zingmp3.pawgrammers.io.vn
ENV VITE_AGENT_URL=$VITE_AGENT_URL
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL
ENV VITE_ADSPILOT_URL=$VITE_ADSPILOT_URL
ENV VITE_ANALYTICS_URL=$VITE_ANALYTICS_URL
ENV VITE_DEMO_NAMESPACE=$VITE_DEMO_NAMESPACE
ENV VITE_ZALO_OA_ID=$VITE_ZALO_OA_ID
ENV VITE_ZALO_OA_NAME=$VITE_ZALO_OA_NAME
ENV VITE_ZALO_OA_QR_IMAGE=$VITE_ZALO_OA_QR_IMAGE
ENV VITE_ZNEWS_URL=$VITE_ZNEWS_URL
ENV VITE_BAOMOI_URL=$VITE_BAOMOI_URL
ENV VITE_ZINGMP3_URL=$VITE_ZINGMP3_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD wget -q -O /dev/null http://127.0.0.1/healthz || exit 1
