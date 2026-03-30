const DEFAULT_API_ORIGIN = "https://i-ascap.onrender.com";

function stripTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

function stripApiSuffix(value: string): string {
  return value.replace(/\/api\/v1\/?$/, "").replace(/\/api\/?$/, "");
}

function normalizeOrigin(value: string): string {
  return stripApiSuffix(stripTrailingSlash(value));
}

function normalizePath(path: string): string {
  return path.startsWith("/") ? path : `/${path}`;
}

export function toApiV1Url(origin: string): string {
  return `${normalizeOrigin(origin)}/api/v1`;
}

export function buildApiV1Url(origin: string, path: string): string {
  return `${toApiV1Url(origin)}${normalizePath(path)}`;
}

export function buildOriginUrl(origin: string, path: string): string {
  return `${normalizeOrigin(origin)}${normalizePath(path)}`;
}

export function resolvePublicApiOrigin(): string {
  return normalizeOrigin(
    process.env.NEXT_PUBLIC_API_URL ||
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      DEFAULT_API_ORIGIN,
  );
}

export function resolveServerApiOrigin(): string {
  return normalizeOrigin(
    process.env.ASCAP_API_URL ||
      process.env.API_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      DEFAULT_API_ORIGIN,
  );
}

export function buildPublicApiV1Url(path: string): string {
  return buildApiV1Url(resolvePublicApiOrigin(), path);
}

export function buildPublicOriginUrl(path: string): string {
  return buildOriginUrl(resolvePublicApiOrigin(), path);
}

export function buildServerApiV1Url(path: string): string {
  return buildApiV1Url(resolveServerApiOrigin(), path);
}
