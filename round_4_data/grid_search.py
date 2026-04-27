"""Grid search Phase 2 params for VEV_5400/5500 on R4 data."""
import subprocess, re, itertools, tempfile, os
from concurrent.futures import ProcessPoolExecutor, as_completed

TRADER = "/mnt/c/Users/rajg6/OneDrive/Desktop/IMC_P4/Round_4/trader.py"
BT = "/mnt/c/Users/rajg6/OneDrive/Desktop/IMC_P4/backtests/prosperity_rust_backtester/target/release/rust_backtester"
BT_DIR = "/mnt/c/Users/rajg6/OneDrive/Desktop/IMC_P4/backtests/prosperity_rust_backtester"
WORKERS = 10

PARAM_GRID = {
    "MARK01_EDGE_MULT":    [1.00],           # confirmed no impact
    "MARK01_ACTIVE_TICKS": [500],            # confirmed no impact
    "CLEAR_BAND_5400":     [5.0, 6.0, 7.0, 8.0, 10.0, 14.0],
    "CLEAR_BAND_5500":     [0.15, 0.5, 1.0, 2.0],
}

with open(TRADER) as f:
    BASE = f.read()


def patch_trader(edge_mult, active_ticks, cb_5400, cb_5500):
    src = BASE
    src = re.sub(r"MARK01_EDGE_MULT\s*=\s*[\d.]+", f"MARK01_EDGE_MULT = {edge_mult}", src)
    src = re.sub(r"MARK01_ACTIVE_TICKS\s*=\s*\d+", f"MARK01_ACTIVE_TICKS = {active_ticks}", src)
    cb = '{' + f'"VEV_5400": {cb_5400}, "VEV_5500": {cb_5500}' + '}'
    src = re.sub(r'CLEAR_BAND_BY_PRODUCT\s*:\s*dict\s*=\s*\{[^}]*\}', f'CLEAR_BAND_BY_PRODUCT: dict = {cb}', src)
    return src


def run_one(params):
    edge_mult, active_ticks, cb_5400, cb_5500 = (params["MARK01_EDGE_MULT"],
                                                   params["MARK01_ACTIVE_TICKS"],
                                                   params["CLEAR_BAND_5400"],
                                                   params["CLEAR_BAND_5500"])
    patched = patch_trader(edge_mult, active_ticks, cb_5400, cb_5500)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", dir="/tmp", delete=False) as tf:
        tf.write(patched)
        tmp = tf.name
    try:
        r = subprocess.run(
            [BT, "--trader", tmp, "--dataset", "round4", "--carry"],
            capture_output=True, text=True, cwd=BT_DIR, timeout=60
        )
        out = r.stdout + r.stderr
        pnl = float(m.group(1)) if (m := re.search(r"all\s+\d+\s+\d+\s+([\d.]+)", out)) else 0.0
        v54 = float(m.group(1)) if (m := re.search(r"VEV_5400\s+([\d.]+)", out)) else 0.0
        v55 = float(m.group(1)) if (m := re.search(r"VEV_5500\s+([\d.]+)", out)) else 0.0
    finally:
        os.unlink(tmp)
    return {**params, "pnl": pnl, "v54": v54, "v55": v55}


if __name__ == "__main__":
    keys = list(PARAM_GRID)
    all_params = [dict(zip(keys, v)) for v in itertools.product(*PARAM_GRID.values())]
    print(f"Running {len(all_params)} combinations with {WORKERS} workers...\n")

    results = []
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(run_one, p): p for p in all_params}
        for f in as_completed(futures):
            res = f.result()
            results.append(res)
            tag = f"cb54={res['CLEAR_BAND_5400']:5.2f} cb55={res['CLEAR_BAND_5500']}"
            print(f"{tag}  pnl={res['pnl']:>10.0f}  v54={res['v54']:>8.0f}  v55={res['v55']:>8.0f}")

    results.sort(key=lambda x: -x["pnl"])
    print("\n=== TOP 5 ===")
    for r in results[:5]:
        print(f"  pnl={r['pnl']:.0f}  v54={r['v54']:.0f}  v55={r['v55']:.0f}  "
              f"cb54={r['CLEAR_BAND_5400']} cb55={r['CLEAR_BAND_5500']}")

    print("\n=== BASELINE (em=1.0, at=any, cb54=0.15) ===")
    base = next((r for r in results if r["CLEAR_BAND_5400"] == 6.0 and r["CLEAR_BAND_5500"] == 0.15), None)
    if base:
        print(f"  pnl={base['pnl']:.0f}  v54={base['v54']:.0f}  v55={base['v55']:.0f}")
