# TensorGuard Benchmark Matrix

## 1. Microbenchmarks (Cryptography & Packaging)

| Metric | Description | Target / Result |
|:---|:---|:---|
| **N2HE Encrypt** | Latency per 1KB | **144ms** (Python) |
| **Homomorphic Add** | Latency, Ops/sec | Scalable linear w/ batch |
| **Decrypt** | Latency | **15ms** (client-side) |
| **Ciphertext Expansion** | Ratio: Size(Cipher) / Size(Plain) | ~3x |
| **Serialization** | Time to serial/deserial `UpdatePackage` | ~2.1s (Full Update) |
| **Key Rotation** | Time to re-key (MOAI) | **2.1s** |

## 2. UpdatePackage Pipeline (Robot-Side)

| Stage | Description | Metric |
|:---|:---|:---|
| **Gradient Extraction** | Adapter delta creation (LoRA/IA3) | Latency, VRAM |
| **Privacy Pipeline** | Clipping + Sparsification + DP Noise | Latency, Sparsity % |
| **Packaging** | Encryption + Signing + Compression | Total Latency, Bytes |
| **Utility Proxy** | Loss decrease per round | Statistical Efficiency |

## 3. Aggregator Pipeline (Hub-Side)

| Stage | Description | Metric |
|:---|:---|:---|
| **Ingestion** | Signature verif + Schema validation | Throughput (pkg/s) |
| **Outlier Detection** | MAD / Cosine distance filtering | Reject Rate, False Positives |
| **Aggregation** | Homomorphic Summation | Latency vs N clients |
| **Availability** | Uptime under fault injection | 99.9% |

## 4. End-to-End Robotics Tracks

| Track | Scenario | Metrics |
|:---|:---|:---|
| **A (Sanity)** | Toy MLP + MNIST-ish | Wall-clock < 5min, Convergence |
| **B (Realistic)** | ViT-Tiny + Immitation Learning | Wall-clock < 1hr, Privacy Budget |
| **C (Stress)** | 500 Clients + Heterogeneous | Latency tails, Dropouts tolerated |

## 5. Privacy Leakage Evaluation

| Attack | Description | Baseline vs Defense |
|:---|:---|:---|
| **Gradient Inversion** | DLG / Geiping et al. (Reconstruct Input) | PSNR/SSIM reduction |
| **MIA** | Membership Inference on Adapter | ROC AUC reduction |
| **Server Trust** | Honest-but-curious server leakage | Info gain (bits) |

## 6. Robustness & Security Controls

| Threat | Test | Success Criteria |
|:---|:---|:---|
| **Byzantine Client** | Sign-flipping / Noise injection | Rejected by MAD |
| **Stragglers** | 30% random client dropout | Round completes (Quorum) |
| **Replay Attack** | Resend old `UpdatePackage` | Rejected (Nonce/Timestamp) |
| **Sybil Attack** | Wrong tenant ID | Rejected (AuthN) |

## 7. Expert Gating Precision (v2.3 Empirical)

| Task Category | Expert Module | Keywords | Measured Precision |
|:---|:---|:---|:---|
| **Manipulation** | `manipulation_grasp` | force, gripper, contact | **94.79%** |
| **Navigation** | `visual_primary` | objects, obstacles | **71.12%** |
| **Instruction** | `language_semantic` | command, verbal | **71.12%** |
| **Visual Aux** | `visual_aux` | color, texture, lighting | **Verified** |
