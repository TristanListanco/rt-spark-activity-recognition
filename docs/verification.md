# Final verification (M8)

The checklist from the project plan, run against the Azure deployment on 2026-10-31, 22:38–22:48 (Manila), with the RT-Spark on home Wi-Fi and the 3-class model from M7. Each line says how it was checked and what came out.

| # | Check | How | Result |
|---|---|---|---|
| 1 | The board publishes once per second in the contract format | Subscribed to `activity/rtspark-01/#` on the Azure broker for 30 s; every message validated with the classifier's own parser (`cloud/classifier/payload.py`) | ✅ 31 IMU messages, 0 invalid, 5 samples each at `rate_hz` 5, median interval 1.00 s (max 1.09 s). 30 predictions published back to the board |
| 2 | `/api/latest` is live and follows the activity | `curl` against the VM; a walk → run replay of real Kaggle rows through the stack | ✅ Newest prediction 1.8 s old, response in 0.3 s. In the replay the label flipped to run about 2 s after the data did (4 s window). The board's own stream was classified idle at 99–100% throughout the check. Walk ↔ run with the board on the wrist: ⏳ shown in the demo video |
| 3 | `/api/history` returns rows and the database grows once per second | `/api/summary` totals 30 s apart | ✅ 30 rows in 30.1 s (1.00 per second); history returns the newest rows first |
| 4 | The app shows live data and history, and handles network loss | Pixel 7 (Android 17) on Wi-Fi, app on its default (Azure) address; then pointed at an unreachable address | ✅ Live, Today and History show the board's data ([screenshots](../README.md#android-app)). With the API unreachable, the app shows "Can't reach the server" and keeps running. On mobile data: ⏳ checked by hand |
| 5 | The system recovers from restarts by itself | `docker compose restart <service>` on the VM, then waiting for the board's next stored prediction | ✅ broker: predictions resumed 7.2 s after the restart (the board and the classifier both reconnected), database: 1.5 s (the classifier retried the failed write), classifier: 3.6 s. Board Wi-Fi loss: ⏳ (the firmware rejoins, and after 20 s tries its other known networks) |
| 6 | Tests pass; the ML report has every test protocol | GitHub Actions on `main`, plus local runs | ✅ API 19, classifier 36, ML 22, firmware host tests 19, Android 27 unit tests + lint, the Compose smoke test (CI and on the VM), and the firmware image build. The ML report covers unseen days, rotated devices, cross-wrist and board data (sections 4 and 10) |
| 7 | No secrets or handout in the repository | `git ls-files` and the whole history checked for `.env`, `secrets.h`, `passwd`, PDFs, keystores and `ml/data/`; the real passwords searched for in every tracked file | ✅ None found |

## Found and fixed during this check

- **Misleading message when the API is unreachable.** With no prediction loaded yet, the app said "No predictions for this device yet. Is the board on?", which blamed the board for a network problem. It now says "No connection". The card text moved to `activityCardText()`, which has unit tests.
- **Smoke test failing on the VM** (M7 deploy): `curl | grep -q` under `pipefail` failed once the web page outgrew one read. The script now fetches the whole response before matching it.

## Numbers from the VM

- 4 containers use about 400 MB of the VM's RAM (887 MB total, plus 2 GB swap).
- One prediction takes about 0.01 ms in ONNX Runtime; the API answers in 0.1–0.3 s from the Philippines to East Asia.
