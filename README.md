# RT-Spark Activity Recognition

[![Repo checks](https://github.com/TristanListanco/rt-spark-activity-recognition/actions/workflows/repo.yml/badge.svg)](https://github.com/TristanListanco/rt-spark-activity-recognition/actions/workflows/repo.yml)
[![Cloud](https://github.com/TristanListanco/rt-spark-activity-recognition/actions/workflows/cloud.yml/badge.svg)](https://github.com/TristanListanco/rt-spark-activity-recognition/actions/workflows/cloud.yml)
[![ML](https://github.com/TristanListanco/rt-spark-activity-recognition/actions/workflows/ml.yml/badge.svg)](https://github.com/TristanListanco/rt-spark-activity-recognition/actions/workflows/ml.yml)
[![Firmware](https://github.com/TristanListanco/rt-spark-activity-recognition/actions/workflows/firmware.yml/badge.svg)](https://github.com/TristanListanco/rt-spark-activity-recognition/actions/workflows/firmware.yml)
[![Android](https://github.com/TristanListanco/rt-spark-activity-recognition/actions/workflows/android.yml/badge.svg)](https://github.com/TristanListanco/rt-spark-activity-recognition/actions/workflows/android.yml)

Laboratory Activity 3: a full-stack IoT system that classifies walking vs. running in real time.

The RT-Spark board streams accelerometer and gyroscope readings over Wi-Fi/MQTT to a cloud service. There, a small 1D-CNN classifies the activity and the result is stored in PostgreSQL. A Flask API serves the results to an Android app.

## Architecture

```mermaid
flowchart LR
  subgraph Device["RT-Spark (STM32F407)"]
    IMU["6-axis IMU"] --> FW["RT-Thread firmware"]
    FW --> WIFI["RW007 Wi-Fi"]
  end
  subgraph Cloud["Cloud VM (Docker Compose)"]
    MQ["Mosquitto broker"] --> CL["Classifier (ONNX 1D-CNN)"]
    CL --> DB[("PostgreSQL")]
    DB --> API["Flask Web API"]
  end
  WIFI -- "MQTT: activity/rtspark-01/imu" --> MQ
  API -- "HTTP/JSON" --> APP["Android app (Kotlin + Volley)"]
```

Message formats, API endpoints and the database schema are in [docs/CONTRACTS.md](docs/CONTRACTS.md).

## Repository layout

| Path | Contents |
|---|---|
| `firmware/` | RT-Thread project for the RT-Spark: IMU sampling, Wi-Fi, MQTT publishing |
| `cloud/` | Docker Compose stack: Mosquitto, PostgreSQL, classifier service, Flask API |
| `ml/` | Dataset exploration, preprocessing, training, exported ONNX model |
| `tools/` | `fake_publisher.py` (simulates the board), `record.py` (records labelled board data) |
| `app/` | Android app: live prediction and history |
| `docs/` | Interface contracts, ML report |

## Progress

- [x] M0: Repository set up
- [x] M1: Local cloud stack (broker, DB, API stub, fake publisher)
- [x] M1b: Firmware toolchain builds and flashes the stock BSP
- [x] M2: ML model trained and exported
- [x] M3: Classifier + API working end to end with simulated data
- [x] M4: Firmware publishes real IMU data over Wi-Fi/MQTT
- [x] M5: Android app
- [ ] M6: Deployed to an Azure VM
- [ ] M7: Own data collected, model fine-tuned
- [ ] M8: Final test, demo video

## Running it

*Filled in as each part is built.*

### Cloud stack (local)

Needs Docker. Four services run from `cloud/docker-compose.yml`:

| Service | Port | Role |
|---|---|---|
| `mosquitto` | 1883 | MQTT broker; password auth only, credentials from `cloud/.env` |
| `db` | internal | PostgreSQL 16; schema in `cloud/db/init.sql` |
| `classifier` | — | Subscribes to `activity/+/imu` and validates each message against the contract. Keeps a 2 s window per device, classifies it once per second with `ml/models/model.onnx` (ONNX Runtime; no PyTorch in the image), and writes the result to `predictions` |
| `api` | 8000 | Flask API over the `predictions` table (contract section 4), plus a live web page at `/` |

```bash
cp cloud/.env.example cloud/.env        # then set real passwords
docker compose -f cloud/docker-compose.yml up -d --build --wait

curl http://localhost:8000/api/health
open http://localhost:8000/             # live page
```

Simulate the board with `tools/fake_publisher.py`, which reads the MQTT credentials from `cloud/.env`. Its default signals are simple but physically plausible, so the model labels them correctly. Add `--csv ml/data/dataset.csv` to replay real dataset rows instead.

```bash
python3 -m venv .venv && .venv/bin/pip install -r tools/requirements.txt
.venv/bin/python tools/fake_publisher.py                   # alternate walk/run every 30 s
.venv/bin/python tools/fake_publisher.py --activity run --count 10

curl "http://localhost:8000/api/latest?device_id=rtspark-01"
mosquitto_sub -h localhost -u device -P <MQTT_PASSWORD> -t 'activity/#' -v   # raw traffic
docker compose -f cloud/docker-compose.yml logs -f classifier                # one line per prediction
```

`cloud/scripts/smoke_test.sh` checks the whole path end to end, and CI runs the same script:
1. Start the stack and check the API and database are healthy.
2. Check the broker rejects anonymous clients.
3. Simulate a board that walks for 6 s and then runs for 6 s.
4. Expect 11 stored predictions, a latest label of "run", both activities in the history, a matching daily summary, the web page loading, and a clean classifier log.

Replaying real dataset rows through the running stack, the label switched to "run" about 1 s after the data switched.

Port 8000 is used instead of 5000 because macOS reserves 5000 for AirPlay Receiver.

### Machine learning

`ml/` is a [uv](https://docs.astral.sh/uv/) project (Python 3.12). On Linux it installs the CPU-only PyTorch build. Put the Kaggle run-or-walk CSV at `ml/data/dataset.csv` (it is not committed), then:

```bash
cd ml
uv sync
uv run python explore.py    # dataset facts + figures (docs/ml/)
uv run python evaluate.py   # compare models on unseen days, rotated devices, other wrist (~13 min)
uv run python train.py      # train the deployed model → models/model.onnx + model_meta.json
uv run pytest
```

The exported model takes raw 2 s windows `(batch, 10, 6)` in g and rad/s and returns `[walk, run]` probabilities. Magnitude channels and normalization happen inside the ONNX file, so the classifier service needs only numpy and ONNX Runtime.

### Firmware

RT-Thread on the RT-Spark, using RT-Thread's official `stm32f407-rt-spark` board package with its RW007 Wi-Fi and ICM-20608 IMU drivers. The firmware samples at 5 Hz and publishes one MQTT message per second. Its LCD shows the cloud's prediction (sent back over MQTT) and the board's status. Details, LED meanings and serial commands: [firmware/README.md](firmware/README.md).

The only prerequisite is the Arm GCC toolchain (GCC 14.2, native on Apple Silicon, no admin rights):

```bash
pio pkg install --global --tool "platformio/toolchain-gccarmnoneeabi@1.140201.0"
```

`firmware/build.sh` does the rest: it fetches RT-Thread at a pinned commit (only the parts this board needs), installs RT-Thread Env if missing, copies this project's code and configuration onto the board package, and builds. It flashes through the on-board ST-Link with PlatformIO's OpenOCD.

```bash
cp firmware/applications/secrets.example.h firmware/applications/secrets.h   # Wi-Fi + MQTT settings
firmware/build.sh flash
pio device monitor -p /dev/cu.usbmodem* -b 115200
```

On macOS, the first time the board is plugged in you have to click **Allow** on the "Allow accessory to connect?" prompt. The board needs a **2.4 GHz, IPv4** Wi-Fi network; a phone hotspot works.

### Android app

A native Android app (Kotlin, Jetpack Compose, Material 3) that polls the API with **Volley**, as the lab recommends. Minimum Android 8.0 (API 26).

| Live | History | API unreachable (dark mode) |
|---|---|---|
| <img src="docs/app/live.png" width="240" alt="Live tab: a large orange card reading Running, 100% confident, updated just now, above today's walking and running totals"> | <img src="docs/app/history.png" width="240" alt="History tab: alternating Walking and Running stretches with time ranges, durations and average confidence"> | <img src="docs/app/offline-dark.png" width="240" alt="Live tab in dark mode with a red banner: Can't reach the server, while still showing the last prediction"> |

- **Live:** the current activity in a large card (blue for walking, orange for running, grey when no data has arrived for 10 s), its confidence and age, and today's walking/running time with a proportional bar. It polls `/api/latest` every second while visible and stops when the app is in the background.
- **History:** the API's one-prediction-per-second records merged into stretches ("Running · 20:50:41 – 20:51:01 · 21 s · 99%"). Pull to refresh; older pages load as you scroll (`before=` paging).
- **Settings:** API address and device ID, saved on the phone, with **Test connection** (`/api/health`). The default is `http://10.0.2.2:8000` on the emulator (the computer running it) and `http://172.20.10.2:8000` on a real phone on the iPhone hotspot. On another network, enter the Mac's address there (e.g. `http://192.168.1.44:8000` at home).

```bash
cd app
./gradlew installDebug          # build and install on a connected phone or a running emulator
./gradlew testDebugUnitTest     # 22 unit tests: JSON parsing, history stretches, formatting, Live ViewModel
./gradlew lintDebug
```

Or open `app/` in Android Studio. Gradle needs JDK 17 or newer (Android Studio's bundled JDK works: `export JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"`). Missing SDK parts (platform 37, build-tools 36) are installed automatically on the first build.

Structure: `data/` holds the Volley client wrapped in coroutines, JSON parsing, the repository (behind an interface, so ViewModels are tested with a fake) and the DataStore settings. `ui/live`, `ui/history` and `ui/settings` each have a ViewModel exposing a `StateFlow`, and `ui/theme` holds the project palette. Notes:
- `targetSdk` stays at 36: targeting Android 17 may opt in to its local-network restrictions, and this app talks to a server on the local network.
- Plain HTTP is allowed (`network_security_config.xml`) because the API address is set at runtime.

## Continuous integration

Each part has its own GitHub Actions workflow in `.github/workflows/`. A workflow runs only when its folder changes, and its jobs skip until that part of the project exists.

| Workflow | Runs when | What it does |
|---|---|---|
| `repo.yml` | every push/PR | Fails if `.env`, `secrets.h`, keystores or the lab handout are committed, or if any file is over 10 MB. Lints the workflows (actionlint) and all Python (ruff, config in `ruff.toml`) |
| `cloud.yml` | `cloud/`, `tools/`, `ml/activity_ml/`, `ml/models/` | `pytest` for the API and classifier against a Postgres service (`DATABASE_URL`). Builds the Compose stack and runs `cloud/scripts/smoke_test.sh` |
| `ml.yml` | `ml/` | `uv sync --locked`, then `pytest` (preprocessing and exported-model checks; no training in CI) |
| `firmware.yml` | `firmware/`, `cloud/classifier/payload.py` | Compiles the firmware's message code on the host and checks its JSON with the cloud classifier's validator. Then `firmware/build.sh` builds the image (pinned RT-Thread, cached between runs) with placeholder secrets, reports flash/RAM size, and uploads `rtthread.bin` |
| `android.yml` | `app/` | Validates the Gradle wrapper, then `lintDebug testDebugUnitTest assembleDebug`. Uploads the debug APK |

## Results

Full details in [docs/ml-report.md](docs/ml-report.md). The deployed model is a 1D-CNN with 1,218 parameters (30 KB ONNX, ≈0.01 ms per prediction), trained with left/right mirroring and random 3D rotations:

| Test | Accuracy |
|---|---|
| Unseen recording day (12-fold) | 99.71% |
| Unseen day, device rotated to a random orientation | 99.70% |
| Train left wrist → test right / train right → test left | 99.62% / 98.82% |

The same CNN trained without rotations also scores 99.9% on unseen days, but drops to 52% once the device is rotated. It learned *how the iPhone was worn* instead of how walking and running move. That is why rotation training matters for the RT-Spark. Results on data recorded with the board are added in M7.

## Demo

_Link to the demo video._
