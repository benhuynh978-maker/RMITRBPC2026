# Running the system in a cloud (Linux) session

Branch `cloud-session-2026-10-31`. Only source code is included: no `node_modules`, no build output, no keys/certs, no runtime data, no private photos.
The folders keep the same relative layout as on the original Windows machine (several scripts find the model with `../../runs/...`).

## Python (AI worker, trash-on-map webtest, model demo site)
    python3 -m venv .venv && . .venv/bin/activate
    pip install -r requirements-cloud.txt
Model weights are in `runs/segment/runs/train/baseline_v1_rev2/weights/best.pt` (YOLO26s-seg, classes Trash / Drain).

## Drain ROI + smoothed drain state demo (ssc-v2, ports 8010 / 5174)
    cd ssc-v2/ssc-road-alerts && npm ci
    npm run backend            # terminal 1, API on 127.0.0.1:8010 (no key: only localhost can write)
    npm run dev                # terminal 2, web on http://localhost:5174
    cd ssc-v2/inference && python -B ai_worker.py    # terminal 3, needs the .venv above
Tests: `npx vitest run` (126 tests).

## Trash-on-map webtest (port 8120)
    cd research/exp02_ve_rac_len_ban_do/webtest
    python -B -m uvicorn server:app --host 127.0.0.1 --port 8120
Tests: `python -B test_server.py` (175 checks).

## Model demo site (main copy: port 8100, v2 copy: port 8110)
    cd test-WebUI-modelAI/server && python -B -m uvicorn app:app --host 0.0.0.0 --port 8100
This one imports `analysis.py` from the top-level `inference/` folder.

## Websites
    cd cleansight-site && npm ci && npm run dev
    cd cleansight-site-v2 && npm ci && npm run dev

## Not included
Datasets (`datasets/`), training scripts/outputs, `last.pt`, user data and photos, TLS keys. The Windows-only `.ps1` helper scripts are included but are for the original PC.
