import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { PropsWithChildren } from 'react';

const STORAGE_KEY = 'cleanshot.settings.v1';

export interface AppSettings {
  /** Base URL of the CleanShot worker, e.g. http://192.168.1.20:8000 */
  apiUrl: string;
  /** Optional shared secret sent as X-API-Key. */
  apiKey: string;
  /** Random per-install id; keeps batches from different phones apart on a shared worker. */
  clientId: string;
}

function randomId(): string {
  let id = '';
  for (let i = 0; i < 4; i++)
    id += Math.floor(Math.random() * 0xffffffff)
      .toString(16)
      .padStart(8, '0');
  return id;
}

const defaultSettings: AppSettings = {
  apiUrl:
    process.env.EXPO_PUBLIC_API_URL ??
    (Constants.expoConfig?.extra?.defaultApiUrl as string | undefined) ??
    'http://localhost:8000',
  apiKey: process.env.EXPO_PUBLIC_API_KEY ?? '',
  clientId: '',
};

export function normalizeUrl(url: string): string {
  return url.trim().replace(/\/+$/, '');
}

interface SettingsContextValue {
  settings: AppSettings;
  ready: boolean;
  update: (patch: Partial<AppSettings>) => Promise<void>;
}

const SettingsContext = createContext<SettingsContextValue | null>(null);

export function SettingsProvider({ children }: PropsWithChildren) {
  const [settings, setSettings] = useState<AppSettings>(defaultSettings);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY)
      .then(async (raw) => {
        const stored = raw ? (JSON.parse(raw) as Partial<AppSettings>) : {};
        const next = { ...defaultSettings, ...stored };
        if (!next.clientId) {
          next.clientId = randomId();
          await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next));
        }
        setSettings(next);
      })
      .catch(() => undefined)
      .finally(() => setReady(true));
  }, []);

  const update = useCallback(
    async (patch: Partial<AppSettings>) => {
      const next = { ...settings, ...patch };
      next.apiUrl = normalizeUrl(next.apiUrl);
      setSettings(next);
      await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    },
    [settings],
  );

  const value = useMemo(() => ({ settings, ready, update }), [settings, ready, update]);
  // Hold rendering until persisted settings are loaded so screens never see stale defaults.
  if (!ready) return null;
  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function useSettings(): SettingsContextValue {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error('useSettings must be used inside <SettingsProvider>');
  return ctx;
}
