# CleanShot

Marketplace-ready product photos from a phone snap.

Small sellers on Meesho, Amazon, Flipkart and Instagram need white-background, centred product
photos. CleanShot takes a batch of phone photos, removes the background, centres and pads the
product to each marketplace's size, adds a soft shadow and hands back a ZIP.

| Part | Stack | Folder |
| --- | --- | --- |
| Mobile app | React Native, Expo SDK 58, Expo Router, TanStack Query | [`app/`](app) |
| Image worker | Python 3.11+, FastAPI, rembg (u2netp / isnet / BiRefNet), OpenCV | [`worker/`](worker) |

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for how the pieces fit together.

## Quick start

```bash
# 1. Worker
cd worker
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cleanshot-worker            # serves http://0.0.0.0:8000

# 2. App (in another terminal)
cd app
npm install
npx expo start
```

In the app, open **Settings** and point it at your worker, e.g. `http://192.168.1.20:8000`
(your computer's LAN IP — `localhost` on a phone means the phone itself).
