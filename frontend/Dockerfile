# Build stage
FROM node:20-alpine AS build

WORKDIR /app

# Copy lockfile and package descriptor for reproducible install
COPY package.json package-lock.json ./
RUN npm ci

# Copy frontend source files
COPY . .

# Build application with API base URL argument
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built static assets
COPY --from=build /app/dist /usr/share/nginx/html

# Copy optimized nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD wget -q --spider http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
