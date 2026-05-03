{{- define "centaur.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "centaur.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "centaur.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "centaur.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" -}}
{{- end -}}

{{- define "centaur.labels" -}}
helm.sh/chart: {{ include "centaur.chart" . }}
{{ include "centaur.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "centaur.selectorLabels" -}}
app.kubernetes.io/name: {{ include "centaur.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "centaur.componentLabels" -}}
{{ include "centaur.labels" .root }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{- define "centaur.componentSelectorLabels" -}}
{{ include "centaur.selectorLabels" .root }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{- define "centaur.componentName" -}}
{{- printf "%s-%s" (include "centaur.fullname" .root) .component | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "centaur.secretEnvName" -}}
{{- if .Values.secretManager.existingSecretName -}}
{{- .Values.secretManager.existingSecretName | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-secret-env" (include "centaur.fullname" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "centaur.trustedCaSecretName" -}}
{{- if .Values.firewall.existingCaSecretName -}}
{{- .Values.firewall.existingCaSecretName | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-firewall-ca" (include "centaur.fullname" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "centaur.apiServiceAccountName" -}}
{{- printf "%s-api" (include "centaur.fullname" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "centaur.repoCacheGithubTokenSecretName" -}}
{{- if .Values.repoCache.githubToken.existingSecretName -}}
{{- .Values.repoCache.githubToken.existingSecretName | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-repo-cache-github-token" (include "centaur.fullname" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "centaur.httpRouteName" -}}
{{- $suffix := default (printf "route-%v" .index) .route.name -}}
{{- printf "%s-%s" (include "centaur.fullname" .root) $suffix | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "centaur.appDatabaseUrl" -}}
{{- if .Values.database.appUrl -}}
{{- .Values.database.appUrl -}}
{{- else -}}
{{- printf "postgresql://%s:%s@%s:5432/%s" .Values.postgres.auth.username .Values.postgres.auth.password (include "centaur.componentName" (dict "root" . "component" "pgbouncer")) .Values.postgres.auth.database -}}
{{- end -}}
{{- end -}}

{{- define "centaur.pgbouncerDatabaseUrl" -}}
{{- if .Values.database.pgbouncerUrl -}}
{{- .Values.database.pgbouncerUrl -}}
{{- else -}}
{{- printf "postgresql://%s:%s@%s:5432/%s" .Values.postgres.auth.username .Values.postgres.auth.password (include "centaur.componentName" (dict "root" . "component" "postgres")) .Values.postgres.auth.database -}}
{{- end -}}
{{- end -}}
