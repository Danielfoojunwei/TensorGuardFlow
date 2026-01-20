// @ts-check
import { test, expect } from '@playwright/test';

/**
 * E2E Tests for Telemetry Ingestion
 *
 * Tests the complete telemetry flow:
 * - Fleet API key authentication
 * - Telemetry batch ingestion
 * - Dashboard updates
 */

test.describe('Telemetry Ingestion', () => {
    let authToken = null;
    let fleetApiKey = null;
    let fleetId = null;

    const timestamp = Date.now();
    const testEmail = `telem_e2e_${timestamp}@example.com`;
    const testPassword = 'TelemE2EPass123!';
    const testOrgName = `TelemOrg_${timestamp}`;

    test.beforeAll(async ({ request }) => {
        // Create org
        await request.post('/api/v1/onboarding/init', {
            params: {
                name: testOrgName,
                admin_email: testEmail,
                admin_pass: testPassword
            }
        });

        // Login
        const loginResponse = await request.post('/api/v1/auth/token', {
            data: { username: testEmail, password: testPassword }
        });

        if (loginResponse.ok()) {
            authToken = (await loginResponse.json()).access_token;
        }

        // Create fleet
        if (authToken) {
            const fleetResponse = await request.post(`/api/v1/fleets?name=TelemFleet_${timestamp}`, {
                headers: { 'Authorization': `Bearer ${authToken}` }
            });

            if (fleetResponse.ok()) {
                const data = await fleetResponse.json();
                fleetId = data.id;
                fleetApiKey = data.api_key;
            }
        }
    });

    test('should reject telemetry without auth', async ({ request }) => {
        const response = await request.post('/api/v1/telemetry/ingest', {
            data: {
                batch_id: `batch_noauth_${timestamp}`,
                messages: []
            }
        });

        expect(response.status()).toBe(401);
    });

    test('should reject telemetry with invalid Fleet key', async ({ request }) => {
        const response = await request.post('/api/v1/telemetry/ingest', {
            headers: {
                'Authorization': 'Fleet invalid_key_12345'
            },
            data: {
                batch_id: `batch_invalid_${timestamp}`,
                messages: []
            }
        });

        expect(response.status()).toBe(401);
    });

    test('should accept telemetry with valid Fleet key', async ({ request }) => {
        test.skip(!fleetApiKey, 'Fleet API key not available');

        const response = await request.post('/api/v1/telemetry/ingest', {
            headers: {
                'Authorization': `Fleet ${fleetApiKey}`
            },
            data: {
                batch_id: `batch_valid_${timestamp}`,
                device_info: { device_id: `device_${timestamp}` },
                messages: []
            }
        });

        expect(response.ok()).toBeTruthy();

        const data = await response.json();
        expect(data).toHaveProperty('accepted');
        expect(data).toHaveProperty('rejected');
    });

    test('should handle telemetry batch with messages', async ({ request }) => {
        test.skip(!fleetApiKey, 'Fleet API key not available');

        const response = await request.post('/api/v1/telemetry/ingest', {
            headers: {
                'Authorization': `Fleet ${fleetApiKey}`
            },
            data: {
                batch_id: `batch_messages_${timestamp}`,
                device_info: { device_id: `device_${timestamp}` },
                messages: [
                    {
                        topic: 'telemetry.stage',
                        timestamp_ns: Date.now() * 1000000,
                        payload: {
                            device_id: `device_${timestamp}`,
                            stage: 'capture',
                            status: 'ok',
                            latency_ms: 25.5
                        },
                        priority: 0
                    },
                    {
                        topic: 'telemetry.system',
                        timestamp_ns: Date.now() * 1000000,
                        payload: {
                            device_id: `device_${timestamp}`,
                            cpu_pct: 45.2,
                            mem_pct: 62.1
                        },
                        priority: 0
                    }
                ]
            }
        });

        expect(response.ok()).toBeTruthy();

        const data = await response.json();
        expect(data.accepted).toBe(2);
        expect(data.rejected).toBe(0);
    });

    test('should handle duplicate batch (idempotency)', async ({ request }) => {
        test.skip(!fleetApiKey, 'Fleet API key not available');

        const batchId = `batch_idempotent_${timestamp}`;

        // First submission
        const response1 = await request.post('/api/v1/telemetry/ingest', {
            headers: { 'Authorization': `Fleet ${fleetApiKey}` },
            data: {
                batch_id: batchId,
                device_info: { device_id: `device_${timestamp}` },
                messages: [{
                    topic: 'telemetry.stage',
                    timestamp_ns: Date.now() * 1000000,
                    payload: {
                        device_id: `device_${timestamp}`,
                        stage: 'capture',
                        status: 'ok',
                        latency_ms: 10
                    },
                    priority: 0
                }]
            }
        });

        expect(response1.ok()).toBeTruthy();
        const data1 = await response1.json();
        expect(data1.is_duplicate).toBe(false);

        // Second submission with same batch_id
        const response2 = await request.post('/api/v1/telemetry/ingest', {
            headers: { 'Authorization': `Fleet ${fleetApiKey}` },
            data: {
                batch_id: batchId,
                device_info: { device_id: `device_${timestamp}` },
                messages: [{
                    topic: 'telemetry.stage',
                    timestamp_ns: Date.now() * 1000000,
                    payload: {
                        device_id: `device_${timestamp}`,
                        stage: 'capture',
                        status: 'ok',
                        latency_ms: 10
                    },
                    priority: 0
                }]
            }
        });

        expect(response2.ok()).toBeTruthy();
        const data2 = await response2.json();
        expect(data2.is_duplicate).toBe(true);
        expect(data2.accepted).toBe(0);
    });

    test('should reject invalid topic', async ({ request }) => {
        test.skip(!fleetApiKey, 'Fleet API key not available');

        const response = await request.post('/api/v1/telemetry/ingest', {
            headers: { 'Authorization': `Fleet ${fleetApiKey}` },
            data: {
                batch_id: `batch_invalid_topic_${timestamp}`,
                device_info: { device_id: `device_${timestamp}` },
                messages: [{
                    topic: 'telemetry.invalid_topic_xyz',
                    timestamp_ns: Date.now() * 1000000,
                    payload: { device_id: `device_${timestamp}` },
                    priority: 0
                }]
            }
        });

        expect(response.ok()).toBeTruthy();

        const data = await response.json();
        expect(data.rejected).toBe(1);
        expect(data.rejections[0].reason).toContain('unknown topic');
    });
});


test.describe('Telemetry Query Endpoints', () => {
    let authToken = null;

    const timestamp = Date.now();
    const testEmail = `query_e2e_${timestamp}@example.com`;
    const testPassword = 'QueryE2EPass123!';
    const testOrgName = `QueryOrg_${timestamp}`;

    test.beforeAll(async ({ request }) => {
        await request.post('/api/v1/onboarding/init', {
            params: {
                name: testOrgName,
                admin_email: testEmail,
                admin_pass: testPassword
            }
        });

        const loginResponse = await request.post('/api/v1/auth/token', {
            data: { username: testEmail, password: testPassword }
        });

        if (loginResponse.ok()) {
            authToken = (await loginResponse.json()).access_token;
        }
    });

    test('should query pipeline telemetry', async ({ request }) => {
        test.skip(!authToken, 'Auth token not available');

        const response = await request.get('/api/v1/telemetry/pipeline', {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });

        expect(response.ok()).toBeTruthy();
        expect(Array.isArray(await response.json())).toBeTruthy();
    });

    test('should query edge telemetry', async ({ request }) => {
        test.skip(!authToken, 'Auth token not available');

        const response = await request.get('/api/v1/telemetry/edge', {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });

        expect(response.ok()).toBeTruthy();
    });

    test('should query system telemetry', async ({ request }) => {
        test.skip(!authToken, 'Auth token not available');

        const response = await request.get('/api/v1/telemetry/system', {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });

        expect(response.ok()).toBeTruthy();
    });

    test('should query devices', async ({ request }) => {
        test.skip(!authToken, 'Auth token not available');

        const response = await request.get('/api/v1/telemetry/devices', {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });

        expect(response.ok()).toBeTruthy();
    });
});
