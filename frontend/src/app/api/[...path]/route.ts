import { NextRequest, NextResponse } from 'next/server';
import { resolveServerApiOrigin } from '../../services/api/config';

const API_ORIGIN = resolveServerApiOrigin();

async function handler(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
    // In Next.js 15+, params is a Promise and must be awaited.
    const resolvedParams = await params;
    const path = resolvedParams.path.join('/');

    // Construct target URL
    // Incoming request: /api/v1/some/endpoint
    // Route handler matches: /api/[...path]
    // params.path: ['v1', 'some', 'endpoint']
    // Target: https://i-ascap.onrender.com/api/v1/some/endpoint

    const targetUrl = `${API_ORIGIN}/api/${path}${request.nextUrl.search}`;

    console.log(`[API Proxy] ${request.method} ${targetUrl}`);

    try {
        const response = await fetch(targetUrl, {
            method: request.method,
            headers: {
                'Content-Type': 'application/json',
                // Forward auth if present
                ...(request.headers.get('Authorization') ? { 'Authorization': request.headers.get('Authorization')! } : {}),
                ...(request.headers.get('X-API-Key') ? { 'X-API-Key': request.headers.get('X-API-Key')! } : {}),
            },
            // Forward body if not GET/HEAD
            body: ['GET', 'HEAD'].includes(request.method) ? undefined : await request.text(),
        });

        const data = await response.text();

        return new NextResponse(data, {
            status: response.status,
            headers: {
                'Content-Type': response.headers.get('Content-Type') || 'application/json',
            },
        });
    } catch (error) {
        console.error('[API Proxy Error]', error);
        return NextResponse.json({ error: 'Proxy failed', details: String(error) }, { status: 502 });
    }
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const DELETE = handler;
export const PATCH = handler;
