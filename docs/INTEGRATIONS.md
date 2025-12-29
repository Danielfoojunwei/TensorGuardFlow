# TensorGuard Integrations

The MOAI Inference Service includes pre-built adapters for standard robotic fleet management protocols.

## Open-RMF
The **RmfAdapter** (`src/tensorguard/integrations/rmf/`) acts as a task dispatch interceptor.
- It listens for RMF Task assignments.
- It queries the MOAI service to resolve the high-level task into policy parameters.
- It forwards the result to the robot via standard RMF topics.

## VDA5050
The **Vda5050Bridge** (`src/tensorguard/integrations/vda5050/`) connects to your MQTT broker.
- Subscribes to `uagv/v2/{id}/order`.
- On receiving an order, triggers an encrypted inference check (e.g., for secure path planning validation).
- Publishes state updates to `uagv/v2/{id}/state`.

## Proprietary Connectors
Interfaces are provided in `connectors.py` for:
- **Formant**
- **InOrbit**
- **RoboRunner**

Implement these interfaces to bind MOAI inference to vendor-specific telemetry streams.
