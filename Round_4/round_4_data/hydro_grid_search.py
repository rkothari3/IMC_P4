"""Grid search HYDROGEL params on R4 data."""
import subprocess, re, itertools, tempfile, os
from concurrent.futures import ProcessPoolExecutor, as_completed

TRADER = "/mnt/c/Users/rajg6/OneDrive/Desktop/IMC_P4/Round_4/trader.py"
BT = "/mnt/c/Users/rajg6/OneDrive/Desktop/IMC_P4/backtests/prosperity_rust_backtester/target/release/rust_backtester"
BT_DIR = "/mnt/c/Users/rajg6/OneDrive/Desktop/IMC_P4/backtests/prosperity_rust_backtester"
WORKERS = 8

PARAM_GRID = {
    "HYDRO_GAP_ALPHA_STRENGTH": [0.0, 1.0, 2.0, 3.0, 4.0],
    "HYDRO_CRASH_BLOCK":        [15.0, 25.0, 40.0, 999.0],   # applied to both CRASH_BLOCK_LONGS and RIP_BLOCK_SHORTS
    "HYDRO_DISABLE_POS":        [160, 170, 180, 190, 200],    # applied to DISABLE_BID_ABOVE_POS; negative for ASK
}

with open(TRADER) as f:
    BASE = f.read()


def patch_trader(gap_str, crash_block, disable_pos):
    src = BASE
    src = re.sub(r"HYDRO_GAP_ALPHA_STRENGTH\s*=\s*[\d.]+", f"HYDRO_GAP_ALPHA_STRENGTH = {gap_str}", src)
    src = re.sub(r"HYDRO_CRASH_BLOCK_LONGS\s*=\s*[\d.]+", f"HYDRO_CRASH_BLOCK_LONGS = {crash_block}", src)
    src = re.sub(r"HYDRO_RIP_BLOCK_SHORTS\s*=\s*[\d.]+", f"HYDRO_RIP_BLOCK_SHORTS = {crash_block}", src)
    src = re.sub(r"HYDRO_DISABLE_BID_ABOVE_POS\s*=\s*\d+", f"HYDRO_DISABLE_BID_ABOVE_POS = {disable_pos}", src)
    src = re.sub(r"HYDRO_DISABLE_ASK_BELOW_POS\s*=\s*-\d+", f"HYDRO_DISABLE_ASK_BELOW_POS = -{disable_pos}", src)
    return src


def run_one(params):
    gap_str = params["HYDRO_GAP_ALPHA_STRENGTH"]
    crash_block = params["HYDRO_CRASH_BLOCK"]
    disable_pos = params["HYDRO_DISABLE_POS"]
    patched = patch_trader(gap_str, crash_block, disable_pos)
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
    except subprocess.TimeoutExpired:
        pnl, hydro = -1.0, -1.0
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return {**params, "pnl": pnl, "hydro": hydro}


if __name__ == "__main__":
    keys = list(PARAM_GRID)
    all_params = [dict(zip(keys, v)) for v in itertools.product(*PARAM_GRID.values())]
    print(f"Running {len(all_params)} combinations with {WORKERS} workers...\n")
    print(f"Baseline: pnl=574350  hydro=102385\n")

    results = []
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(run_one, p): p for p in all_params}
        for f in as_completed(futures):
            res = f.result()
            results.append(res)
            tag = (f"gap={res['HYDRO_GAP_ALPHA_STRENGTH']:4.1f} "
                   f"block={res['HYDRO_CRASH_BLOCK']:5.1f} "
                   f"dis={res['HYDRO_DISABLE_POS']}")
            print(f"{tag}  pnl={res['pnl']:>10.0f}  hydro={res['hydro']:>8.0f}")

    results.sort(key=lambda x: -x["pnl"])
    print("\n=== TOP 10 ===")
    for r in results[:10]:
        print(f"  pnl={r['pnl']:.0f}  hydro={r['hydro']:.0f}  "
              f"gap={r['HYDRO_GAP_ALPHA_STRENGTH']} block={r['HYDRO_CRASH_BLOCK']} dis={r['HYDRO_DISABLE_POS']}")

    print("\n=== BASELINE (gap=2.0 block=25.0 dis=180) ===")
    base = next((r for r in results
                 if r["HYDRO_GAP_ALPHA_STRENGTH"] == 2.0
                 and r["HYDRO_CRASH_BLOCK"] == 25.0
                 and r["HYDRO_DISABLE_POS"] == 180), None)
    if base:
        print(f"  pnl={base['pnl']:.0f}  hydro={base['hydro']:.0f}")
