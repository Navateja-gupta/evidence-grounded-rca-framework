# Evidence-Grounded AI Framework for Root Cause Analysis in Cloud-Native Microservice Infrastructure

M.Tech dissertation implementation. The platform performs root cause analysis (RCA) for
cloud-native microservice applications by combining anomaly detection, root cause ranking,
retrieval-augmented generation (RAG), LLM-based diagnosis, and NLI-based verification of the
diagnosis against collected evidence.

> **Status: Phase 1 – foundation.** This phase provides the project structure, FastAPI backend,
> configuration system, logging and error handling. No AI algorithms, telemetry backends or
> target microservices are implemented or deployed yet.

## Design principles

- **Application-independent.** No application names, services, namespaces, dependencies or
  endpoints are hardcoded. Everything about the target system comes from configuration.
- **Configuration-driven.** Platform defaults live in `config/default.yaml`. Each target
  application gets its own YAML file, selected at runtime with `RCA_APP_CONFIG_PATH`.
- **OpenTelemetry as the integration layer.** Telemetry is modelled as OTel signals (metrics,
  logs, traces). Query backends for each signal are chosen in configuration.
- **Independent modules.** Anomaly detection, root cause ranking, RAG, LLM diagnosis and NLI
  verification are separate packages under `rca/modules/`. They do not import one another.
  `rca/pipeline/` handles orchestration between them.
- **Simple deployment.** Docker now; a Helm chart for Kubernetes comes later.

## Project structure

```
evidence-grounded-rca-framework/
├── rca/                          # Python backend package
│   ├── main.py                   # FastAPI application factory (create_app)
│   ├── core/
│   │   ├── config.py             # Settings (env vars) + PlatformConfig (YAML) loading
│   │   ├── logging.py            # text / JSON logging setup
│   │   └── errors.py             # exception hierarchy + uniform JSON error responses
│   ├── api/
│   │   ├── router.py             # versioned API router (/api/v1)
│   │   ├── dependencies.py       # FastAPI dependencies for config access
│   │   └── routes/
│   │       ├── health.py         # /health (liveness), /ready (readiness)
│   │       └── system.py         # /api/v1/system/info (non-sensitive config view)
│   ├── integrations/telemetry/   # OpenTelemetry-based telemetry adapters      (later phase)
│   ├── modules/
│   │   ├── anomaly_detection/    #                                             (later phase)
│   │   ├── root_cause_ranking/   #                                             (later phase)
│   │   ├── rag/                  #                                             (later phase)
│   │   ├── llm_diagnosis/        #                                             (later phase)
│   │   └── nli_verification/     #                                             (later phase)
│   └── pipeline/                 # end-to-end RCA orchestration                (later phase)
├── config/
│   ├── default.yaml              # application-agnostic platform defaults
│   └── applications/
│       └── _template.yaml        # template for an application-specific config
├── deploy/helm/                  # Kubernetes / Helm chart                     (later phase)
├── tests/                        # pytest suite
├── data/                         # generated data, indexes, results (git-ignored)
├── docs/                         # dissertation / design documentation
├── Dockerfile, docker-compose.yml, .dockerignore
├── requirements.txt              # runtime dependencies
├── requirements-dev.txt          # + test dependencies
├── pyproject.toml                # project metadata + pytest config
└── .env.example                  # documented environment variables
```

## Configuration

Configuration has two layers.

### 1. Runtime settings: environment variables

These control the platform itself. They are read from the environment or from a `.env` file
(copy `.env.example`). All use the `RCA_` prefix:

| Variable | Default | Purpose |
|---|---|---|
| `RCA_ENVIRONMENT` | `development` | `development` / `testing` / `staging` / `production` |
| `RCA_LOG_LEVEL` | `INFO` | log level |
| `RCA_LOG_FORMAT` | `text` | `text`, or `json` for containers |
| `RCA_API_HOST` / `RCA_API_PORT` | `0.0.0.0` / `8000` | bind address (informational for uvicorn CLI) |
| `RCA_CONFIG_DIR` | `<project>/config` | directory containing `default.yaml` |
| `RCA_APP_CONFIG_PATH` | unset | application YAML to merge over the defaults |
| `RCA_LLM_API_KEY`, `RCA_TELEMETRY_AUTH_TOKEN` | unset | secrets, never logged or returned by the API |

### 2. Target application: YAML

`config/default.yaml` is loaded first. If `RCA_APP_CONFIG_PATH` is set, that file is then
deep-merged over it. String values can reference environment variables:

```yaml
telemetry:
  metrics:
    endpoint: ${RCA_METRICS_ENDPOINT}                 # required: fails fast if unset
  traces:
    endpoint: ${RCA_TRACES_ENDPOINT:-http://host:1234} # with a default
```

Unknown keys are rejected, so typos produce an error instead of being ignored silently.

To add a new application:

```bash
cp config/applications/_template.yaml config/applications/my-app.yaml
# edit it, then:
export RCA_APP_CONFIG_PATH=config/applications/my-app.yaml
```

Application YAML files are git-ignored by default. Only the template is committed.

## Setup

Requires Python 3.10+.

```bash
python -m venv .venv
# Windows (PowerShell):  .venv\Scripts\Activate.ps1
# Linux/macOS:           source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # optional
```

## Running

```bash
uvicorn rca.main:create_app --factory --reload --port 8000
```

Then open:

- http://localhost:8000/health: liveness
- http://localhost:8000/ready: readiness
- http://localhost:8000/api/v1/system/info: active (non-sensitive) configuration
- http://localhost:8000/docs: interactive OpenAPI docs

### With Docker

```bash
docker compose up --build
```

`config/` is mounted read-only into the container, so YAML changes need only a restart, not a
rebuild.

## Tests

```bash
pytest
```

The suite covers YAML loading, deep merging, environment variable interpolation, validation
errors, settings from environment variables, the health/readiness/system endpoints, secret
redaction, and the error response envelope.

## Error responses

Every API error has the same shape:

```json
{"error": {"code": "configuration_error", "message": "...", "request_id": "..."}}
```

Each response carries an `X-Request-ID` header. If the client sends one, it is reused.
