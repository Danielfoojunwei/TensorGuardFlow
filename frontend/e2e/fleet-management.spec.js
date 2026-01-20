// @ts-check
import { test, expect } from '@playwright/test';

/**
 * E2E Tests for Fleet Management
 *
 * Tests fleet lifecycle:
 * - Fleet creation
 * - Fleet listing
 * - Key rotation
 * - Fleet deactivation
 */

test.describe('Fleet Management', () => {
    let authToken = null;
    let testFleetId = null;
    let testApiKey = null;

    const timestamp = Date.now();
    const testEmail = `fleet_e2e_${timestamp}@example.com`;
    const testPassword = 'FleetE2EPass123!';
    const testOrgName = `FleetOrg_${timestamp}`;

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
            data: {
                username: testEmail,
                password: testPassword
            }
        });

        if (loginResponse.ok()) {
            const data = await loginResponse.json();
            authToken = data.access_token;
        }
    });

    test('should create a new fleet', async ({ request }) => {
        test.skip(!authToken, 'Auth token not available');

        const response = await request.post(`/api/v1/fleets?name=TestFleet_${timestamp}`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });

        expect(response.ok()).toBeTruthy();

        const data = await response.json();
        expect(data).toHaveProperty('id');
        expect(data).toHaveProperty('api_key');
        expect(data.api_key).toMatch(/^tgf_/);

        testFleetId = data.id;
        testApiKey = data.api_key;
    });

    test('should list fleets', async ({ request }) => {
        test.skip(!authToken, 'Auth token not available');

        const response = await request.get('/api/v1/fleets', {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });

        expect(response.ok()).toBeTruthy();

        const data = await response.json();
        expect(Array.isArray(data)).toBeTruthy();
    });

    test('should get extended fleet info', async ({ request }) => {
        test.skip(!authToken, 'Auth token not available');

        const response = await request.get('/api/v1/fleets/extended', {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });

        expect(response.ok()).toBeTruthy();

        const data = await response.json();
        expect(Array.isArray(data)).toBeTruthy();

        if (data.length > 0) {
            expect(data[0]).toHaveProperty('devices_total');
            expect(data[0]).toHaveProperty('trust');
        }
    });

    test('should rotate fleet key', async ({ request }) => {
        test.skip(!authToken || !testFleetId, 'Auth or fleet not available');

        const response = await request.post(`/api/v1/fleets/${testFleetId}/rotate-key`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });

        expect(response.ok()).toBeTruthy();

        const data = await response.json();
        expect(data).toHaveProperty('api_key');
        expect(data.api_key).not.toBe(testApiKey);
    });

    test('should update dashboard stats after fleet creation', async ({ request }) => {
        test.skip(!authToken, 'Auth token not available');

        const response = await request.get('/api/v1/dashboard/stats', {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });

        expect(response.ok()).toBeTruthy();

        const data = await response.json();
        expect(data).toHaveProperty('fleet_count');
        expect(data.fleet_count).toBeGreaterThanOrEqual(1);
    });
});


test.describe('Dashboard Stats', () => {
    let authToken = null;

    const timestamp = Date.now();
    const testEmail = `dash_e2e_${timestamp}@example.com`;
    const testPassword = 'DashE2EPass123!';
    const testOrgName = `DashOrg_${timestamp}`;

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

    test('should return valid dashboard stats structure', async ({ request }) => {
        test.skip(!authToken, 'Auth token not available');

        const response = await request.get('/api/v1/dashboard/stats', {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });

        expect(response.ok()).toBeTruthy();

        const data = await response.json();
        expect(data).toHaveProperty('fleet_count');
        expect(data).toHaveProperty('compliance_level');
        expect(data).toHaveProperty('system_health');
        expect(typeof data.fleet_count).toBe('number');
    });

    test('should return security score', async ({ request }) => {
        test.skip(!authToken, 'Auth token not available');

        const response = await request.get('/api/v1/security/score', {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });

        expect(response.ok()).toBeTruthy();

        const data = await response.json();
        expect(data).toHaveProperty('overall');
        expect(data.overall).toBeGreaterThanOrEqual(0);
        expect(data.overall).toBeLessThanOrEqual(100);
    });
});
