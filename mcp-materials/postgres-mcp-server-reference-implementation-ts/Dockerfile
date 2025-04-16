FROM node:22.12-alpine AS builder

WORKDIR /app

# Copy package files first
COPY package*.json ./
# COPY package-lock.json ./  # Uncomment if you have a package-lock.json

# Install dependencies (using npm ci is generally preferred if you have a lock file)
RUN npm install 

# Copy the rest of the application files
COPY tsconfig.json ./
COPY index.ts ./

# Build the TypeScript code
RUN npm run build

FROM node:22-alpine AS release

WORKDIR /app

# Copy only necessary files from builder
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist

ENV NODE_ENV=production
# Make sure the command runs the compiled JS
CMD ["node", "dist/index.js"]