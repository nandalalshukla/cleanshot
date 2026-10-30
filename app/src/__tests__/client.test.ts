import { ApiClient, ApiError } from '@/api/client';

const settings = { apiUrl: 'http://worker:8000', apiKey: 'k', clientId: 'c1' };

function mockFetch(impl: (url: string, init: RequestInit) => Promise<Partial<Response>>) {
  globalThis.fetch = jest.fn(impl) as unknown as typeof fetch;
}

describe('ApiClient', () => {
  it('sends auth and client headers and parses JSON', async () => {
    mockFetch(async () => ({ ok: true, status: 200, json: async () => ({ status: 'ok' }) }));
    const api = new ApiClient(settings);
    await expect(api.request('/health')).resolves.toEqual({ status: 'ok' });

    const [url, init] = (globalThis.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe('http://worker:8000/health');
    expect(init.headers).toMatchObject({ 'X-API-Key': 'k', 'X-Client-Id': 'c1' });
  });

  it('surfaces the server detail message as ApiError', async () => {
    mockFetch(async () => ({
      ok: false,
      status: 409,
      statusText: 'Conflict',
      json: async () => ({ detail: 'Add at least one photo first' }),
    }));
    const err = await new ApiClient(settings).request<never>('/x').catch((e: ApiError) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(409);
    expect(err.message).toBe('Add at least one photo first');
  });

  it('reports unreachable servers clearly', async () => {
    mockFetch(async () => {
      throw new TypeError('Network request failed');
    });
    const err = await new ApiClient(settings).request<never>('/x').catch((e: ApiError) => e);
    expect(err.status).toBe(0);
    expect(err.message).toContain('Cannot reach the CleanShot server');
  });

  it('builds image sources for relative and absolute paths', () => {
    const api = new ApiClient({ apiUrl: 'http://w', apiKey: '' });
    expect(api.imageSource('/v1/a.jpg')).toEqual({ uri: 'http://w/v1/a.jpg', headers: {} });
    expect(api.imageSource('https://cdn/x.jpg').uri).toBe('https://cdn/x.jpg');
  });
});
