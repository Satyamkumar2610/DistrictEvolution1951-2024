import { resolvePublicApiOrigin, toApiV1Url } from './config';

const BASE_URL =
    typeof window === 'undefined'
        ? toApiV1Url(resolvePublicApiOrigin())
        : '/api/v1';

export class ApiError extends Error {
    constructor(public status: number, message: string) {
        super(message);
        this.name = 'ApiError';
    }
}

function parseDetail(detail: unknown): string | null {
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
        const parts = detail
            .map((item) => {
                if (typeof item === 'string') return item;
                if (item && typeof item === 'object') {
                    const record = item as Record<string, unknown>;
                    if (typeof record.msg === 'string') return record.msg;
                }
                return null;
            })
            .filter((item): item is string => Boolean(item));
        return parts.length > 0 ? parts.join('; ') : null;
    }
    return null;
}

function parseApiMessage(payload: Record<string, unknown>): string | null {
    const nestedError = payload.error;
    const nestedErrorMessage =
        nestedError && typeof nestedError === 'object'
            ? (nestedError as Record<string, unknown>).message
            : null;

    return (
        parseDetail(payload.detail) ||
        (typeof payload.message === 'string' ? payload.message : null) ||
        (typeof payload.error === 'string' ? payload.error : null) ||
        (typeof nestedErrorMessage === 'string' ? nestedErrorMessage : null)
    );
}

async function fetchOnce<T>(url: string, options: RequestInit = {}): Promise<T> {
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
    };

    const response = await fetch(url, {
        ...options,
        headers,
        signal: AbortSignal.timeout ? AbortSignal.timeout(60000) : undefined,
    });

    if (!response.ok) {
        const contentType = response.headers.get('Content-Type') || '';
        let errorText = 'Unknown error';
        let message: string | null = null;

        if (contentType.includes('application/json')) {
            const payload = await response.json().catch(() => null) as Record<string, unknown> | null;
            if (payload) {
                message = parseApiMessage(payload);
                errorText = JSON.stringify(payload);
            }
        } else {
            errorText = await response.text().catch(() => 'Unknown error');
            message = errorText || null;
        }

        console.error(`[API] Error ${response.status}: ${errorText}`);

        if (response.status === 404) {
            throw new ApiError(404, message || 'Resource not found');
        }
        if (response.status >= 500) {
            throw new ApiError(response.status, message ? `Server error: ${message}` : `Server error: ${errorText}`);
        }
        throw new ApiError(response.status, message || `API Error: ${response.statusText}`);
    }

    return response.json();
}

export async function fetcher<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const cleanEndpoint = endpoint.startsWith('/') ? endpoint.slice(1) : endpoint;
    const url = `${BASE_URL}/${cleanEndpoint}`;

    if (process.env.NODE_ENV === 'development') {
        console.log(`[API] Fetching: ${url}`);
    }

    try {
        return await fetchOnce<T>(url, options);
    } catch (error) {
        if (error instanceof ApiError) throw error;
        console.warn(`[API] Retrying after network error:`, error);
        await new Promise(r => setTimeout(r, 2000));
        try {
            return await fetchOnce<T>(url, options);
        } catch (retryError) {
            if (retryError instanceof ApiError) throw retryError;
            console.warn(`[API] Retry failed (Backend offline?):`, retryError);
            throw new ApiError(0, `Network error - backend may be offline. Please retry.`);
        }
    }
}
