import { scenePreviewPath } from '@/api/endpoints';
import type { BatchImage } from '@/api/types';
import { isFlagged, tileStatus } from '@/features/quality/quality';
import { presetLabel } from '@/lib/format';
import { normalizeUrl } from '@/lib/settings';

const image = (patch: Partial<BatchImage>): BatchImage => ({
  id: 'i',
  position: 0,
  filename: 'a.jpg',
  status: 'done',
  error: null,
  width: 1,
  height: 1,
  attempts: 1,
  outputs: [],
  quality: null,
  timings: {},
  original_url: '/o',
  preview_url: '/p',
  cutout_url: '/c',
  ...patch,
});

const report = (verdict: 'ok' | 'warning' | 'retake') => ({
  verdict,
  score: 50,
  flags: [],
  metrics: {},
});

describe('quality helpers', () => {
  it('prefers quality verdicts over a plain done status', () => {
    expect(tileStatus(image({ quality: report('retake') }))).toBe('retake');
    expect(tileStatus(image({ quality: report('warning') }))).toBe('flagged');
    expect(tileStatus(image({ quality: report('ok') }))).toBe('done');
    expect(tileStatus(image({ status: 'processing', quality: null }))).toBe('processing');
  });

  it('flags only non-ok photos', () => {
    expect(isFlagged(image({ quality: report('warning') }))).toBe(true);
    expect(isFlagged(image({ quality: null }))).toBe(false);
  });
});

describe('formatting', () => {
  it('labels presets', () => {
    expect(presetLabel('instagram_portrait')).toBe('Instagram 4:5');
    expect(presetLabel('something_new')).toBe('something new');
  });

  it('normalises server URLs', () => {
    expect(normalizeUrl('  http://192.168.1.2:8000/// ')).toBe('http://192.168.1.2:8000');
  });

  it('builds scene preview paths', () => {
    const path = scenePreviewPath('custom', { prompt: 'pink silk', seed: 9 });
    expect(path).toContain('/v1/scenes/preview?');
    expect(path).toContain('scene=custom');
    expect(path).toContain('seed=9');
    expect(path).toContain('prompt=pink+silk');
  });
});
