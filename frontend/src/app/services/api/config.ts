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

export function toApiV1Url(origin: string): string {
  return `${normalizeOrigin(origin)}/api/v1`;
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
