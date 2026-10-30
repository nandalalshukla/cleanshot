# CleanShot app

Expo (SDK 58) + Expo Router app for sellers: pick product photos, choose marketplace sizes and
a background, watch the batch process, retake flagged photos and download a ZIP.

## Run

```bash
npm install
cp .env.example .env        # optional: default worker URL
npx expo start              # press a / i, or scan the QR code with Expo Go
```

Open **Settings** in the app and enter your worker URL, e.g. `http://192.168.1.20:8000`
(the computer's LAN IP — `localhost` on a phone is the phone itself).

## Scripts

| Command | What it does |
| --- | --- |
| `npm run typecheck` | TypeScript, strict |
| `npm run lint` | ESLint (`eslint-config-expo`) |
| `npm test` | Jest unit tests (`jest-expo`) |
| `npm run format` | Prettier |

## Structure

```
src/
  app/                 routes (Expo Router): home, settings, batch/new, batch/[id], batch/[id]/[imageId]
  api/                 ApiClient, one function per endpoint, wire types mirroring the worker
  components/          themed UI kit (Button, Card, Chip, Segmented, ProgressBar, RemoteImage…)
  features/
    batches/           queries with smart polling, create/upload flow, batch actions
    options/           options form, scene picker, remembered defaults
    photos/            gallery/camera picking and pre-upload downscaling
    quality/           quality verdict helpers and panel
  lib/                 settings store, query client, download/share, formatting
  theme/               colours (light/dark), spacing, typography
```

Screens never call `fetch` directly: they use hooks in `features/*`, which use `api/endpoints.ts`.

## Builds

[EAS](https://docs.expo.dev/eas/) profiles live in `eas.json`:

```bash
npx eas-cli@latest build --profile preview --platform android   # installable APK
npx eas-cli@latest build --profile production
```

Android allows plain-HTTP traffic (`expo-build-properties`) so the app can talk to a worker on
the shop's local network. Use HTTPS for any worker exposed to the internet.
