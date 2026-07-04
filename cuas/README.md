# cuas — Phase-1 counter-UAS control software

Software backbone for the cheap stationary hard-kill C-UAS described in
`docs/superpowers/specs/2026-07-04-cheap-cuas-hardkill-design.md` and
`docs/superpowers/plans/2026-07-04-cheap-cuas-hardkill.md`.

Pipeline: **passive sensors → C2 fusion (2-of-N) → operator OK/ABORT → effector (auto-guided)**.

## Layout
```
common/      messages (Detection, Track) + MQTT bus
sim/         intercept feasibility model (25% speed margin + latency)
sensors/
  acoustic/  harmonic-comb drone detector + node daemon
  rf/        wideband drone-band detector + SDR node daemon
  eoir/      pixel->az/el + YOLO track publisher + PTZ slew-to-cue
c2/          fusion 2-of-N, effector selection, no-fire arcs,
             engagement state machine (OK/ABORT), FastAPI console, dispatch
effectors/
  e2_ram/    ultra-cheap auto-ram: vision lead-pursuit guidance + MAVLink offboard
  e1_net/    reusable net-drone: approach + range-gated net trigger + RTL
tests/       pytest suite (pure-logic, no hardware)
```

## Run the tests
```
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # (Windows)
python -m pytest cuas/tests/ -v
```
28 tests, all pure-logic — **no hardware, broker, or heavy models needed** to run them.
Heavy/hardware deps (sounddevice, pyrtlsdr, scipy, ultralytics, pymavlink) are
**lazy-imported inside the daemon `run()` functions**, so the algorithmic core is
importable and testable on any machine.

## What is tested vs hardware-gated
- **Unit-tested (green):** message schemas, intercept model, acoustic scorer,
  RF band detector, EO/IR pixel→az/el, fusion 2-of-N, effector selection,
  no-fire arcs, engagement OK/ABORT, guidance law, net-trigger gate, dispatch.
- **Hardware/field (see plan M3.2/M4.2/M5/M6):** live sensor ranges, PTZ slew
  accuracy, ArduPilot SITL + real flight, net capture + reuse, safety (no-fire,
  ABORT latency, fail-safe), cost-exchange verification. **Inert targets only —
  no warheads anywhere in this repo.**

## Run components (needs a broker + hardware)
```
mosquitto &                                  # MQTT broker
python -c "import cuas.c2.server as s; s.start()"   # wire bus; then: uvicorn cuas.c2.server:app
python -m cuas.sensors.acoustic.node --bearing 130
```
