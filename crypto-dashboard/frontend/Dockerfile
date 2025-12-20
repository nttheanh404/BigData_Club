# Stage 1: Build React App
FROM node:18-alpine AS build

WORKDIR /app

# IMPORTANT: Copy ONLY package.json (ignore local package-lock.json)
COPY package.json ./

# Install dependencies based strictly on package.json
RUN npm install

# Copy the rest of the application code
COPY . .

# Build the application
RUN npm run build

# Stage 2: Serve with Nginx
FROM nginx:alpine

# Copy build artifacts from Stage 1
COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom Nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
