import type { ApiClient } from './client';
import type { HealthResponse, ModelInfo, Preset } from './types';

export const getHealth = (api: ApiClient) => api.request<HealthResponse>('/health', {}, 8_000);

export const listPresets = (api: ApiClient) => api.request<Preset[]>('/v1/presets');
export const listModels = (api: ApiClient) => api.request<ModelInfo[]>('/v1/models');
