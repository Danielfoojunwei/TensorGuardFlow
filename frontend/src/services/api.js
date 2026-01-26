/**
 * DYNAMICAL API Service Layer
 *
 * Centralized API client with:
 * - Automatic Authorization header injection
 * - Global 401 handling with redirect to login
 * - AbortController support for cancellations
 * - Retry logic for idempotent GET requests
 * - Consistent error handling
 */

const API_BASE = '/api/v1'

class ApiError extends Error {
    constructor(message, status, data = null, correlationId = null) {
        super(message)
        this.status = status
        this.data = data
        this.correlationId = correlationId
        this.name = 'ApiError'
    }
}

// Retry configuration
const RETRY_CONFIG = {
    maxRetries: 3,
    retryDelay: 1000,
    retryStatusCodes: [502, 503, 504], // Gateway errors
    retryOnNetworkError: true
}

// Sleep helper for retries
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms))

// Check if request is idempotent (safe to retry)
const isIdempotent = (method) => ['GET', 'HEAD', 'OPTIONS'].includes(method?.toUpperCase())

/**
 * Core request function
 * @param {string} endpoint - API endpoint (e.g., '/settings')
 * @param {object} options - Fetch options + custom options
 * @param {AbortSignal} options.signal - AbortController signal for cancellation
 * @param {boolean} options.skipAuth - Skip Authorization header
 * @param {boolean} options.retry - Enable retry for this request (default true for GET)
 */
async function request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`
    const method = options.method?.toUpperCase() || 'GET'

    const config = {
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        },
        ...options
    }

    // Remove custom options from config
    const { skipAuth, retry, signal, ...fetchConfig } = config

    // Add auth token if available and not skipped
    if (!skipAuth) {
        const token = localStorage.getItem('auth_token')
        if (token) {
            fetchConfig.headers['Authorization'] = `Bearer ${token}`
        }
    }

    // Add signal for abort support
    if (signal) {
        fetchConfig.signal = signal
    }

    // Determine if retry is enabled
    const shouldRetry = retry !== false && isIdempotent(method)
    let lastError = null
    const maxAttempts = shouldRetry ? RETRY_CONFIG.maxRetries + 1 : 1

    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        try {
            const response = await fetch(url, fetchConfig)

            // Handle 401 Unauthorized globally
            if (response.status === 401) {
                localStorage.removeItem('auth_token')
                localStorage.removeItem('auth_user')
                // Redirect to login (uses history API to avoid circular imports)
                window.location.href = '/login'
                throw new ApiError('Session expired. Please log in again.', 401)
            }

            // Check for retry-able errors
            if (shouldRetry && RETRY_CONFIG.retryStatusCodes.includes(response.status)) {
                if (attempt < maxAttempts) {
                    await sleep(RETRY_CONFIG.retryDelay * attempt)
                    continue
                }
            }

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}))
                const correlationId = response.headers.get('x-correlation-id') || errorData.correlation_id
                throw new ApiError(
                    errorData.detail || errorData.message || `HTTP ${response.status}`,
                    response.status,
                    errorData,
                    correlationId
                )
            }

            // Handle empty responses
            const contentType = response.headers.get('content-type')
            if (contentType && contentType.includes('application/json')) {
                return await response.json()
            }
            return null
        } catch (error) {
            // Handle abort
            if (error.name === 'AbortError') {
                throw error
            }

            // Handle network errors with retry
            if (error instanceof TypeError && RETRY_CONFIG.retryOnNetworkError && shouldRetry) {
                lastError = error
                if (attempt < maxAttempts) {
                    await sleep(RETRY_CONFIG.retryDelay * attempt)
                    continue
                }
            }

            // Re-throw ApiError as-is
            if (error instanceof ApiError) {
                throw error
            }

            // Wrap other errors
            lastError = error
        }
    }

    // All retries exhausted
    throw lastError instanceof ApiError ? lastError : new ApiError(lastError?.message || 'Network error', 0)
}

/**
 * Upload file with FormData
 * @param {string} endpoint - API endpoint
 * @param {FormData} formData - Form data with file
 * @param {object} options - Additional options
 */
async function uploadFile(endpoint, formData, options = {}) {
    const url = `${API_BASE}${endpoint}`

    const headers = {}
    const token = localStorage.getItem('auth_token')
    if (token) {
        headers['Authorization'] = `Bearer ${token}`
    }

    const response = await fetch(url, {
        method: 'POST',
        headers,
        body: formData,
        ...options
    })

    if (response.status === 401) {
        localStorage.removeItem('auth_token')
        localStorage.removeItem('auth_user')
        window.location.href = '/login'
        throw new ApiError('Session expired. Please log in again.', 401)
    }

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new ApiError(errorData.detail || 'Upload failed', response.status, errorData)
    }

    return response.json()
}

// VLA Model Registry API
export const vlaApi = {
    listModels: (params = {}) => {
        const query = new URLSearchParams(params).toString()
        return request(`/vla/models${query ? '?' + query : ''}`)
    },
    getModel: (modelId) => request(`/vla/models/${modelId}`),
    createModel: (data) => request('/vla/models', { method: 'POST', body: JSON.stringify(data) }),
    deployModel: (modelId, fleetId, rolloutPercentage = 100) =>
        request('/vla/deploy', {
            method: 'POST',
            body: JSON.stringify({ model_id: modelId, fleet_id: fleetId, rollout_percentage: rolloutPercentage })
        }),
    submitSafetyCheck: (modelId, testScenarios = 100) =>
        request('/vla/safety/validate', {
            method: 'POST',
            body: JSON.stringify({ model_id: modelId, test_environment: 'simulation', test_scenarios: testScenarios })
        }),
    getFleetSafetyMetrics: (fleetId) => request(`/vla/safety/metrics/${fleetId}`),
    submitBenchmark: (data) => request('/vla/benchmark/submit', { method: 'POST', body: JSON.stringify(data) }),
    getBenchmarkHistory: (modelId) => request(`/vla/benchmark/${modelId}`)
}

// Identity & Certificate Management API
export const identityApi = {
    getInventory: (params = {}) => {
        const query = new URLSearchParams(params).toString()
        return request(`/identity/inventory${query ? '?' + query : ''}`)
    },
    createEndpoint: (data) => request('/identity/inventory/endpoints', { method: 'POST', body: JSON.stringify(data) }),
    requestScan: (fleetId) => request(`/identity/scan/request?fleet_id=${fleetId}`, { method: 'POST' }),
    listPolicies: () => request('/identity/policies'),
    createPolicy: (data) => request('/identity/policies', { method: 'POST', body: JSON.stringify(data) }),
    getPolicy: (policyId) => request(`/identity/policies/${policyId}`),
    runRenewals: (endpointIds, policyId) =>
        request('/identity/renewals/run', {
            method: 'POST',
            body: JSON.stringify({ endpoint_ids: endpointIds, policy_id: policyId })
        }),
    listRenewals: (params = {}) => {
        const query = new URLSearchParams(params).toString()
        return request(`/identity/renewals${query ? '?' + query : ''}`)
    },
    executeEkuMigration: () => request('/identity/migrations/eku-split', { method: 'POST' }),
    getRiskAnalysis: (certId = null) => {
        const query = certId ? `?cert_id=${certId}` : ''
        return request(`/identity/risk${query}`)
    },
    getAuditLog: (params = {}) => {
        const query = new URLSearchParams(params).toString()
        return request(`/identity/audit${query ? '?' + query : ''}`)
    },
    verifyAuditChain: () => request('/identity/audit/verify')
}

// FedMoE API
export const fedmoeApi = {
    listExperts: () => request('/fedmoe/experts'),
    createExpert: (name, baseModel) =>
        request('/fedmoe/experts', { method: 'POST', body: JSON.stringify({ name, base_model: baseModel }) }),
    getSkillsLibrary: () => request('/fedmoe/skills-library'),
    addEvidence: (expertId, evidenceType, value) =>
        request(`/fedmoe/experts/${expertId}/evidence`, {
            method: 'POST',
            body: JSON.stringify({ evidence_type: evidenceType, value })
        })
}

// Integrations API
export const integrationsApi = {
    connect: (service, config) =>
        request('/integrations/connect', { method: 'POST', body: JSON.stringify({ service, config }) }),
    getStatus: () => request('/integrations/status')
}

// TGSP Marketplace API
export const tgspApi = {
    listPackages: () => request('/tgsp/packages'),
    uploadPackage: (file) => {
        const formData = new FormData()
        formData.append('file', file)
        return uploadFile('/tgsp/upload', formData)
    },
    createRelease: (packageId, fleetId, channel = 'stable') =>
        request('/tgsp/releases', {
            method: 'POST',
            body: JSON.stringify({ package_id: packageId, fleet_id: fleetId, channel, is_active: true })
        }),
    getCurrentFleetPackage: (fleetId, channel = 'stable') =>
        request(`/tgsp/fleets/${fleetId}/current?channel=${channel}`)
}

// KMS API
export const kmsApi = {
    getKeys: () => request('/kms/keys'),
    getRotationSchedule: () => request('/kms/rotation-schedule'),
    getAttestationPolicies: () => request('/kms/attestation-policies'),
    rotateKey: (kid, reason = 'manual_rotation') =>
        request('/kms/rotate', { method: 'POST', body: JSON.stringify({ kid, reason }) })
}

// Pipeline Config API
export const pipelineApi = {
    getConfig: () => request('/pipeline/config'),
    updateConfig: (key, value) =>
        request('/pipeline/config', { method: 'PUT', body: JSON.stringify({ key, value: String(value) }) }),
    resetConfig: () => request('/pipeline/config/reset', { method: 'POST' })
}

// Bayesian Policy API
export const policyApi = {
    getBayesianConfig: () => request('/policy/bayesian/config'),
    updateRules: (rules) => request('/policy/bayesian/rules', { method: 'POST', body: JSON.stringify(rules) }),
    triggerEvaluation: (runId) =>
        request(`/policy/bayesian/evaluate?run_id=${runId}`, { method: 'POST' })
}

// Forensics API
export const forensicsApi = {
    getIncidents: () => request('/forensics/incidents'),
    analyzeIncident: (incidentId, timeWindowHours = 24) =>
        request('/forensics/analyze', {
            method: 'POST',
            body: JSON.stringify({ incident_id: incidentId, time_window_hours: timeWindowHours })
        }),
    verifyCompliance: () => request('/forensics/verify-compliance', { method: 'POST' }),
    getMetricsExtended: () => request('/forensics/metrics/extended')
}

// Fleet API
export const fleetApi = {
    listFleets: () => request('/fleets/extended'),
    createFleet: (name) => request(`/fleets?name=${encodeURIComponent(name)}`, { method: 'POST' }),
    emergencyRollback: (fleetId, reason) =>
        request('/fleets/emergency-rollback', {
            method: 'POST',
            body: JSON.stringify({ fleet_id: fleetId, reason })
        })
}

// PEFT API
export const peftApi = {
    getProfiles: () => request('/peft/profiles'),
    listRuns: () => request('/peft/runs'),
    createRun: (wizardState) => request('/peft/runs', { method: 'POST', body: JSON.stringify(wizardState) }),
    getRun: (runId) => request(`/peft/runs/${runId}`),
    promoteRun: (runId, channel) =>
        request(`/peft/runs/${runId}/promote`, { method: 'POST', body: JSON.stringify({ channel }) })
}

// Telemetry API
export const telemetryApi = {
    getPipeline: (timeRange = '15m') => request(`/telemetry/pipeline?time_range=${timeRange}`),
    getDevices: () => request('/telemetry/devices')
}

// Dashboard API
export const dashboardApi = {
    getStats: () => request('/dashboard/stats')
}

// Settings API
export const settingsApi = {
    getSettings: () => request('/settings'),
    updateSetting: (key, value) =>
        request('/settings', { method: 'PUT', body: JSON.stringify({ key, value: String(value) }) }),
    bulkUpdate: (settings) =>
        request('/settings/bulk', { method: 'PUT', body: JSON.stringify(settings) })
}

// Status & Health API
export const statusApi = {
    getStatus: () => request('/status'),
    getHealth: () => request('/status/health'),
    getMetrics: () => request('/status/metrics')
}

// Security API
export const securityApi = {
    getScore: () => request('/security/score')
}

// Skills API
export const skillsApi = {
    getLibrary: () => request('/skills/library'),
    rollback: (skillId, version) =>
        request('/skills/rollback', { method: 'POST', body: JSON.stringify({ skill_id: skillId, version }) })
}

// Lineage API
export const lineageApi = {
    getVersions: () => request('/lineage/versions'),
    deploy: (versionId, fleetId) =>
        request('/lineage/deploy', { method: 'POST', body: JSON.stringify({ version_id: versionId, fleet_id: fleetId }) }),
    sync: () => request('/lineage/sync', { method: 'POST' })
}

// Audit API
export const auditApi = {
    getLogs: (limit = 50) => request(`/audit/logs?limit=${limit}`)
}

// Community API
export const communityApi = {
    getTgspPackages: () => request('/community/tgsp/packages')
}

export { ApiError, request, uploadFile }
