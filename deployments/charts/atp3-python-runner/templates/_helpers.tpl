{{/*
Return the fully qualified name.
*/}}
{{- define "atp3-python-runner.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Return the chart name.
*/}}
{{- define "atp3-python-runner.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "securityContext.pod" -}}
runAsNonRoot: true
seccompProfile:
  type: "RuntimeDefault"
{{- with .Values.podSecurityContext }}
{{ toYaml . }}
{{- end -}}
{{- end -}}

{{- define "securityContext.container" -}}
allowPrivilegeEscalation: false
capabilities:
  drop: ["ALL"]
{{- with .Values.containerSecurityContext }}
{{ toYaml . }}
{{- end -}}
{{- end -}}