FROM node:22-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

ENV API_INTERNAL_URL=http://backend:8000
ENV NEXT_PUBLIC_API_BASE_URL=
ENV NEXT_PUBLIC_FIXTURE_DATA=0
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

FROM node:22-alpine AS runtime

WORKDIR /app

ENV NODE_ENV=production
ENV API_INTERNAL_URL=http://backend:8000
ENV NEXT_PUBLIC_API_BASE_URL=
ENV NEXT_PUBLIC_FIXTURE_DATA=0
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=build /app/.next ./.next
COPY --from=build /app/public ./public
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/node_modules ./node_modules

EXPOSE 3000

CMD ["npm", "start"]
