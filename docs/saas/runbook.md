# Operations Runbook

## Provision a new tenant

The provisioner worker handles this automatically when a deployment is created
via the dashboard. If manual intervention is needed:

```bash
# Set env
export KUBECONFIG=~/.centaur/deployments/test-dev/kubeconfig.yaml
NS=centaur-{tenant-name}

# Check status
kubectl get pods -n $NS
kubectl logs -n $NS deploy/{tenant-name}-centaur-api --tail=20
kubectl logs -n $NS deploy/{tenant-name}-centaur-slackbot --tail=20 | grep -v health
```

## Push a credential manually

When the provisioner can't push (not running, or needs immediate update):

```bash
export KUBECONFIG=~/.centaur/deployments/test-dev/kubeconfig.yaml
NS=centaur-{tenant-name}

# Patch the secret
kubectl -n $NS get secret centaur-infra-env -o json | \
  jq --arg val "$(echo -n 'ACTUAL_VALUE' | base64)" \
  '.data["KEY_NAME"]=$val' | \
  kubectl apply -f -

# Restart the affected service
kubectl -n $NS rollout restart deployment {tenant-name}-centaur-slackbot
kubectl -n $NS rollout restart deployment {tenant-name}-centaur-api
```

## Fix NetworkPolicy for a tenant

Apply all required policies:

```bash
export KUBECONFIG=~/.centaur/deployments/test-dev/kubeconfig.yaml
NS=centaur-{tenant-name}
NAME={tenant-name}

# 1. Traefik ingress (for HTTPS + cert-manager solver)
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-traefik-ingress
  namespace: $NS
spec:
  podSelector: {}
  policyTypes: [Ingress]
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
      ports:
        - {port: 8000, protocol: TCP}
        - {port: 3001, protocol: TCP}
        - {port: 8089, protocol: TCP}
EOF

# 2. API → K8s API + internet
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-k8s-access
  namespace: $NS
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/component: api
  policyTypes: [Egress]
  egress:
    - to: [{namespaceSelector: {}}]
      ports: [{port: 443, protocol: TCP}]
    - to: [{ipBlock: {cidr: "0.0.0.0/0"}}]
      ports: [{port: 443, protocol: TCP}]
EOF

# 3. Slackbot → internet
kubectl apply -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: slackbot-egress-internet
  namespace: $NS
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/component: slackbot
  policyTypes: [Egress]
  egress:
    - to: [{ipBlock: {cidr: "0.0.0.0/0"}}]
      ports: [{port: 443, protocol: TCP}]
EOF

# 4. Remove HTTPS_PROXY
kubectl set env deployment/$NAME-centaur-api -n $NS \
  --containers=api HTTPS_PROXY- HTTP_PROXY- https_proxy- http_proxy-
kubectl set env deployment/$NAME-centaur-slackbot -n $NS \
  --containers=slackbot HTTPS_PROXY- HTTP_PROXY- https_proxy- http_proxy-
```

## Debug Slack not responding

```bash
NS=centaur-{tenant-name}

# 1. Is the slackbot receiving events?
kubectl logs -n $NS deploy/{name}-centaur-slackbot --tail=30 | grep -v health
# Look for: POST /api/webhooks/slack 200

# 2. Can slackbot reach Slack API?
# Look for: ECONNREFUSED → need slackbot-egress-internet policy

# 3. Is the signing secret correct?
kubectl get secret centaur-infra-env -n $NS \
  -o jsonpath='{.data.SLACK_SIGNING_SECRET}' | base64 -d
# Should NOT be "stub"

# 4. Can the API spawn sandboxes?
kubectl logs -n $NS deploy/{name}-centaur-api --tail=20
# Look for: Cannot connect to host 10.43.0.1:443 → need api-k8s-access policy

# 5. Can the sandbox reach OpenAI?
kubectl get pods -n $NS -l centaur.ai/managed=true
kubectl logs -n $NS {sandbox-pod-name} --tail=20
# Look for: 401 Unauthorized → OPENAI_API_KEY not in secret
```

## Debug agent returns empty response

```bash
NS=centaur-{tenant-name}

# Check sandbox logs
kubectl logs -n $NS {sandbox-pod-name} --tail=30

# Common causes:
# 1. "401 Unauthorized: Incorrect API key OPENAI_A**_KEY"
#    → OPENAI_API_KEY not in centaur-infra-env secret
#    → Fix: patch secret + restart API

# 2. "failed to connect to websocket: IO error"
#    → Sandbox can't reach api.openai.com
#    → iron-proxy should handle this, but check NetworkPolicy
```

## Tear down a tenant

```bash
KUBECONFIG=~/.centaur/deployments/test-dev/kubeconfig.yaml
NS=centaur-{tenant-name}

helm uninstall {tenant-name} -n $NS
kubectl delete namespace $NS
```

## Restart everything

```bash
KUBECONFIG=~/.centaur/deployments/test-dev/kubeconfig.yaml
NS=centaur-{tenant-name}
NAME={tenant-name}

kubectl -n $NS rollout restart deployment $NAME-centaur-api
kubectl -n $NS rollout restart deployment $NAME-centaur-slackbot
```
