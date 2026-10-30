type ClientSettings = { apiUrl: string; apiKey: string; clientId?: string };

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * Thin fetch wrapper bound to the configured worker URL.
 * All endpoints live in `endpoints.ts`; screens never call fetch directly.
 */
export class ApiClient {
  constructor(private readonly settings: ClientSettings) {}

  get baseUrl(): string {
    return this.settings.apiUrl;
  }

  /** Headers every request (including image loads and downloads) must carry. */
  get authHeaders(): Record<string, string> {
    const headers: Record<string, string> = {};
    if (this.settings.apiKey) headers['X-API-Key'] = this.settings.apiKey;
    if (this.settings.clientId) headers['X-Client-Id'] = this.settings.clientId;
    return headers;
  }

  /** Image source for expo-image, with auth headers. Accepts worker-relative paths. */
  imageSource(path: string) {
    return { uri: path.startsWith('http') ? path : this.url(path), headers: this.authHeaders };
  }

  url(path: string): string {
    return `${this.baseUrl}${path}`;
  }

  async request<T>(path: string, init: RequestInit = {}, timeoutMs = 30_000): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    let res: Response;
    try {
      res = await fetch(this.url(path), {
        ...init,
        signal: controller.signal,
        headers: { Accept: 'application/json', ...this.authHeaders, ...init.headers },
      });
    } catch (err) {
      const aborted = err instanceof Error && err.name === 'AbortError';
      throw new ApiError(
        aborted
          ? 'The server took too long to respond.'
          : `Cannot reach the CleanShot server at ${this.baseUrl}.`,
        0,
      );
    } finally {
      clearTimeout(timer);
    }

    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = (await res.json()) as { detail?: unknown };
        if (typeof body.detail === 'string') detail = body.detail;
      } catch {
        // non-JSON error body
      }
      throw new ApiError(detail || `Request failed (${res.status})`, res.status);
    }
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  }
}
