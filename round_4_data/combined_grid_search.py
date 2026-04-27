"""Combined grid search: hydrogel second-pass + OU params + CLEAR_BAND_5500."""
import subprocess, re, itertools, tempfile, os
from concurrent.futures import ProcessPoolExecutor, as_completed

TRADER = "/mnt/c/Users/rajg6/OneDrive/Desktop/IMC_P4/Round_4/trader.py"
BT = "/mnt/c/Users/rajg6/OneDrive/Desktop/IMC_P4/backtests/prosperity_rust_backtester/target/release/rust_backtester"
BT_DIR = "/mnt/c/Users/rajg6/OneDrive/Desktop/IMC_P4/backtests/prosperity_rust_backtester"
WORKERS = 8

PARAM_GRID = {
    # Hydrogel second-pass (gap/block/dis already locked at 1.0/15/160)
    "HYDRO_TREND_WINDOW":  [25, 50, 100],
    "HYDRO_GAP_THRESHOLD": [1, 2, 3],
    # OU strategy (VEV_5000-5300)
    "OU_EMA_SPAN":         [500, 1000, 1250, 2000],
    "OU_ENTRY_DEV":        [10.0, 13.0, 17.423, 22.0],
    # VEV_5500 clear band
    "CLEAR_BAND_5500":     [0.15, 0.5, 1.0, 2.0],
}

with open(TRADER) as f:
    BASE = f.read()


def patch_trader(tw, gt, ou_span, ou_dev, cb55):
    src = BASE
    src = re.sub(r"HYDRO_TREND_WINDOW\s*=\s*\d+", f"HYDRO_TREND_WINDOW = {tw}", src)
    src = re.sub(r"HYDRO_GAP_THRESHOLD\s*=\s*\d+", f"HYDRO_GAP_THRESHOLD = {gt}", src)
    src = re.sub(r"OU_EMA_SPAN\s*=\s*\d+", f"OU_EMA_SPAN = {ou_span}", src)
    src = re.sub(r"OU_ENTRY_DEV\s*=\s*[\d.]+", f"OU_ENTRY_DEV = {ou_dev}", src)
    cb = '{' + f'"VEV_5400": 6.0, "VEV_5500": {cb55}' + '}'
    src = re.sub(r'CLEAR_BAND_BY_PRODUCT\s*:\s*dict\s*=\s*\{[^}]*\}', f'CLEAR_BAND_BY_PRODUCT: dict = {cb}', src)
    return src


def run_one(params):
    tw     = params["HYDRO_TREND_WINDOW"]
    gt     = params["HYDRO_GAP_THRESHOLD"]
    ou_span = params["OU_EMA_SPAN"]
    ou_dev = params["OU_ENTRY_DEV"]
    cb55   = params["CLEAR_BAND_5500"]
    patched = patch_trader(tw, gt, ou_span, ou_dev, cb55)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", dir="/tmp", delete=False) as tf:
        tf.write(patched)
        tmp = tf.name
    try:
        r = subprocess.run(
            [BT, "--trader", tmp, "--dataset", "round4", "--carry"],
            capture_output=True, text=True, cwd=BT_DIR, timeout=180
        )
        out = r.stdout + r.stderr
        pnl   = float(m.group(1)) if (m := re.search(r"all\s+\d+\s+\d+\s+([\d.]+)", out)) else 0.0
        hydro = float(m.group(1)) if (m := re.search(r"HYDROGEL_PACK\s+([\d.]+)", out)) else 0.0
        v55   = float(m.group(1)) if (m := re.search(r"VEV_5500\s+([\d.]+)", out)) else 0.0
        ou    = sum(float(m.group(1)) for prod in ["VEV_5000","VEV_5100","VEV_5200","VEV_5300"]
                    if (m := re.search(rf"{prod}\s+([\d.]+)", out)))
    except subprocess.TimeoutExpired:
        pnl, hydro, v55, ou = -1.0, -1.0, -1.0, -1.0
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return {**params, "pnl": pnl, "hydro": hydro, "v55": v55, "ou": ou}


if __name__ == "__main__":
    keys = list(PARAM_GRID)
    all_params = [dict(zip(keys, v)) for v in itertools.product(*PARAM_GRID.values())]
    print(f"Running {len(all_params)} combinations with {WORKERS} workers...\n")
    print(f"Baseline: pnl=585936  hydro=113971  v55=1900  ou=437448\n")

    results = []
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(run_one, p): p for p in all_params}
        for f in as_completed(futures):
            res = f.result()
            results.append(res)
            tag = (f"tw={res['HYDRO_TREND_WINDOW']:3d} gt={res['HYDRO_GAP_THRESHOLD']} "
                   f"span={res['OU_EMA_SPAN']:4d} dev={res['OU_ENTRY_DEV']:6.3f} cb55={res['CLEAR_BAND_5500']}")
            print(f"{tag}  pnl={res['pnl']:>10.0f}  hydro={res['hydro']:>8.0f}  ou={res['ou']:>8.0f}  v55={res['v55']:>6.0f}")

    results.sort(key=lambda x: -x["pnl"])
    print("\n=== TOP 10 ===")
    for r in results[:10]:
        print(f"  pnl={r['pnl']:.0f}  hydro={r['hydro']:.0f}  ou={r['ou']:.0f}  v55={r['v55']:.0f}  "
              f"tw={r['HYDRO_TREND_WINDOW']} gt={r['HYDRO_GAP_THRESHOLD']} "
              f"span={r['OU_EMA_SPAN']} dev={r['OU_ENTRY_DEV']} cb55={r['CLEAR_BAND_5500']}")

    # Baseline combo
    print("\n=== BASELINE (tw=50 gt=1 span=1250 dev=17.423 cb55=0.15) ===")
    base = next((r for r in results
                 if r["HYDRO_TREND_WINDOW"] == 50 and r["HYDRO_GAP_THRESHOLD"] == 1
                 and r["OU_EMA_SPAN"] == 1250 and r["OU_ENTRY_DEV"] == 17.423
                 and r["CLEAR_BAND_5500"] == 0.15), None)
    if base:
        print(f"  pnl={base['pnl']:.0f}  hydro={base['hydro']:.0f}  ou={base['ou']:.0f}  v55={base['v55']:.0f}")

    # Best per-area breakdown
    print("\n=== BEST PER AREA ===")
    best_hydro = max(results, key=lambda x: x["hydro"])
    best_ou    = max(results, key=lambda x: x["ou"])
    best_v55   = max(results, key=lambda x: x["v55"])
    print(f"  best hydro={best_hydro['hydro']:.0f}  tw={best_hydro['HYDRO_TREND_WINDOW']} gt={best_hydro['HYDRO_GAP_THRESHOLD']}")
    print(f"  best ou={best_ou['ou']:.0f}  span={best_ou['OU_EMA_SPAN']} dev={best_ou['OU_ENTRY_DEV']}")
    print(f"  best v55={best_v55['v55']:.0f}  cb55={best_v55['CLEAR_BAND_5500']}")
