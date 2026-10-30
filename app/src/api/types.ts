/** Wire types mirrored from the worker's pydantic schemas (worker/cleanshot_worker/api/schemas.py). */

export interface HealthResponse {
  status: 'ok';
  version: string;
}
