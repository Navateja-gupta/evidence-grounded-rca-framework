# Helm chart (planned)

A Helm chart for deploying the RCA platform to Kubernetes will be added in a later phase.

Design notes for that phase:

- The same container image as `Dockerfile` is used.
- `config/default.yaml` and the application YAML are mounted from a ConfigMap; `RCA_APP_CONFIG_PATH` points at it.
- Secrets (`RCA_LLM_API_KEY`, `RCA_TELEMETRY_AUTH_TOKEN`) come from a Kubernetes Secret.
- `/health` and `/ready` serve as liveness and readiness probes.
