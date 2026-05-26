# echo-model-runtime

> Sandboxed execution service for Echo Protocol quant models.

This is the **only** component that touches untrusted code (ONNX bytes uploaded by quants). Designed so that even a malicious model cannot:
- Read host filesystem outside its artifact path
- Open network sockets
- Spawn processes
- Exceed CPU/memory limits
- Crash the host process

## Architecture

```
┌────────────────────────────────────────────────┐
│  Echo API  →  POST /infer (Bearer token)       │
└────────────────────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────┐
│  Host process (this service)                    │
│  - Validate Inputs schema                       │
│  - Acquire sandbox from LRU cache               │
│  - Extract feature vector                       │
│  - Send to sandbox over stdin                   │
│  - Decode output → Signal                       │
│  - Validate Signal schema                       │
└────────────────────────────────────────────────┘
                       │   stdin/stdout
                       ▼
┌────────────────────────────────────────────────┐
│  Sandbox subprocess (runner.entry)              │
│  Resource limits:                               │
│    RLIMIT_CPU      = 5s                         │
│    RLIMIT_AS       = 512 MB                     │
│    RLIMIT_NOFILE   = 64                         │
│    RLIMIT_NPROC    = 0                          │
│  onnxruntime CPU provider only                  │
│  No imports of user code (only ONNX bytes)      │
└────────────────────────────────────────────────┘
```

## Threat model

| Threat | Mitigation |
|---|---|
| Malicious pickle / arbitrary code in artifact | Reject everything except ONNX |
| ONNX runtime CVE | One subprocess per model; crash bounded |
| Model spawns subprocess | RLIMIT_NPROC=0 in sandbox |
| Model opens network socket | No new fds beyond stdin/stdout/stderr |
| Model exhausts memory | RLIMIT_AS = 512 MB |
| Model loops forever | RLIMIT_CPU + asyncio wait_for |
| Model writes huge output | Reader cap = 64 KB |
| Bad Inputs from upstream | Pydantic validation in host before dispatch |
| Bad Signal from model | Pydantic validation in host after dispatch |

## Production hardening roadmap

- v0.4.4: gVisor / runsc wrapper around the subprocess
- v0.5.0: Per-tenant filesystem namespaces
- v0.5.0: AWS Nitro Enclave for cert-relevant inference
- v0.5.0: Per-call attestation chain (snapshot_hash → cert_id → runtime_run_id)

## Local dev

```bash
pip install -e .
uvicorn app.main:app --reload --port 8001
```

Set `RUNTIME_SHARED_TOKEN=dev` and call:

```bash
curl -X POST http://localhost:8001/infer \
  -H "Authorization: Bearer dev" \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/sample_request.json
```
