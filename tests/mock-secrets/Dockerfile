FROM python:3.11-alpine
RUN apk add --no-cache curl
WORKDIR /app
COPY server.py .
CMD ["python", "server.py"]
