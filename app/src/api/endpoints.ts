/** One function per worker endpoint. Screens and hooks use these, never raw fetch. */
import { Platform } from 'react-native';

import type { ApiClient } from './client';
import type {
  Batch,
  BatchImage,
  BatchSummary,
  HealthResponse,
  ModelInfo,
  Preset,
  ProcessOptions,
} from './types';

export const getHealth = (api: ApiClient) => api.request<HealthResponse>('/health', {}, 8_000);

export const listPresets = (api: ApiClient) => api.request<Preset[]>('/v1/presets');
export const listModels = (api: ApiClient) => api.request<ModelInfo[]>('/v1/models');

// ---- batches ---------------------------------------------------------------------------------

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export const listBatches = (api: ApiClient) => api.request<BatchSummary[]>('/v1/batches');

export const getBatch = (api: ApiClient, id: string) => api.request<Batch>(`/v1/batches/${id}`);

export const createBatch = (api: ApiClient, options: ProcessOptions, name?: string) =>
  api.request<Batch>('/v1/batches', json({ name: name || null, options }));

export const startBatch = (api: ApiClient, id: string) =>
  api.request<Batch>(`/v1/batches/${id}/start`, { method: 'POST' });

export const cancelBatch = (api: ApiClient, id: string) =>
  api.request<Batch>(`/v1/batches/${id}/cancel`, { method: 'POST' });

export const retryFailed = (api: ApiClient, id: string) =>
  api.request<Batch>(`/v1/batches/${id}/retry`, { method: 'POST' });

export const deleteBatch = (api: ApiClient, id: string) =>
  api.request<void>(`/v1/batches/${id}`, { method: 'DELETE' });

// ---- images ----------------------------------------------------------------------------------

export interface LocalPhoto {
  uri: string;
  name: string;
  mimeType: string;
}

async function photoPart(photo: LocalPhoto): Promise<Blob> {
  if (Platform.OS === 'web') {
    return await (await fetch(photo.uri)).blob();
  }
  // React Native's fetch streams files from disk when given { uri, name, type }.
  return { uri: photo.uri, name: photo.name, type: photo.mimeType } as unknown as Blob;
}

/** Uploads take longer than JSON calls on mobile data, so allow up to 2 minutes each. */
const UPLOAD_TIMEOUT = 120_000;

export async function uploadPhoto(
  api: ApiClient,
  batchId: string,
  photo: LocalPhoto,
  position?: number,
) {
  const form = new FormData();
  form.append('files', await photoPart(photo), photo.name);
  // Uploads run in parallel; the explicit position keeps the seller's chosen order.
  if (position !== undefined) form.append('position', String(position));
  const [image] = await api.request<BatchImage[]>(
    `/v1/batches/${batchId}/images`,
    { method: 'POST', body: form },
    UPLOAD_TIMEOUT,
  );
  return image!;
}

export async function replacePhoto(
  api: ApiClient,
  batchId: string,
  imageId: string,
  photo: LocalPhoto,
) {
  const form = new FormData();
  form.append('file', await photoPart(photo), photo.name);
  return api.request<BatchImage>(
    `/v1/batches/${batchId}/images/${imageId}`,
    { method: 'PUT', body: form },
    UPLOAD_TIMEOUT,
  );
}

export const retryImage = (api: ApiClient, batchId: string, imageId: string) =>
  api.request<BatchImage>(`/v1/batches/${batchId}/images/${imageId}/retry`, { method: 'POST' });

export const deleteImage = (api: ApiClient, batchId: string, imageId: string) =>
  api.request<void>(`/v1/batches/${batchId}/images/${imageId}`, { method: 'DELETE' });
