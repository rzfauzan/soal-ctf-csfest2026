#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import time
import sys
import multiprocessing as mp # Tambahkan library multiprocessing
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pikaspx_common import ChallengeParams, derive_key, derive_public_root, xor_stream  # noqa: E402

PUBLIC_PATH = ROOT / "dist" / "output.txt"
AUTHOR_PATH = ROOT / "author" / "instance.json"


def load_public(path: Path) -> dict[str, object]:
    ns: dict[str, object] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        key, value = line.split("=", 1)
        ns[key.strip()] = ast.literal_eval(value.strip())
    return ns


def params_from_public(public: dict[str, object]) -> ChallengeParams:
    return ChallengeParams(
        code_bits=int(public["code_bits"]),
        pbkdf2_rounds=int(public["pbkdf2_rounds"]),
        tree_height=int(public["tree_height"]),
        salt=bytes.fromhex(public["salt"]),
    )


def benchmark_rate(params: ChallengeParams, samples: int) -> float:
    start = time.perf_counter()
    acc = 0
    for code in range(samples):
        acc ^= derive_public_root(code, params)[0]
    elapsed = time.perf_counter() - start
    if elapsed == 0:
        raise RuntimeError("benchmark timer resolution failure")
    print(f"benchmark_samples={samples} dummy={acc}")
    return samples / elapsed


def format_duration(seconds: float) -> str:
    minutes, sec = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {sec}s"
    return f"{minutes}m {sec}s"


# --- WORKER UNTUK MULTIPROCESSING ---
def brute_force_worker(start_code: int, end_code: int, target_root: bytes, params: ChallengeParams, 
                       progress_step: int, worker_id: int, stop_event: mp.Event, result_queue: mp.Queue):
    start = time.perf_counter()
    for code in range(start_code, end_code):
        # Jika core lain sudah menemukan hasilnya, hentikan loop ini
        if stop_event.is_set():
            return

        if worker_id == 0 and code > start_code and (code - start_code) % progress_step == 0:
            elapsed = time.perf_counter() - start
            rate = (code - start_code) / elapsed if elapsed else 0.0
            eta = (end_code - code) / rate if rate else 0.0
            print(f"[Core 0] progress={code - start_code}/{end_code - start_code} rate={rate:.1f} code/s eta={format_duration(eta)}")
            
        if derive_public_root(code, params) == target_root:
            result_queue.put(code) # Masukkan hasil ke antrean
            stop_event.set()       # Beri sinyal ke semua core untuk berhenti
            return


# --- FUNGSI BRUTE FORCE PARALEL ---
def brute_force_parallel(public: dict[str, object], params: ChallengeParams, progress_step: int) -> int:
    target_root = bytes.fromhex(public["root"])
    num_cores = mp.cpu_count()
    print(f"[*] Optimasi Multiprocessing: Menggunakan {num_cores} core CPU.")
    
    chunk_size = params.code_space // num_cores
    processes = []
    stop_event = mp.Event()
    result_queue = mp.Queue()
    
    for i in range(num_cores):
        start_code = i * chunk_size
        # Pastikan core terakhir memproses sisa modulus
        end_code = start_code + chunk_size if i < num_cores - 1 else params.code_space
        worker_progress_step = max(1, progress_step // num_cores)
        
        p = mp.Process(
            target=brute_force_worker, 
            args=(start_code, end_code, target_root, params, worker_progress_step, i, stop_event, result_queue)
        )
        processes.append(p)
        p.start()
        
    # Tunggu sampai ada hasil atau semua proses selesai
    found_code = None
    while any(p.is_alive() for p in processes):
        if not result_queue.empty():
            found_code = result_queue.get()
            break
        time.sleep(0.1)
        
    # Bersihkan jika ada sisanya
    if found_code is None and not result_queue.empty():
        found_code = result_queue.get()

    stop_event.set() # Pastikan semua thread ditutup
    for p in processes:
        p.join()
        
    if found_code is not None:
        return found_code
        
    raise RuntimeError("brute force exhausted the keyspace")


def decrypt_flag(public: dict[str, object], params: ChallengeParams, code: int) -> bytes:
    root = bytes.fromhex(public["root"])
    key = derive_key(code, params, root)
    return xor_stream(key, bytes.fromhex(public["nonce"]), bytes.fromhex(public["ct"]))


def load_author_code() -> int | None:
    if not AUTHOR_PATH.exists():
        return None
    data = json.loads(AUTHOR_PATH.read_text(encoding="utf-8"))
    return int(data["debug_code"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-only", action="store_true")
    parser.add_argument("--benchmark-samples", type=int, default=4096)
    parser.add_argument("--progress-step", type=int, default=1 << 16)
    args = parser.parse_args()

    public = load_public(PUBLIC_PATH)
    params = params_from_public(public)
    
    rate = benchmark_rate(params, args.benchmark_samples)
    num_cores = mp.cpu_count()
    est_total_rate = rate * num_cores * 0.95 # Asumsi efisiensi multi-core ~95%
    
    total_seconds = params.code_space / est_total_rate
    print(f"estimated_full_scan={format_duration(total_seconds)} at ~{est_total_rate:.1f} code/s (Multi-core)")
    
    author_code = load_author_code()
    if author_code is not None:
        estimated_hit = author_code / est_total_rate
        print(f"estimated_hit_time={format_duration(estimated_hit)} for code=0x{author_code:06x}")
        
    if args.benchmark_only:
        return

    code = brute_force_parallel(public, params, args.progress_step)
    flag = decrypt_flag(public, params, code)
    print(f"debug_code=0x{code:06x}")
    print(flag.decode())


if __name__ == "__main__":
    main()