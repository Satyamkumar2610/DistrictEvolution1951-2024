// Direct Render Backend URL - avoids Vercel proxy timeout issues
const BASE_URL = process.env.NEXT_PUBLIC_API_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'https://i-ascap.onrender.com';

export class ApiError extends Error {
    constructor(public status: number, message: string) {
        super(message);
        this.name = 'ApiError';
    }
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
        const errorText = await response.text().catch(() => 'Unknown error');
        console.error(`[API] Error ${response.status}: ${errorText}`);

        if (response.status === 404) {
            throw new ApiError(404, 'Resource not found');
        }
        if (response.status >= 500) {
            throw new ApiError(response.status, `Server error: ${errorText}`);
        }
        throw new ApiError(response.status, `API Error: ${response.statusText}`);
    }

    return response.json();
}

export async function fetcher<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const cleanEndpoint = endpoint.startsWith('/') ? endpoint.slice(1) : endpoint;
    const url = `${BASE_URL}/api/v1/${cleanEndpoint}`;

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
