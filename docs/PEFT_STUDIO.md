# PEFT Studio: Parameter-Efficient Fine-Tuning Guided Mastery

The PEFT Studio is a comprehensive 8-step wizard within TensorGuardFlow designed to help AI Engineers configure, run, and promote fine-tuned models with built-in data privacy and cryptographic integrity.

## Core Features

- **Guided Wizard**: Step-by-step configuration from training method selection to deployment.
- **Unified Hub**: Connectors for HuggingFace, Local Storage, MLflow, and more.
- **Differential Privacy**: Built-in DP-LoRA support for privacy-preserving fine-tuning.
- **Cryptographic Evidence**: Automated generation of TGSP manifests and PQC-signed evidence.
- **Simulation Mode**: Run full workflows in simulated environments to verify pipeline integrity without heavy compute.

## Architecture

The PEFT Studio is built on a modular "Connector Hub" architecture:

- `contracts.py`: Defines the interface for data, model, and monitoring connectors.
- `catalog.py`: Handles dynamic discovery of installed backends (e.g., detecting `torch` or `mlflow`).
- `workflow.py`: Orchestrates the 9-stage pipeline:
  1. Data Resolve
  2. Model Resolve
  3. Pre-flight Check
  4. Training Init
  5. Training Exec
  6. Evaluation
  7. TGSP Packing
  8. Evidence Signing
  9. Notification

## CLI Usage

### Launch PEFT Studio UI
```bash
tensorguard peft ui --port 8000
```

### Run Workflow from Config
```bash
tensorguard peft run path/to/config.json
```

## Security & Compliance

Every PEFT run generates a **TensorGuard Security Profile (TGSP)**. This package includes:
- **Manifest**: Hash-pinned container of the fine-tuned adapter weights.
- **Evidence**: Cryptographic trace of the training hyperparameters and DP-epsilon budget.
- **Policy Gate**: Automated verification before promotion to "Stable" environments.
