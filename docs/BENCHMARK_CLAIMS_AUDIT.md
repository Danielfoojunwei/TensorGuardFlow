# Benchmark Claims Audit

**Date:** 2026-01-26
**Auditor:** Empirical Benchmark Framework
**Purpose:** Identify all performance/benchmark claims in README.md and codebase, assess reproducibility

---

## Executive Summary

This audit identifies **ALL** benchmark claims in the TensorGuardFlow repository and classifies them by:
1. **Reproducibility status** - Can these numbers be reproduced from code?
2. **Data source** - What dataset/task was used?
3. **Methodology** - Is the benchmark based on real ML training or simulation?

### Verdict: Most claims are based on **SIMULATED** data and require replacement with empirical benchmarks.

---

## Section 1: README.md Performance Claims

### 1.1 Platform Infrastructure (Section 4)

| Claim | Metric | Value | Reproducible? | Source | Notes |
|-------|--------|-------|---------------|--------|-------|
| Health Check RPS | Throughput | 183 RPS | **PARTIAL** | `benchmarks/api_bench.py` | API load test, reproducible but not ML-related |
| Health Check P95 | Latency | 12.5ms | **PARTIAL** | `benchmarks/api_bench.py` | Same as above |
| Authentication RPS | Throughput | 140 RPS | **PARTIAL** | `benchmarks/api_bench.py` | JWT + Argon2, reproducible |
| Authentication P95 | Latency | 48.7ms | **PARTIAL** | `benchmarks/api_bench.py` | Same as above |
| Fleet Listing RPS | Throughput | 127 RPS | **PARTIAL** | `benchmarks/api_bench.py` | DB query benchmark |
| Fleet Listing P95 | Latency | 65.3ms | **PARTIAL** | `benchmarks/api_bench.py` | Same as above |
| Telemetry Ingest | Throughput | 14,150/sec | **PARTIAL** | `benchmarks/ingest_bench.py` | Synthetic telemetry messages |
| Telemetry Ingest P95 | Latency | 685ms | **PARTIAL** | `benchmarks/ingest_bench.py` | Same as above |

**Status:** These are API/infrastructure benchmarks using synthetic workloads. Reproducible but not ML benchmarks.

---

### 1.2 VLA Performance (Section 4)

| Claim | Metric | DYNAMICAL Value | Baseline | Reproducible? | Source |
|-------|--------|-----------------|----------|---------------|--------|
| Success Rate | Accuracy | 96.8% | 97.1% (OpenVLA) | **NO** | Simulated in `comprehensive_vla_bench.py` |
| Privacy (RRE) | Privacy | 1.35 | 0.00 | **NO** | Claimed but not computed empirically |
| Round Latency | Latency | 658.5ms | 45.0ms | **PARTIAL** | Crypto latency measured, but not end-to-end |
| Bandwidth (PEFT) | Compression | 16.4 MB (30.5x) | ~500 MB | **NO** | Simulated compression ratios |

**Status:** These claims are based on **SIMULATED** learning dynamics, not actual VLA model training.

---

### 1.3 FastUMI Baseline Tasks (Section 13)

| Task | Latency | Bandwidth | Success Rate | Reproducible? | Source |
|------|---------|-----------|--------------|---------------|--------|
| Pick and Place | 0.017s | 9.4 KB | 93.9% | **NO** | Hardcoded/simulated values |
| Rotate Handle | 0.018s | 9.4 KB | 95.9% | **NO** | Same |
| Open Drawer | 0.017s | 9.4 KB | 96.0% | **NO** | Same |
| Push Button | 0.018s | 9.4 KB | 97.1% | **NO** | Same |
| Stack Cubes | 0.017s | 9.4 KB | 94.0% | **NO** | Same |

**Status:** These appear to be **ASPIRATIONAL** targets, not measured values.

---

### 1.4 Lifelong Learning Metrics (Section 14)

| Metric | Value | Target | Reproducible? | Source |
|--------|-------|--------|---------------|--------|
| Negative Backward Transfer (NBT) | 4.21% | ≤15% | **NO** | `comprehensive_vla_bench.py` - simulated forgetting curve |
| Forward Transfer (FWT) | 20.3% | ≥0% | **NO** | Same - simulated transfer gains |

**Status:** Simulated with hardcoded decay rates (`forgetting_rate = 0.00018`), not from actual model training.

---

## Section 2: NON-CANONICAL Benchmark Code

The following files contain simulation/mock benchmark logic that **MUST NOT** be used for official performance claims:

### 2.1 `benchmarks/production_benchmark.py`

**Location:** `/home/user/TensorGuardFlow/benchmarks/production_benchmark.py`

**Mock Patterns Identified:**
- Line 139: `mock_demos = [self._create_mock_demonstration() for _ in range(num_demos)]`
- Line 157-160: `mock_gradients = {...np.random.randn(1024, 1024)...}`
- Line 176-177: Simulated network latency with `time.sleep()`
- Line 183: Simulated aggregation delay `time.sleep(0.01 * num_clients)`
- Line 243: Hardcoded `success_rate=0.95`

**Verdict:** NON-CANONICAL - Uses synthetic data and simulated delays.

---

### 2.2 `src/tensorguard/bench/comprehensive_vla_bench.py`

**Location:** `/home/user/TensorGuardFlow/src/tensorguard/bench/comprehensive_vla_bench.py`

**Mock Patterns Identified:**
- Line 65-94: `_simulate_learning_dynamics()` - All learning is simulated:
  - Line 74: `gain = 0.007 * np.exp(-progress * 3.0)` - Hardcoded learning rate
  - Line 83: `forgetting_rate = 0.00018` - Hardcoded forgetting
  - Line 92-94: Forward transfer is simulated with `transfer_noise`
- Line 96-106: `_calculate_expert_conflict()` - Simulated ECI with hardcoded base conflict
- NO actual model training or gradient computation

**Verdict:** NON-CANONICAL - 100% simulated learning dynamics.

---

### 2.3 `src/tensorguard/bench/continual_learning_experiment.py`

**Location:** `/home/user/TensorGuardFlow/src/tensorguard/bench/continual_learning_experiment.py`

**Mock Patterns Identified:**
- Line 93-110: `_simulate_task_performance()` - Simulated success rates
- Line 179-184: Simulated forgetting during Task B training
- Line 448-480: Falls back to synthetic video/trajectory data if real data unavailable

**Verdict:** NON-CANONICAL - Simulated performance metrics, optional real video input.

---

### 2.4 `src/tensorguard/bench/micro.py`

**Location:** `/home/user/TensorGuardFlow/src/tensorguard/bench/micro.py`

**Mock Patterns:**
- Line 44: `data = np.random.randn(num_elements).astype(np.float32)`
- Line 73: Dummy UpdatePackage

**Verdict:** ACCEPTABLE for crypto microbenchmarks (measures actual crypto operations), but not ML benchmarks.

---

### 2.5 Frontend Simulation Store (if exists)

**Status:** Not directly relevant to ML benchmarks, but any simulation state should not be used for claims.

---

## Section 3: What's Required for Reproducible Benchmarks

### Required Datasets (Public, Automatically Downloaded)

| Suite | Dataset | Source | Protocol |
|-------|---------|--------|----------|
| Continual Learning | Split CIFAR-100 | torchvision | 20 tasks, 5 classes each |
| Continual Learning | Split TinyImageNet | Download from source | 20+ tasks |
| Continual Learning | CORe50 | Official repository | Standard scenarios |
| Distribution Shift | WILDS | wilds package | ID/OOD splits |
| PEFT | Adapter training | Any standard dataset | Throughput metrics |

### Required Baselines

1. **Frozen baseline** - No adaptation, just evaluate
2. **Naive sequential fine-tune** - Train sequentially (expected forgetting)
3. **TensorGuardFlow method** - Use adapter artifact management + gating

### Required Metrics

| Suite | Metrics |
|-------|---------|
| Continual Learning | Average Accuracy, Forgetting, BWT, FWT |
| Distribution Shift | ID Accuracy, OOD Accuracy, Worst-Group Accuracy |
| PEFT | Steps/sec, Examples/sec, Peak GPU Memory, Adapter Size |

---

## Section 4: Recommended Actions

1. **REPLACE** all README benchmark claims with references to generated reports
2. **CREATE** `benchmarks_empirical/` package with real dataset loaders
3. **IMPLEMENT** reproducible benchmark runners with deterministic seeding
4. **GENERATE** `reports/benchmark_report.md` from actual runs
5. **ENFORCE** `--fail_on_mock` flag to prevent simulated data in official benchmarks

---

## Appendix: Files Requiring Modification

| File | Action Required |
|------|-----------------|
| `README.md` | Replace hardcoded claims with "Run `make bench`" |
| `Makefile` | Add `bench` target for empirical benchmarks |
| `benchmarks/` | Mark as NON-CANONICAL in comments |
| NEW: `benchmarks_empirical/` | Create canonical benchmark package |
| NEW: `scripts/bench/run_empirical.sh` | Create benchmark runner script |
| NEW: `reports/` | Output directory for benchmark artifacts |

---

**End of Audit**
