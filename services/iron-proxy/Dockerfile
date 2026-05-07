FROM ironsh/iron-proxy:0.22.0@sha256:96aa4d082d8b5113d74b98becb53ae568a26d337206ed7bce8356943186f1ed2

USER root
RUN apk add --no-cache curl jq

COPY services/iron-proxy/iron-proxy.yaml /usr/local/share/iron-proxy/proxy.yaml.default
COPY --chmod=755 services/iron-proxy/entrypoint.sh /entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]
