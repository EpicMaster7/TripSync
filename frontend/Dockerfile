FROM node:22-alpine
WORKDIR /web
COPY package.json ./
RUN npm install --no-audit --no-fund
COPY . .
CMD ["npm","run","dev"]
