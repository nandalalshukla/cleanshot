import type { PresetId } from '@/api/types';

const PRESET_LABELS: Record<PresetId, string> = {
  amazon: 'Amazon',
  flipkart: 'Flipkart',
  meesho: 'Meesho',
  instagram_portrait: 'Instagram 4:5',
  instagram_square: 'Instagram 1:1',
  instagram_story: 'Instagram story',
  webstore: 'Web store',
  custom: 'Custom',
};

export function presetLabel(id: PresetId | string): string {
  return PRESET_LABELS[id as PresetId] ?? id.replace(/_/g, ' ');
}
