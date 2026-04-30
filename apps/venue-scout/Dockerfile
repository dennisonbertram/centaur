ARG NODEJS_IMAGE="node:24.15.0-bookworm-slim@sha256:03eae3ef7e88a9de535496fb488d67e02b9d96a063a8967bae657744ecd513f2"
FROM ${NODEJS_IMAGE}

WORKDIR /app

COPY package.json ./
RUN npm install --omit=dev

COPY index.html server.js ./

EXPOSE 3000
CMD ["npm", "start"]
