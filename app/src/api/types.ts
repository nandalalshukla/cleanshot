/** Wire types mirrored from the worker's pydantic schemas (worker/cleanshot_worker/api/schemas.py). */

export interface HealthResponse {
  status: 'ok';
  version: string;
}

export type SegmentationModel = 'u2netp' | 'isnet-general-use' | 'birefnet-general-lite';

export interface ModelInfo {
  id: SegmentationModel;
  label: string;
  description: string;
  approx_size_mb: number;
}

export type PresetId =
  | 'amazon'
  | 'flipkart'
  | 'meesho'
  | 'instagram_portrait'
  | 'instagram_square'
  | 'instagram_story'
  | 'webstore'
  | 'custom';

export type Alignment = 'center' | 'bottom';
export type OutputFormat = 'jpeg' | 'png' | 'webp';
export type ShadowStyle = 'none' | 'ground' | 'drop';

export interface Preset {
  id: PresetId;
  label: string;
  marketplace: string;
  width: number;
  height: number;
  aspect: string;
  background_color: string;
  fill: number;
  alignment: Alignment;
  white_background_required: boolean;
  description: string;
}

/** Mirrors ProcessOptions in worker/cleanshot_worker/pipeline/options.py. */
export interface ProcessOptions {
  model: SegmentationModel;
  refine_edges: boolean;
  presets: PresetId[];
  custom_width: number;
  custom_height: number;
  fill: number | null;
  alignment: Alignment | null;
  background_color: string | null;
  output_format: OutputFormat;
  shadow: ShadowStyle;
  shadow_opacity: number;
}

export type BatchStatus = 'draft' | 'processing' | 'completed' | 'cancelled';
export type ImageStatus = 'uploaded' | 'queued' | 'processing' | 'done' | 'failed' | 'cancelled';

export interface OutputFile {
  preset: PresetId;
  filename: string;
  width: number;
  height: number;
  url: string;
}

export interface BatchImage {
  id: string;
  position: number;
  filename: string;
  status: ImageStatus;
  error: string | null;
  width: number;
  height: number;
  attempts: number;
  outputs: OutputFile[];
  quality: Record<string, unknown> | null;
  timings: Record<string, number>;
  original_url: string;
  preview_url: string | null;
  cutout_url: string | null;
}

export interface BatchSummary {
  id: string;
  name: string;
  status: BatchStatus;
  created_at: number;
  updated_at: number;
  total: number;
  counts: Record<ImageStatus, number>;
  progress: number;
  cover_url: string | null;
  download_url: string;
}

export interface Batch extends BatchSummary {
  options: ProcessOptions;
  images: BatchImage[];
}
