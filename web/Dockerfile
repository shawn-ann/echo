# syntax=docker/dockerfile:1
FROM node:24-alpine AS build
WORKDIR /app

COPY package*.json ./
ARG NPM_REGISTRY=https://registry.npmjs.org
RUN --mount=type=cache,target=/root/.npm \
    npm ci --registry="$NPM_REGISTRY"

COPY . .
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
