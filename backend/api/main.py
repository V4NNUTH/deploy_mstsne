"""
Ms t-SNE Explorer — FastAPI Backend
Mirrors the 21-section notebook flow with WebSocket live log streaming.
Temp files auto-cleaned after TTL (default 2h).
"""
import os, sys, json, time, uuid, asyncio, shutil, threading

from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import FileResponse, JSONResponse

from dataset_loaders import get_dataset_list, load_dataset

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT     = Path(__file__).parent.parent
TMP_DIR  = ROOT / "tmp"
TMP_TTL  = 7200   # seconds — 2 hours
TMP_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(ROOT))

app = FastAPI(title="Ms t-SNE Explorer", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Session store ──────────────────────────────────────────────────────────────
sessions: dict[str, dict] = {}

# ── Temp file cleanup (background thread) ─────────────────────────────────────
def _cleanup_loop():
    while True:
        now = time.time()
        for sid in list(sessions.keys()):
            s = sessions[sid]
            if now - s.get("created_at", now) > TMP_TTL:
                sess_dir = TMP_DIR / sid
                if sess_dir.exists():
                    shutil.rmtree(sess_dir, ignore_errors=True)
                sessions.pop(sid, None)
        time.sleep(300)

threading.Thread(target=_cleanup_loop, daemon=True).start()

@app.get("/api/datasets")
def list_datasets():
    return get_dataset_list()

@app.get("/api/datasets/{dataset_id}/info")
def dataset_info(dataset_id: str):
    try:
        _, _, meta = load_dataset(dataset_id)
        return meta
    except Exception as e:
        raise HTTPException(404, f"Dataset not found: {e}")

# ── GPU status (Section 1 equivalent) ─────────────────────────────────────────
@app.get("/api/gpu-status")
def gpu_status():
    try:
        import cupy as cp
        props = cp.cuda.runtime.getDeviceProperties(0)
        free, total = cp.cuda.runtime.memGetInfo()
        return {
            "gpu_active": True,
            "gpu_name": props['name'].decode(),
            "cupy_version": cp.__version__,
            "vram_free_gb": round(free/1e9, 2),
            "vram_total_gb": round(total/1e9, 2),
        }
    except Exception as e:
        return {"gpu_active": False, "error": str(e)}

# ── Session create ─────────────────────────────────────────────────────────────
@app.post("/api/session")
def create_session():
    sid = str(uuid.uuid4())
    sess_dir = TMP_DIR / sid
    (sess_dir / "weights").mkdir(parents=True, exist_ok=True)
    (sess_dir / "figures").mkdir(exist_ok=True)
    sessions[sid] = {
        "created_at": time.time(),
        "status": "idle",
        "results": {},
        "meta": {}
    }
    return {"session_id": sid}

@app.delete("/api/session/{sid}")
def delete_session(sid: str):
    sess_dir = TMP_DIR / sid
    if sess_dir.exists():
        shutil.rmtree(sess_dir, ignore_errors=True)
    sessions.pop(sid, None)
    return {"deleted": sid}

# ── Upload CSV dataset (Section 7 equivalent) ─────────────────────────────────
@app.post("/api/session/{sid}/upload")
async def upload_dataset(sid: str, file: UploadFile = File(...)):
    if sid not in sessions:
        raise HTTPException(404, "Session not found")
    dest = TMP_DIR / sid / "dataset.csv"
    content = await file.read()
    dest.write_bytes(content)
    # Quick peek
    import pandas as pd, io
    df = pd.read_csv(io.BytesIO(content), nrows=5)
    return {
        "filename": file.filename,
        "shape_preview": f"{len(content)//1024}KB",
        "columns": list(df.columns),
        "preview_rows": 5
    }

# ── Experiment config ──────────────────────────────────────────────────────────
class ExperimentConfig(BaseModel):
    session_id: str
    dataset_source: str          # "upload" | built-in name
    label_column: Optional[str] = None
    feature_columns: Optional[list] = None
    pca_components: Optional[int] = None   # None = no PCA
    optimizers: list = ["L-BFGS-B", "SGD", "Momentum", "Adam"]
    adam_lr_list: list = [100.0, 10.0, 1.0, 0.1, 0.01, 0.001]
    n_iter: int = 200
    lr: float = 100.0
    momentum: float = 0.5
    beta1: float = 0.9
    beta2: float = 0.999
    seed: int = 40
    init: str = "pca"
    device: str = "gpu" 

# ── WebSocket experiment runner ────────────────────────────────────────────────
@app.websocket("/ws/{sid}/run")
async def run_experiment(websocket: WebSocket, sid: str):
    await websocket.accept()
    if sid not in sessions:
        await websocket.send_json({"type": "error", "msg": "Session not found"})
        await websocket.close(); return

    try:
        cfg_raw = await websocket.receive_json()
        cfg = ExperimentConfig(**cfg_raw)
    except Exception as e:
        await websocket.send_json({"type": "error", "msg": f"Config error: {e}"})
        await websocket.close(); return

    loop = asyncio.get_event_loop()
    sess_dir = TMP_DIR / sid

    async def send(msg_type, **kwargs):
        try:
            await websocket.send_json({"type": msg_type, "ts": datetime.now().isoformat(), **kwargs})
        except Exception:
            pass  # client disconnected — continue running, don't crash
    await send("log", section=1, msg="=== GPU VERIFICATION ===")
    gpu_info = gpu_status()
    await send("log", section=1, msg=f"GPU active: {gpu_info['gpu_active']}")
    if gpu_info.get("gpu_name"):
        await send("log", section=1, msg=f"GPU: {gpu_info['gpu_name']} | VRAM free: {gpu_info['vram_free_gb']} GB")
    await send("gpu_status", data=gpu_info)

    # ── Load data (Section 7) ─────────────────────────────────────────────────
    await send("log", section=7, msg="=== LOADING DATASET ===")
    try:
        import pandas as pd
        from engine.mstsne import eucl_dist_matr_best, USE_GPU, eval_dr_quality

        if cfg.dataset_source == 'upload':
            data_path = sess_dir / "dataset.csv"
            if not data_path.exists():
                await send("error", msg="No uploaded file found for this session")
                return
            df = pd.read_csv(data_path)
            y_col = cfg.label_column or df.columns[-1]
            feat_cols = cfg.feature_columns or [c for c in df.columns if c != y_col]
            X_hd = df[feat_cols].values.astype(np.float64)
            y    = df[y_col].values
            dataset_name = "uploaded dataset"
            await send("log", section=7, msg=f"Uploaded CSV loaded | shape={X_hd.shape}")
        else:
            X_hd, y, meta = await loop.run_in_executor(
                None, lambda: load_dataset(cfg.dataset_source))
            dataset_name = meta["name"]
            await send("log", section=7,
                msg=f"Dataset: {dataset_name} | N={meta['N']} | "
                    f"features={meta['features']} | classes={meta['n_classes']}")

        # PCA preprocessing if requested
        if cfg.pca_components and X_hd.shape[1] > cfg.pca_components:
            from sklearn.decomposition import PCA
            X_hd = PCA(n_components=cfg.pca_components,
                       random_state=cfg.seed).fit_transform(X_hd)
            await send("log", section=7, msg=f"PCA → {cfg.pca_components} components")

        N, M = X_hd.shape
        await send("log", section=7, msg=f"Final shape: N={N} | features={M}")
        await send("dataset_info", N=N, M=M, name=dataset_name)
    except Exception as e:
        await send("error", msg=f"Data loading failed: {e}"); return

    # ── HD distance matrix (Section 8) ────────────────────────────────────────
    await send("log", section=8, msg="=== COMPUTING HD DISTANCE MATRIX ===")
    t0 = time.time()
    dm_hd = await loop.run_in_executor(None, lambda: eucl_dist_matr_best(X_hd))
    await send("log", section=8, msg=f"HD distance matrix done in {time.time()-t0:.2f}s")

    results = {}
    adam_grid = {}
    sessions[sid]["status"] = "running"

    # ── Run each optimizer (Sections 9-13) ────────────────────────────────────
    from engine.mstsne import mstsne_with_optimizer, eucl_dist_matr_gpu, eucl_dist_matr_cpu

    dist_fn = eucl_dist_matr_gpu if cfg.device == 'gpu' else eucl_dist_matr_cpu
    dm_hd = await loop.run_in_executor(None, lambda: dist_fn(X_hd))

    async def run_opt(opt_name, lr_val, label, section):
        await send("log", section=section, msg=f"=== RUNNING: {label} ===")
        progress_msgs = []

        def progress_cb(n_perp, L, perp_h, cost, scale_time):
            progress_msgs.append({
                "scale": n_perp, "total_scales": L,
                "perp": round(perp_h,1), "cost": round(cost,6),
                "time": round(scale_time,2)
            })
            # keepalive ping so nginx doesn't timeout
            asyncio.run_coroutine_threadsafe(
                websocket.send_json({"type": "ping", "scale": n_perp, "total": L}),
                loop
            )

        t0 = time.time()
        X_ld = await loop.run_in_executor(None, lambda: mstsne_with_optimizer(
            X_hds=X_hd, init=cfg.init, n_components=2, dm_hds=dm_hd,
            seed_mstsne=cfg.seed, optimizer=opt_name, lr=lr_val,
            n_iter=cfg.n_iter, momentum=cfg.momentum,
            beta1=cfg.beta1, beta2=cfg.beta2, progress_cb=progress_cb
        ))
        elapsed = time.time() - t0

        for pm in progress_msgs:
            await send("scale_progress", **pm)

        rnx, auc = await loop.run_in_executor(
            None, lambda: eval_dr_quality(
                d_hd=dm_hd, d_ld=eucl_dist_matr_best(X_ld)))

        await send("log", section=section, msg=f"[{label}] AUC={auc:.6f} | Time={elapsed:.2f}s")
        await send("optimizer_result", optimizer=label, auc=round(auc,6), time=round(elapsed,2))

        # Save weights to tmp
        ts  = datetime.now().strftime('%Y%m%d_%H%M%S')
        np.save(sess_dir/"weights"/f"embedding_{label}_{ts}.npy", X_ld)
        np.save(sess_dir/"weights"/f"rnx_{label}_{ts}.npy", rnx)
        with open(sess_dir/"weights"/f"meta_{label}_{ts}.json",'w') as f:
            json.dump({'auc':float(auc),'time':elapsed,'optimizer':label,
                       'N':N,'mode':'GPU' if USE_GPU else 'CPU','timestamp':ts}, f, indent=2)

        return X_ld, rnx, float(auc), elapsed

    opt_section_map = {
        "L-BFGS-B": 9, "SGD": 10, "Momentum": 11
    }

    for opt in cfg.optimizers:
        if opt == "Adam": continue   # handled in lr sensitivity
        if opt in opt_section_map:
            X_ld, rnx, auc, elapsed = await run_opt(opt, cfg.lr, opt, opt_section_map[opt])
            results[opt] = {"X_ld": X_ld.tolist(), "rnx": rnx.tolist(),
                            "auc": auc, "time": elapsed}

    # ── Adam lr sensitivity (Section 12-13) ───────────────────────────────────
    if "Adam" in cfg.optimizers:
        await send("log", section=12, msg="=== ADAM lr=100 (catastrophic baseline) ===")
        await send("log", section=13, msg="=== ADAM LR SENSITIVITY SEARCH ===")
        best_auc = 0.0; best_lr = None; best_X_ld = None; best_rnx = None

        for lr_test in cfg.adam_lr_list:
            X_ld, rnx, auc, elapsed = await run_opt(
                "Adam", lr_test, f"Adam_lr{lr_test}", 12 if lr_test==100.0 else 13)
            adam_grid[lr_test] = {"auc": auc, "time": elapsed,
                                  "X_ld": X_ld.tolist(), "rnx": rnx.tolist()}
            if auc > best_auc:
                best_auc = auc; best_lr = lr_test
                best_X_ld = X_ld.copy(); best_rnx = rnx.copy()

        results["Adam_lr100"] = adam_grid.get(100.0, {})
        results["Adam_best"]  = {
            "X_ld": best_X_ld.tolist() if best_X_ld is not None else [],
            "rnx":  best_rnx.tolist() if best_rnx is not None else [],
            "auc": best_auc, "time": adam_grid.get(best_lr, {}).get("time", 0),
            "best_lr": best_lr
        }
        await send("log", section=13, msg=f"Best Adam: lr={best_lr} | AUC={best_auc:.6f}")
        await send("adam_sensitivity", grid={str(k): {"auc": v["auc"], "time": v["time"]}
                                              for k, v in adam_grid.items()},
                   best_lr=best_lr)

    # ── Generate figures (Sections 15-20) ─────────────────────────────────────
    await send("log", section=15, msg="=== GENERATING FIGURES ===")
    fig_paths = await loop.run_in_executor(
        None, lambda: _generate_figures(results, adam_grid, y, N,
                                        str(sess_dir/"figures"), dataset_name))
    for fig_key, fig_path in fig_paths.items():
        await send("figure_ready", key=fig_key,
                   url=f"/api/session/{sid}/figure/{Path(fig_path).name}")

    # ── Save final JSON (Section 21) ──────────────────────────────────────────
    save_data = {}
    for key, val in results.items():
        save_data[key] = {"auc": val.get("auc"), "time": val.get("time"),
                          "rnx": val.get("rnx")}
        if "best_lr" in val: save_data[key]["best_lr"] = val["best_lr"]
    save_data["adam_lr_grid"] = {
        str(lr): {"auc": v["auc"], "time": v["time"]}
        for lr, v in adam_grid.items()
    }
    save_data["meta"] = {
        "dataset": dataset_name, "N": N, "features": M,
        "mode": "GPU" if USE_GPU else "CPU", "seed": cfg.seed,
        "n_iter": cfg.n_iter, "timestamp": datetime.now().isoformat()
    }

    result_path = sess_dir / "results.json"
    result_path.write_text(json.dumps(save_data, indent=2))
    sessions[sid]["results"] = save_data
    sessions[sid]["status"]  = "done"

    await send("log", section=21, msg=f"Results saved ✓")
    await send("done", result_url=f"/api/session/{sid}/results")
    await websocket.close()

# ── Serve figures ──────────────────────────────────────────────────────────────
@app.get("/api/session/{sid}/figure/{fname}")
def get_figure(sid: str, fname: str):
    path = TMP_DIR / sid / "figures" / fname
    if not path.exists(): raise HTTPException(404, "Figure not found")
    return FileResponse(str(path), media_type="image/png")

@app.get("/api/session/{sid}/results")
def get_results(sid: str):
    path = TMP_DIR / sid / "results.json"
    if not path.exists(): raise HTTPException(404, "No results yet")
    return json.loads(path.read_text())

@app.get("/api/session/{sid}/download/results")
def download_results(sid: str):
    path = TMP_DIR / sid / "results.json"
    if not path.exists(): raise HTTPException(404)
    return FileResponse(str(path), media_type="application/json",
                        filename="mstsne_results.json")

# ── Figure generation (Sections 15-20 logic) ──────────────────────────────────
def _generate_figures(results, adam_grid, y, N, fig_dir, dataset_name):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm

    fig_dir = Path(fig_dir); fig_dir.mkdir(exist_ok=True)
    paths = {}

    # Unique colors per class
    classes  = np.unique(y)
    n_cls    = len(classes)
    cmap     = cm.get_cmap("tab20", n_cls)
    col_map  = {c: cmap(i) for i, c in enumerate(classes)}

    # Sections 15-18: embedding plots
    embed_keys = [k for k in ["L-BFGS-B","SGD","Momentum","Adam_best"] if k in results]
    for key in embed_keys:
        r = results[key]
        if not r.get("X_ld"): continue
        X_ld = np.array(r["X_ld"])
        auc  = r["auc"]; t = r["time"]
        label = key if key != "Adam_best" else f"Adam lr={r.get('best_lr','?')} (best)"
        fig, ax = plt.subplots(figsize=(7,6))
        for cls in classes:
            mask = y == cls
            ax.scatter(X_ld[mask,0], X_ld[mask,1],
                       c=[col_map[cls]], s=5, alpha=0.7, linewidths=0, label=str(cls))
        ax.set_title(f"{dataset_name} — {label}\nAUC={auc:.4f} | Time={t:.1f}s",
                     fontsize=11, fontweight="bold")
        ax.set_xticks([]); ax.set_yticks([])
        if n_cls <= 20:
            ax.legend(fontsize=8, markerscale=3, loc="best",
                      ncol=max(1, n_cls//10))
        plt.tight_layout()
        fname = f"embedding_{key}.png"
        fig.savefig(fig_dir/fname, dpi=120, bbox_inches="tight")
        plt.close(fig)
        safe_key = key.replace("-", "").replace(" ", "_")
        paths[f"embedding_{safe_key}"] = str(fig_dir/fname)

    # Section 19: R_NX curves
    fig, ax = plt.subplots(figsize=(8,5))
    plot_cfg = {
        "L-BFGS-B":  ("black",      "-",  "L-BFGS-B"),
        "SGD":        ("royalblue",  "-",  "SGD"),
        "Momentum":   ("green",      "-",  "Momentum"),
        "Adam_lr100": ("red",        "--", "Adam lr=100"),
        "Adam_best":  ("orange",     "-",  f"Adam lr={results.get('Adam_best',{}).get('best_lr','?')} (best)"),
    }
    for key, (col, ls, lbl) in plot_cfg.items():
        if key not in results or not results[key].get("rnx"): continue
        rnx = np.array(results[key]["rnx"])
        K   = np.arange(1, rnx.size+1)
        ax.semilogx(K, rnx, color=col, ls=ls, lw=2,
                    label=f"{lbl} (AUC={results[key]['auc']:.4f})")
    ax.axhline(0, color="grey", ls=":", lw=1)
    ax.set_xlabel("Neighbourhood size K (log scale)", fontsize=11)
    ax.set_ylabel("R_NX(K)", fontsize=11)
    ax.set_title(f"{dataset_name} — R_NX Quality Curves", fontsize=12)
    ax.legend(fontsize=9); ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(fig_dir/"rnx_curves.png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    paths["rnx_curves"] = str(fig_dir/"rnx_curves.png")

    # Section 20: AUC bar + lr sensitivity
    fig, axes = plt.subplots(1, 2, figsize=(12,4))
    keys_bar = [k for k in ["L-BFGS-B","SGD","Momentum","Adam_lr100","Adam_best"] if k in results]
    aucs     = [results[k]["auc"] for k in keys_bar]
    lbls     = [k if k != "Adam_best" else f"Adam\nlr={results['Adam_best'].get('best_lr','?')}"
                for k in keys_bar]
    colors   = {"L-BFGS-B":"#2c2c2c","SGD":"royalblue","Momentum":"green",
                "Adam_lr100":"red","Adam_best":"orange"}
    cols     = [colors.get(k,"gray") for k in keys_bar]
    bars = axes[0].bar(lbls, aucs, color=cols, edgecolor="black", width=0.55)
    for bar, auc in zip(bars, aucs):
        axes[0].text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.002,
                     f"{auc:.4f}", ha="center", fontsize=8)
    axes[0].set_ylabel("AUC"); axes[0].set_title(f"AUC Comparison — {dataset_name}")
    axes[0].set_ylim(0, max(aucs)*1.25 if aucs else 1)
    axes[0].grid(axis="y", alpha=0.3)

    if adam_grid:
        lr_vals  = sorted(adam_grid.keys())
        auc_vals = [adam_grid[lr]["auc"] for lr in lr_vals]
        axes[1].plot([str(lr) for lr in lr_vals], auc_vals,
                     marker="o", color="orange", lw=2, ms=8)
        for lr, auc in zip(lr_vals, auc_vals):
            axes[1].annotate(f"{auc:.4f}", xy=(str(lr), auc),
                             xytext=(0,8), textcoords="offset points",
                             ha="center", fontsize=8)
        if "L-BFGS-B" in results:
            axes[1].axhline(results["L-BFGS-B"]["auc"], color="black",
                            ls="--", lw=1.5, label="L-BFGS-B")
        axes[1].set_xlabel("Adam Learning Rate")
        axes[1].set_ylabel("AUC")
        axes[1].set_title(f"Adam lr Sensitivity — {dataset_name}")
        axes[1].legend(fontsize=9); axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    fig.savefig(fig_dir/"auc_summary.png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    paths["auc_summary"] = str(fig_dir/"auc_summary.png")
    return paths

def _load_builtin(name):
    from sklearn import datasets
    name = name.lower()
    if name == "iris":
        d = datasets.load_iris()
        return d.data, d.target, "Iris"
    if name == "digits":
        d = datasets.load_digits()
        return d.data, d.target, "Digits"
    if name == "wine":
        d = datasets.load_wine()
        return d.data, d.target, "Wine"
    if name == "breast_cancer":
        d = datasets.load_breast_cancer()
        return d.data, d.target, "Breast Cancer"
    raise ValueError(f"Unknown built-in dataset: {name}")

class SnippetRequest(BaseModel):
    code: str
    section: int

@app.post("/api/session/{sid}/run-snippet")
async def run_snippet(sid: str, req: SnippetRequest):
    if sid not in sessions:
        raise HTTPException(404, "Session not found")
    
    import io, contextlib, traceback
    import numpy as np
    import numba
    import scipy.spatial.distance
    import scipy.optimize
    import sklearn.decomposition
    
    # Safe execution namespace — inject numpy, cupy if available
    namespace = {
        "np":      np,
        "numba":   numba,
        "scipy":   scipy,
        "sklearn": sklearn,
        "pd":      pd,
        "time":    __import__("time"),
        "os":      __import__("os"),
        "json":    __import__("json"),
    }

    # CuPy optional
    try:
        import cupy as cp
        namespace["cp"] = cp
    except ImportError:
        namespace["cp"] = None

    try:
        import sklearn
        namespace["sklearn"] = sklearn
    except ImportError:
        pass

    stdout_capture = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout_capture):
            exec(compile(req.code, "<node-snippet>", "exec"), namespace)
        output = stdout_capture.getvalue() or "✓ Ran successfully (no output)"
        return {"output": output, "error": None}
    except Exception:
        return {"output": None, "error": traceback.format_exc()}
    
    # Add mstSNE engine functions directly into namespace
    try:
        from engine.mstsne import (
            eucl_dist_matr_best, eucl_dist_matr_cpu,
            ms_perplexities, sne_hd_similarities,
            mstsne_ld_sim, mstsne_obj, mstsne_grad,
            eval_dr_quality, eval_rnx, eval_auc,
            coranking, init_lds, mstsne_with_optimizer,
            fill_diago, close_to_zero, arange_except_i,
            n_eps_np_float64
        )
        namespace.update({
            "eucl_dist_matr_best": eucl_dist_matr_best,
            "eucl_dist_matr_cpu":  eucl_dist_matr_cpu,
            "ms_perplexities":     ms_perplexities,
            "sne_hd_similarities": sne_hd_similarities,
            "mstsne_ld_sim":       mstsne_ld_sim,
            "mstsne_obj":          mstsne_obj,
            "mstsne_grad":         mstsne_grad,
            "eval_dr_quality":     eval_dr_quality,
            "mstsne_with_optimizer": mstsne_with_optimizer,
            "n_eps_np_float64":    n_eps_np_float64,
        })
    except Exception as e:
        namespace["_engine_load_error"] = str(e)
