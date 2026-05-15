FROM ironsh/iron-proxy:0.29.0@sha256:b96c8a1f38bd29153e829671aea69db0c666c0cbec5e41dbf88082bc9b4093ef

USER root
RUN apk add --no-cache curl jq

COPY services/iron-proxy/iron-proxy.yaml /usr/local/share/iron-proxy/proxy.yaml.default
COPY --chmod=755 services/iron-proxy/entrypoint.sh /entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]
