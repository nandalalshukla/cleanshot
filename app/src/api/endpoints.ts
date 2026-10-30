import type { ApiClient } from './client';
import type { HealthResponse } from './types';

export const getHealth = (api: ApiClient) => api.request<HealthResponse>('/health', {}, 8_000);
