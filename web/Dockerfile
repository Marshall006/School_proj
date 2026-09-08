# syntax=docker/dockerfile:1.7
# Construit depuis la racine du depot : le tableau de bord partage `shared/`.
#   docker build -f web/Dockerfile .
FROM node:22-alpine AS deps
WORKDIR /app
COPY web/package.json web/package-lock.json* ./web/
COPY shared/package.json shared/package-lock.json* ./shared/
RUN cd shared && npm install --omit=dev --no-audit --no-fund || npm install --no-audit --no-fund
RUN cd web && npm install --no-audit --no-fund

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/web/node_modules ./web/node_modules
COPY --from=deps /app/shared/node_modules ./shared/node_modules
COPY shared ./shared
COPY web ./web
RUN cd shared && npx tsc -p tsconfig.json
RUN cd web && npm run build

FROM node:22-alpine AS runtime
ENV NODE_ENV=production
WORKDIR /app
RUN addgroup -S koda && adduser -S koda -G koda
COPY --from=builder --chown=koda:koda /app/web/.next ./web/.next
COPY --from=builder --chown=koda:koda /app/web/node_modules ./web/node_modules
COPY --from=builder --chown=koda:koda /app/web/package.json ./web/package.json
COPY --from=builder --chown=koda:koda /app/web/public ./web/public
COPY --from=builder --chown=koda:koda /app/shared ./shared
USER koda
WORKDIR /app/web
EXPOSE 3000
CMD ["npm", "run", "start"]
