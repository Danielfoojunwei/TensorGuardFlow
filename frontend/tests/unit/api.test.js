/**
 * API Service Unit Tests
 *
 * Tests for the API client including:
 * - Token persistence in localStorage
 * - Authorization header attachment
 * - 401 error handling
 * - ApiError construction
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Mock fetch globally before importing
const mockFetch = vi.fn()
global.fetch = mockFetch

// Mock window.location for 401 redirect tests
const mockLocation = { href: '' }
Object.defineProperty(window, 'location', {
    value: mockLocation,
    writable: true
})

// Import after setting up mocks
import { ApiError, request } from '@/services/api.js'


describe('ApiError', () => {
    it('should construct with message, status, and data', () => {
        const error = new ApiError('Not found', 404, { detail: 'Resource missing' })

        expect(error.message).toBe('Not found')
        expect(error.status).toBe(404)
        expect(error.data).toEqual({ detail: 'Resource missing' })
        expect(error.name).toBe('ApiError')
    })

    it('should work without optional data parameter', () => {
        const error = new ApiError('Server error', 500)

        expect(error.message).toBe('Server error')
        expect(error.status).toBe(500)
        expect(error.data).toBeNull()
    })

    it('should be instanceof Error', () => {
        const error = new ApiError('Test', 400)
        expect(error instanceof Error).toBe(true)
    })

    it('should include correlation ID', () => {
        const error = new ApiError('Test', 400, null, 'corr-123')
        expect(error.correlationId).toBe('corr-123')
    })
})


describe('Token Persistence', () => {
    beforeEach(() => {
        localStorage.clear()
        mockFetch.mockReset()
    })

    afterEach(() => {
        localStorage.clear()
    })

    it('should store auth token in localStorage', () => {
        const token = 'test_jwt_token_12345'
        localStorage.setItem('auth_token', token)

        expect(localStorage.getItem('auth_token')).toBe(token)
    })

    it('should retrieve stored auth token', () => {
        const token = 'another_jwt_token_67890'
        localStorage.setItem('auth_token', token)

        const retrieved = localStorage.getItem('auth_token')
        expect(retrieved).toBe(token)
    })

    it('should return null for missing token', () => {
        const token = localStorage.getItem('auth_token')
        expect(token).toBeNull()
    })

    it('should overwrite existing token', () => {
        localStorage.setItem('auth_token', 'old_token')
        localStorage.setItem('auth_token', 'new_token')

        expect(localStorage.getItem('auth_token')).toBe('new_token')
    })

    it('should clear token on removeItem', () => {
        localStorage.setItem('auth_token', 'token_to_remove')
        localStorage.removeItem('auth_token')

        expect(localStorage.getItem('auth_token')).toBeNull()
    })
})


describe('API Request Authorization Headers', () => {
    beforeEach(() => {
        localStorage.clear()
        mockFetch.mockReset()
    })

    afterEach(() => {
        localStorage.clear()
    })

    it('should attach Bearer token when auth_token exists', async () => {
        const token = 'valid_jwt_token'
        localStorage.setItem('auth_token', token)

        mockFetch.mockResolvedValueOnce({
            ok: true,
            headers: new Headers({ 'content-type': 'application/json' }),
            json: async () => ({ data: 'test' })
        })

        await request('/test')

        expect(mockFetch).toHaveBeenCalledWith(
            '/api/v1/test',
            expect.objectContaining({
                headers: expect.objectContaining({
                    'Authorization': `Bearer ${token}`
                })
            })
        )
    })

    it('should not attach Authorization header when no token', async () => {
        mockFetch.mockResolvedValueOnce({
            ok: true,
            headers: new Headers({ 'content-type': 'application/json' }),
            json: async () => ({ data: 'test' })
        })

        await request('/test')

        const callArgs = mockFetch.mock.calls[0][1]
        expect(callArgs.headers['Authorization']).toBeUndefined()
    })

    it('should include Content-Type header', async () => {
        mockFetch.mockResolvedValueOnce({
            ok: true,
            headers: new Headers({ 'content-type': 'application/json' }),
            json: async () => ({})
        })

        await request('/test')

        expect(mockFetch).toHaveBeenCalledWith(
            '/api/v1/test',
            expect.objectContaining({
                headers: expect.objectContaining({
                    'Content-Type': 'application/json'
                })
            })
        )
    })
})


describe('API Request Error Handling', () => {
    beforeEach(() => {
        localStorage.clear()
        mockFetch.mockReset()
        mockLocation.href = ''
    })

    afterEach(() => {
        localStorage.clear()
    })

    it('should throw ApiError on 401 Unauthorized', async () => {
        mockFetch.mockResolvedValueOnce({
            ok: false,
            status: 401,
            json: async () => ({ detail: 'Invalid credentials' })
        })

        await expect(request('/auth/me', { retry: false })).rejects.toThrow(ApiError)
    })

    it('should redirect to login on 401', async () => {
        mockFetch.mockResolvedValueOnce({
            ok: false,
            status: 401,
            json: async () => ({ detail: 'Invalid credentials' })
        })

        try {
            await request('/auth/me', { retry: false })
        } catch (error) {
            expect(mockLocation.href).toBe('/login')
        }
    })

    it('should include status code in ApiError', async () => {
        mockFetch.mockResolvedValueOnce({
            ok: false,
            status: 403,
            headers: new Headers(),
            json: async () => ({ detail: 'Forbidden' })
        })

        try {
            await request('/protected', { retry: false })
        } catch (error) {
            expect(error.status).toBe(403)
        }
    })

    it('should handle 404 Not Found', async () => {
        mockFetch.mockResolvedValueOnce({
            ok: false,
            status: 404,
            headers: new Headers(),
            json: async () => ({ detail: 'Not found' })
        })

        await expect(request('/nonexistent', { retry: false })).rejects.toThrow(ApiError)
    })

    it('should handle 500 Server Error', async () => {
        mockFetch.mockResolvedValueOnce({
            ok: false,
            status: 500,
            headers: new Headers(),
            json: async () => ({ detail: 'Internal server error' })
        })

        try {
            await request('/error', { retry: false })
        } catch (error) {
            expect(error.status).toBe(500)
        }
    })

    it('should handle network errors', async () => {
        mockFetch.mockRejectedValueOnce(new TypeError('Network failure'))

        await expect(request('/test', { method: 'POST', retry: false })).rejects.toThrow()
    })

    it('should handle non-JSON error responses', async () => {
        mockFetch.mockResolvedValueOnce({
            ok: false,
            status: 502,
            headers: new Headers(),
            json: async () => { throw new Error('Not JSON') }
        })

        try {
            await request('/bad-gateway', { retry: false })
        } catch (error) {
            expect(error.status).toBe(502)
        }
    })
})


describe('API Request Success Handling', () => {
    beforeEach(() => {
        localStorage.clear()
        mockFetch.mockReset()
    })

    it('should return JSON data on success', async () => {
        const responseData = { id: 1, name: 'Test Fleet' }

        mockFetch.mockResolvedValueOnce({
            ok: true,
            headers: new Headers({ 'content-type': 'application/json' }),
            json: async () => responseData
        })

        const result = await request('/fleets/1')
        expect(result).toEqual(responseData)
    })

    it('should handle empty responses', async () => {
        mockFetch.mockResolvedValueOnce({
            ok: true,
            headers: new Headers({ 'content-type': 'text/plain' }),
            json: async () => null
        })

        const result = await request('/empty')
        expect(result).toBeNull()
    })

    it('should make POST requests correctly', async () => {
        mockFetch.mockResolvedValueOnce({
            ok: true,
            headers: new Headers({ 'content-type': 'application/json' }),
            json: async () => ({ success: true })
        })

        await request('/create', {
            method: 'POST',
            body: JSON.stringify({ name: 'test' })
        })

        expect(mockFetch).toHaveBeenCalledWith(
            '/api/v1/create',
            expect.objectContaining({
                method: 'POST',
                body: JSON.stringify({ name: 'test' })
            })
        )
    })
})
