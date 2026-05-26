FROM node:24-slim

RUN apt-get update -qq && apt-get install -y -qq curl git jq openssh-client openssl && \
    curl -fsSL https://dl.k8s.io/release/v1.33.0/bin/linux/amd64/kubectl -o /usr/local/bin/kubectl && \
    chmod +x /usr/local/bin/kubectl && \
    curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN npm install -g pnpm@10

WORKDIR /app
COPY package.json ./
RUN pnpm install

COPY . .
RUN pnpm build

RUN git clone --depth 1 https://github.com/paradigmxyz/centaur.git /tmp/centaur && \
    cp -r /tmp/centaur/contrib/chart /app/chart && \
    rm -rf /tmp/centaur

RUN mkdir -p /tmp/deployments
ENV CENTAUR_STATE_DIR=/tmp/deployments
ENV CENTAUR_CHART_PATH=/app/chart

CMD ["node", "dist/worker.js"]
