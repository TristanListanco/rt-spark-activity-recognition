# ML report: walk/run/idle classifier

How the model behind the activity predictions was built, tested and chosen. Every number here comes from `ml/results/dataset_facts.json`, `ml/results/evaluation.json` and `ml/results/own_evaluation.json`, which `ml/explore.py`, `ml/evaluate.py` and `ml/evaluate_own.py` regenerate.

Sections 1–9 are the M2 work on the Kaggle data (two classes, walk and run). Section 10 tests those models on data recorded with the RT-Spark and adds a third class, idle; the deployed model is now that 3-class model.

## Summary

- **Data:** the Kaggle run-or-walk dataset: 88,588 samples from one person wearing an iPhone on the wrist, recorded on 12 days.
- **Units and rate, settled from the data:** 5 Hz; acceleration in g *with gravity included*; angular rate in rad/s. These are now fixed in [CONTRACTS.md](CONTRACTS.md), and the firmware must send the same.
- **M2 model:** a 1D-CNN over 2 s windows (10 samples), trained with left/right mirroring and random 3D rotations.
  - 1,218 parameters, a 30 KB ONNX file, about 0.01 ms per prediction on a laptop CPU.
  - **99.71%** accuracy on unseen recording days, and **99.70%** when the unseen day's data is also rotated to simulate a differently mounted device.
- **On the RT-Spark (M7, section 10):** that model scores **99.6%** on walking and running recorded with the board. The model trained without rotations scores 53%, which confirms the main lesson below.
- **Deployed model (M7):** the same CNN with a third class, **idle**, over 4 s windows (20 samples), trained on the Kaggle data plus about 8 minutes of board recordings. **97.2%** on held-out stretches of the board recordings (idle 97.5%, walk 94.5%, run 100%), still 99.7% on unseen Kaggle days.
- **The main lesson:** every model trained *without* rotations reaches 99.9% on the dataset but drops to **~52–58%**, coin-flip level, once the device orientation changes. The RT-Spark will not be worn exactly like the iPhone, so rotation training is what makes the model usable on the board.
- **Honest caveat:** a simpler model that ignores time order (logistic regression on window statistics), when also trained with rotations, is slightly *more* accurate on this dataset (99.88% vs 99.70%). Section 5 explains why the CNN was deployed anyway. On the board data the CNN is clearly better (99.6% vs 90.4%, section 10).

## 1. Dataset

| Fact | Value |
|---|---|
| Samples | 88,588 (44,223 walk, 44,365 run) |
| People | 1 (`viktor`) |
| Recording days | 12 |
| Sessions | 339, median 54 samples (≈ 11 s) |
| Wrist | 42,330 left, 46,258 right; most days use one wrist |
| Sample interval | median 0.2000 s → **5 Hz** |
| Acceleration range | −5.35 … 5.60 g |
| Angular rate range | −9.48 … 11.27 rad/s |

**Time format.** The `time` column looks like `13:51:15:847724020`. Read as hours:minutes:seconds:**nanoseconds**, consecutive samples are 0.2000 s apart (10th–90th percentile 0.199–0.201 s). Read as a decimal fraction, the gaps make no sense (thousands of negative steps). A few rows are out of order, so the loader sorts by time. It then splits the data into sessions on gaps over 1 s or a change of activity or wrist.

**Units and gravity.** The mean acceleration magnitude while walking is **1.08 g** (median 1.06). That is what an accelerometer reads with gravity included. Phone "user acceleration", which has gravity removed, would average near 0; m/s² would average near 9.8. Angular rate magnitudes average 1.9 (walk) and 2.7 (run) with a maximum of 11, which fits rad/s; deg/s would be about 57 times larger. The ICM-20608 on the board also measures gravity, so the firmware only has to convert raw counts to g and rad/s.

**Posture.** While walking, gravity sits almost entirely on the −y axis (mean −0.98 g): the arm hangs down. While running it mostly leaves −y (mean −0.14 g) and moves towards −z (−0.41 g): the arm is bent. That is a very strong clue, but it depends entirely on how the device sits on the arm.

![Mean acceleration per axis, walking vs running](ml/posture.png)

Over time, running shows a regular arm swing of about 1.1 s on the y-axis, and larger, faster rotations:

![10 s of walking vs running](ml/signals.png)

**Wrist.** The mean x-acceleration flips sign between the left wrist (+0.57 g) and the right (−0.66 g), as expected for mirror-image placements.

## 2. Method

**Windows.** Each session is cut into overlapping windows of W samples, which never cross a session boundary. At W = 10 that gives 85,567 windows from 335 sessions (4 sessions shorter than 10 samples are dropped). Training uses every second window, which is just as effective as using all of them in half the time. Testing uses all windows.

**Model.** The model takes raw windows of shape (W, 6) and does everything else inside the network:
1. It adds two channels, |acceleration| and |angular rate|, which don't depend on orientation.
2. It standardizes all 8 channels with statistics from the training set.
3. Two 1D convolutions (16 filters, kernel 3, ReLU) slide over time. Together they see 5 consecutive samples (1 s), so they learn the *shape* of the motion over time.
4. Global average pooling and a linear layer produce 2 outputs, then softmax.

That is 1,218 parameters. Because the feature steps are inside the exported ONNX file, the live classifier feeds it exactly what the board sends, and training and serving cannot disagree.

**Augmentation.** Each training batch is changed randomly so the model can't rely on how the iPhone happened to be worn:
- **Mirroring** reflects half the windows across the body's mid-plane (left ↔ right wrist): acceleration becomes (−ax, ay, az). Angular rate is an *axial* vector, so under a reflection it becomes (gx, −gy, −gz), not just a flipped x.
- **Rotation** additionally turns acceleration and angular rate by the same uniformly random 3D rotation, so no fixed orientation can be memorized.

**Baseline.** For comparison, a model that ignores time order: the mean, standard deviation, minimum and maximum of the 8 channels in each window (32 numbers), fed to logistic regression. Swapping samples within a window doesn't change its input at all.

**Training.** Adam, learning rate 5×10⁻³ with cosine decay, batch size 512, 8 epochs, seed 0. Evaluation and the final model use exactly the same settings.

## 3. How the models were tested

A random train/test split would be meaningless here. Neighbouring windows share 9 of their 10 samples, so the test set would contain near-copies of training windows. Every protocol below keeps the test data completely separate:

| Protocol | Trains on | Tests on | What it asks |
|---|---|---|---|
| **Unseen day** | 11 of the 12 days (12 rounds) | the held-out day | Does it generalize to a new recording session? |
| **Rotated device** | 11 of the 12 days | the held-out day, with all its data turned by one fixed random rotation | Does it still work when the device sits differently on the arm? This is the situation on the RT-Spark |
| **Left → right wrist** | left-wrist data only | right-wrist data | Does it transfer to the other arm? |
| **Right → left wrist** | right-wrist data only | left-wrist data | The same, in reverse |

All results pool the predictions from every round. For the models that work, macro-F1 is within 0.1 points of accuracy, because the classes are balanced. For the models that collapse on rotated devices it is much lower (e.g. 0.39 for the plain 1D-CNN), because they predict almost only one class. The full numbers, including confusion matrices and per-day accuracy, are in `ml/results/evaluation.json`.

## 4. Results

**2 s windows (W = 10)**

| Model | Unseen day | Rotated device | Left → right wrist | Right → left wrist |
|---|---|---|---|---|
| Baseline: window statistics + logistic regression | 99.97% | 57.44% | 99.94% | 99.88% |
| Baseline, trained with rotations | 99.86% | 99.88% | 99.89% | 99.87% |
| 1D-CNN | 99.95% | 52.29% | 99.46% | 81.22% |
| 1D-CNN + wrist mirroring | 99.95% | 52.45% | 99.94% | 99.73% |
| **1D-CNN + mirroring + rotations (deployed)** | 99.71% | 99.70% | 99.62% | 98.82% |

**4 s windows (W = 20)**

| Model | Unseen day | Rotated device | Left → right wrist | Right → left wrist |
|---|---|---|---|---|
| Baseline: window statistics + logistic regression | 100.00% | 58.02% | 98.26% | 99.97% |
| Baseline, trained with rotations | 99.98% | 99.99% | 99.98% | 99.94% |
| 1D-CNN | 99.99% | 50.31% | 71.29% | 91.39% |
| 1D-CNN + wrist mirroring | 99.98% | 50.90% | 99.98% | 99.93% |
| 1D-CNN + mirroring + rotations | 99.82% | 99.85% | 99.67% | 99.38% |

What the numbers show:
1. **The dataset alone is easy.** On unseen days every model scores ≥ 99.7%. Holding out a day is not a hard enough test on its own.
2. **Without augmentation the CNN memorizes posture.** It drops to 81% (2 s) or 71% (4 s) on the other wrist. Mirroring fixes that.
3. **Only rotation training survives a turned device.** Every model trained without rotations collapses to 50–58%: it calls almost everything "run", because "gravity is not on −y" is what it learned running looks like. With rotation training both model types stay above 99.7%.
4. **Longer windows help slightly** (the rotation-trained CNN goes from 99.70% to 99.85% on rotated devices), but make the prediction react more slowly.

For the deployed model, the unseen-day confusion matrix (all 12 rounds pooled) is:

| | predicted walk | predicted run |
|---|---|---|
| **walk** | 42,987 | 120 |
| **run** | 126 | 42,334 |

Its worst single day scores 99.0%, both normally and rotated.

## 5. Choosing the deployed model

**Rotation training is required.** The board's sensor axes will not line up with the iPhone's, so a model that relies on orientation would most likely fail on real board data, however good its dataset scores.

**Two rotation-trained candidates remain.** The CNN makes 255 errors on the 85,567 rotated-device windows; the statistics baseline makes 104. The baseline is slightly better on this dataset. The CNN is deployed anyway, for these reasons:
- **The lab asks for a model that uses temporal information,** built with TensorFlow or PyTorch. The CNN learns motion patterns over time; the baseline throws time order away by construction.
- **The gap is small** (99.70% vs 99.88%), and this dataset has one person and one device. Which model transfers better to a different person and board is still an open question.
- **M7 will settle it with real data.** I'll record walking and running with the RT-Spark and re-test both models. If the baseline is clearly better on board data, it can be exported the same way (logistic regression is a single linear layer).

**2 s windows (W = 10) instead of 4 s.** The label reacts about 2 s faster when you change pace, for a 0.15-point accuracy cost. (M7 revisits this: with an idle class, 4 s windows are clearly better; see section 10.)

## 6. The lab's design questions

- **Temporal information.** The CNN's convolutions run along time and learn the shape of a 1 s stretch of motion. The baseline shows that on this dataset an order-free model is competitive, because walking and running also differ in overall intensity: mean angular rate is 1.9 vs 2.7 rad/s. I report that rather than hide it.
- **Sophisticated vs lightweight.** Lightweight. The model has 1,218 parameters, the whole training set fits in memory, and one training run takes about 10 s on a laptop CPU. A larger model has nothing left to gain here: the remaining errors come from orientation and transfer, not from capacity.
- **Compute vs memory.** Neither is a constraint at this size. The model file is 30 KB and one prediction takes about 0.01 ms, so the 1 GB Azure VM runs it easily with ONNX Runtime alone (no PyTorch needed).
- **Probabilistic output.** Yes: the softmax output is reported as the prediction's confidence and shown in the app. These probabilities are not calibrated, so read 0.95 as "confident", not as an exact 95% chance.

## 7. Deployed model

The M2 model was a 2-class version of this (30,634 bytes, input (batch, 10, 6)). Since M7 it is:

| | |
|---|---|
| File | `ml/models/model.onnx` (30,702 bytes), described by `ml/models/model_meta.json` |
| Input `imu` | float32 (batch, 20, 6): raw `[ax, ay, az, gx, gy, gz]` in g and rad/s, 5 Hz, oldest sample first |
| Output `probs` | float32 (batch, 3): probabilities for `[walk, run, idle]` |
| Parameters | 1,235 |
| Check | ONNX Runtime output matches PyTorch to within 9×10⁻⁷ |
| Speed | ≈ 0.01 ms per window (ONNX Runtime, CPU) |

## 8. Limitations

- **One person and one phone.** Results across days and wrists can't show how the model handles other people or other sensors. The board recordings in M7 are the real test (section 10), but they are one more person, one session per activity.
- **5 Hz sampling** captures movement up to 2.5 Hz. Arm swing (about 1 Hz) is well covered; finer detail of each footstep is not.
- **Idle comes from one recording.** The M2 model had no idle class, so standing still was labelled run or walk (section 10). The idle class added in M7 is learned from a single 3-minute session of standing still with the board on the wrist, so other still postures (sitting, lying down, the board on a table) may look different to it.

## 9. Reproduce

```bash
cd ml
uv sync                                  # Python 3.12 environment from uv.lock
# put the Kaggle CSV at ml/data/dataset.csv (not committed)
uv run python explore.py                 # dataset facts + figures
uv run python evaluate.py                # all protocols, about 13 min on a laptop CPU
# record board data with tools/record.py into ml/data/own/ (not committed)
uv run python evaluate_own.py            # section 10, about 4 min; run before train.py
uv run python train.py                   # final 3-class model → models/model.onnx
uv run python train.py --own none --window 10   # the 2-class M2 model instead
uv run pytest                            # preprocessing, model and exported-file tests
```

## 10. Results on board data (M7)

### Recording

I wore the RT-Spark strapped to my wrist, screen facing outward, in one fixed position, and labelled the stream with the board's buttons (LEFT walk, RIGHT run, UP idle, DOWN stop; `firmware/applications/label.c`). `tools/record.py` saved the labelled samples. One session per activity, on 2026-10-31:

| Activity | Duration | Instruction |
|---|---|---|
| idle | 201 s | stand still |
| walk | 142 s | walk at a normal pace |
| run | 121 s | run or jog |

That is 2,320 samples at 5 Hz. The first and last 2 s of each session are dropped, because around a button press I was still starting or stopping. This leaves 2,233 windows of 10 samples (2,203 of 20).

### Kaggle-trained models on the board

Each model type from section 4 is trained on all of the Kaggle data and tested on the board recordings. These models only know walk and run, so for idle the table shows what they predict instead.

| Model (trained on Kaggle only) | Walk/run accuracy | Walk recall | Run recall | Idle predicted as |
|---|---|---|---|---|
| Statistics baseline | 54.0% | 15.1% | 100% | run 100% |
| Statistics baseline, rotations | 90.4% | 82.2% | 100% | walk 97% |
| CNN | 52.8% | 12.9% | 100% | run 100% |
| CNN, mirror | 53.0% | 13.2% | 100% | run 100% |
| **CNN, rotations (the M2 model)** | **99.6%** | **99.3%** | **100%** | run 72%, walk 28% |

- **Rotation training is what makes the model work on the board.** Without it, every model calls nearly everything "run". This is the failure section 4 predicted with simulated rotations, now seen on real data.
- **This settles the question left open in section 5.** On the Kaggle data the statistics baseline was slightly better; on the board, the temporal CNN is clearly better (99.6% vs 90.4%). It is the model that transfers to a new person and device.
- **Standing still needs its own class.** The M2 model labels 72% of idle windows "run". On the LCD and in the app, standing still showed as "Running".

### Adding the idle class

The CNN now has three outputs, `[walk, run, idle]`. It is trained on the Kaggle walk/run windows plus the board windows, with the same mirror-and-rotate augmentation. The board data is a few minutes against hours of Kaggle data, so each board window is repeated 10 times (each copy gets a different random rotation). I also tried weighting the loss by inverse class frequency ("balanced"), since idle is the rarest class.

**How it is tested.** With one session per activity, the board data can't be split by session. Instead each session is cut into 4 consecutive time blocks, and each block is predicted by a model trained without it. Training windows within 2 s (W = 10) or 4 s (W = 20) of a test block are also left out, so no training window shares samples with a test window. Each fold also holds out 3 of the 12 Kaggle days, to check that walk/run on the Kaggle data doesn't get worse.

| Variant | Board accuracy | Walk | Run | Idle | Unseen Kaggle days | Kaggle windows called idle |
|---|---|---|---|---|---|---|
| W = 10, repeat 10, balanced | 94.1% | 89.3% | 100% | 94.1% | 99.39% | 0.04% |
| W = 10, repeat 10 | 94.6% | 94.1% | 100% | 91.8% | 99.39% | 0.04% |
| W = 10, repeat 5 | 93.0% | 89.3% | 100% | 91.4% | 99.30% | 0.05% |
| **W = 20, repeat 10, balanced** | **97.2%** | 94.5% | 100% | **97.5%** | 99.70% | 0.02% |
| W = 20, repeat 10 | 96.1% | 95.8% | 100% | 93.9% | 99.85% | 0.02% |

Confusion matrix of the chosen variant on the board data (rows = truth):

| | → walk | → run | → idle |
|---|---|---|---|
| **walk** | 634 | 0 | 37 |
| **run** | 0 | 566 | 0 |
| **idle** | 24 | 0 | 942 |

- **Every error is walk ↔ idle.** Running is never confused with anything. Walking and standing are the two low-motion activities, so a stretch of walking with little arm swing, or fidgeting while standing, is the likely cause (not checked window by window).
- **4 s windows (W = 20) are now worth their delay.** With two classes, W = 20 gained only 0.15 points (section 5). With idle, a 2 s window often can't tell a pause in arm swing from standing still: 4 s windows raise board accuracy from 94.1% to 97.2%. The cost is that the label reacts about 2 s later.
- **The Kaggle data is not hurt:** 99.7% on unseen Kaggle days, and only 0.02% of Kaggle walk/run windows are called idle.

**Deployed:** W = 20, repeat 10, balanced, trained on all Kaggle data and all board recordings (`ml/train.py`). As a sanity check, 200 simulated windows of a motionless board (gravity in a random direction plus sensor-sized noise) are all classified idle.

### Caveats

- **The numbers are optimistic.** The variant was picked using the same folds that score it, and the test blocks come from the same three sessions (same day, same strap position) as the training blocks. A new session on another day is likely to score lower.
- **One wearer, one session per activity.** Recording more sessions, ideally on different days, would allow a proper leave-one-session-out test.
- **The deployed model saw all the board data,** so it has no held-out board test of its own. The end-to-end check with the board on the wrist (M7/M8) is its real test.

