"""
Ms t-SNE engine — extracted from musk_v2_optimizer_gpu.ipynb
Supports: L-BFGS-B, SGD, Momentum, Adam
GPU (CuPy) with CPU fallback
"""
import numpy as np
import numba
import scipy.spatial.distance
import scipy.optimize
import sklearn.decomposition
import time, gc

# ── Constants (from Section 3) ────────────────────────────────────────────────
seed_MstSNE_def  = 40
dr_nitmax        = 30
dr_gtol          = 10**(-5)
dr_ftol          = 2.2204460492503131e-09
dr_maxls         = 30
dr_maxcor        = 6
n_eps_np_float64 = np.finfo(dtype=np.float64).eps

# ── Section 5: Core functions ─────────────────────────────────────────────────
@numba.jit(nopython=True)
def close_to_zero(v):
    return np.absolute(v) <= 10.0**(-8.0)

@numba.jit(nopython=True)
def arange_except_i(N, i):
    arr = np.arange(N)
    return np.hstack((arr[:i], arr[i+1:]))

@numba.jit(nopython=True)
def fill_diago(M, v):
    for i in range(M.shape[0]):
        M[i, i] = v
    return M

def eucl_dist_matr_cpu(X):
    return scipy.spatial.distance.squareform(
        scipy.spatial.distance.pdist(X, metric='euclidean'))

def eucl_dist_matr_gpu(X):
    try:
        import cupy as cp
        X_g = cp.asarray(X, dtype=cp.float32)
        sq  = cp.sum(X_g**2, axis=1, keepdims=True)
        D2  = cp.maximum(sq+sq.T-2.0*(X_g@X_g.T), 0.0)
        D_g = cp.sqrt(D2); cp.fill_diagonal(D_g, 0.0)
        cp.cuda.Stream.null.synchronize()
        result = cp.asnumpy(D_g).astype(np.float64)
        del X_g, sq, D2, D_g
        cp.get_default_memory_pool().free_all_blocks()
        return result
    except Exception:
        return eucl_dist_matr_cpu(X)

def sqeucl_dist_matr_gpu(X):
    try:
        import cupy as cp
        X_g = cp.asarray(X, dtype=cp.float32)
        sq  = cp.sum(X_g**2, axis=1, keepdims=True)
        D2  = cp.maximum(sq+sq.T-2.0*(X_g@X_g.T), 0.0)
        cp.fill_diagonal(D2, 0.0)
        result = cp.asnumpy(D2).astype(np.float64)
        del X_g, sq, D2
        cp.get_default_memory_pool().free_all_blocks()
        return result
    except Exception:
        return scipy.spatial.distance.squareform(
            scipy.spatial.distance.pdist(X, metric='sqeuclidean'))

try:
    import cupy as cp
    _t = cp.asarray(np.ones((10,10), dtype=np.float32))
    _ = _t @ _t.T
    cp.get_default_memory_pool().free_all_blocks()
    eucl_dist_matr_best = eucl_dist_matr_gpu
    USE_GPU = True
except Exception:
    eucl_dist_matr_best = eucl_dist_matr_cpu
    USE_GPU = False

@numba.jit(nopython=True)
def ms_perplexities(N, K_star=2, L_min=-1, L_max=-1):
    if L_min == -1: L_min = 1
    if L_max == -1: L_max = int(round(np.log2(np.float64(N)/np.float64(K_star))))
    L   = L_max - L_min + 1
    K_h = (np.float64(2.0)**(np.linspace(L_min-1, L_max-1, L).astype(np.float64))) * np.float64(K_star)
    return L, K_h

def init_lds(X_hds, N, init='pca', n_components=2, rand_state=None):
    if rand_state is None: rand_state = np.random
    if isinstance(init, str) and init == 'pca':
        return sklearn.decomposition.PCA(
            n_components=n_components, random_state=rand_state).fit_transform(X_hds)
    elif isinstance(init, np.ndarray):
        return init
    return rand_state.randn(N, n_components)

@numba.jit(nopython=True)
def sne_sim(dsi, vi, i, compute_log=True):
    N  = dsi.size
    si = np.empty(N, dtype=np.float64); si[i] = 0.0
    log_si = np.empty(N, dtype=np.float64)
    indj   = arange_except_i(N, i); dsij = dsi[indj]
    log_num = (dsij.min()-dsij)/vi
    si[indj] = np.exp(log_num); den = si.sum(); si /= den
    if compute_log:
        log_si[i] = 0.0; log_si[indj] = log_num - np.log(den)
    return si, log_si

@numba.jit(nopython=True)
def sne_bsf(dsi, vi, i, log_perp):
    si, log_si = sne_sim(dsi, vi, i, compute_log=True)
    return -np.dot(si, log_si) - log_perp

@numba.jit(nopython=True)
def sne_bs(dsi, i, log_perp, x0=1.0):
    fx0 = sne_bsf(dsi, x0, i, log_perp)
    if close_to_zero(fx0): return x0
    elif not np.isfinite(fx0): raise ValueError("fx0 nan")
    elif fx0 > 0:
        x_up, x_low = x0, x0/2.0
        fx_low = sne_bsf(dsi, x_low, i, log_perp)
        if close_to_zero(fx_low): return x_low
        elif not np.isfinite(fx_low): return x_up
        while fx_low > 0:
            x_up, x_low = x_low, x_low/2.0
            fx_low = sne_bsf(dsi, x_low, i, log_perp)
            if close_to_zero(fx_low): return x_low
            if not np.isfinite(fx_low): return x_up
    else:
        x_up, x_low = x0*2.0, x0
        fx_up = sne_bsf(dsi, x_up, i, log_perp)
        if close_to_zero(fx_up): return x_up
        elif not np.isfinite(fx_up): return x_low
        while fx_up < 0:
            x_up, x_low = 2.0*x_up, x_up
            fx_up = sne_bsf(dsi, x_up, i, log_perp)
            if close_to_zero(fx_up): return x_up
    while True:
        x = (x_up+x_low)/2.0
        fx = sne_bsf(dsi, x, i, log_perp)
        if close_to_zero(fx): return x
        elif fx > 0: x_up = x
        else: x_low = x

@numba.jit(nopython=True)
def sne_hd_similarities(dsm_hds, perp, compute_log=True,
                         start_bs=np.ones(1, dtype=np.float64)):
    if perp <= 1: raise ValueError("perp must be > 1")
    N = dsm_hds.shape[0]
    if start_bs.size == 1: start_bs = np.ones(N, dtype=np.float64)
    log_perp = np.log(min(np.float64(perp), np.floor(0.99*np.float64(N))))
    si     = np.empty((N,N), dtype=np.float64)
    log_si = np.empty((N,N), dtype=np.float64)
    arr_vi = np.empty(N, dtype=np.float64)
    for i in range(N):
        vi = sne_bs(dsm_hds[i,:], i, log_perp, x0=start_bs[i])
        tmp = sne_sim(dsm_hds[i,:], vi, i, compute_log)
        si[i,:] = tmp[0]
        if compute_log: log_si[i,:] = tmp[1]
        arr_vi[i] = vi
    return si, log_si, arr_vi

@numba.jit(nopython=True)
def mstsne_ld_sim(dsm_ld):
    global n_eps_np_float64
    dsm_ld_one     = 1.0+dsm_ld
    inv_dsm_ld_one = 1.0/np.maximum(n_eps_np_float64, dsm_ld_one)
    t_ij     = inv_dsm_ld_one.copy()
    log_t_ij = -np.log(dsm_ld_one)
    t_ij     = fill_diago(t_ij, 0.0)
    log_t_ij = fill_diago(log_t_ij, 0.0)
    den      = t_ij.sum()
    t_ij    /= np.maximum(n_eps_np_float64, den)
    log_t_ij -= np.log(den)
    return t_ij, log_t_ij, inv_dsm_ld_one

def mstsne_obj(x, tau_ij, N, n_components, arr_one, prod_N_nc):
    try:
        import cupy as cp
        X_lds = np.reshape(x, (N, n_components))
        X_g   = cp.asarray(X_lds, dtype=cp.float32)
        sq    = cp.sum(X_g**2, axis=1, keepdims=True)
        D2    = cp.maximum(sq+sq.T-2.0*(X_g@X_g.T), 0.0)
        cp.fill_diagonal(D2, 0.0); del sq
        D2_64      = D2.astype(cp.float64); del D2
        dsm_ld_one = 1.0+D2_64
        inv_one    = 1.0/cp.maximum(n_eps_np_float64, dsm_ld_one)
        t_ij_g     = inv_one.copy()
        log_t_ij_g = -cp.log(dsm_ld_one)
        del D2_64, dsm_ld_one, inv_one
        diag_idx = cp.arange(N)
        t_ij_g[diag_idx,diag_idx]     = 0.0
        log_t_ij_g[diag_idx,diag_idx] = 0.0
        den = cp.maximum(n_eps_np_float64, t_ij_g.sum())
        t_ij_g /= den; log_t_ij_g -= cp.log(den); del t_ij_g
        cp.get_default_memory_pool().free_all_blocks()
        tau_g = cp.asarray(tau_ij, dtype=cp.float64)
        cost  = float(-cp.dot(tau_g.ravel(), log_t_ij_g.ravel()))
        del tau_g, log_t_ij_g
        cp.get_default_memory_pool().free_all_blocks()
        return cost
    except Exception:
        X_lds    = np.reshape(x, (N, n_components))
        dsm_ld   = sqeucl_dist_matr_gpu(X_lds)
        log_t_ij = mstsne_ld_sim(dsm_ld)[1]
        return -np.dot(tau_ij.ravel(), log_t_ij.ravel())

def mstsne_grad(x, tau_ij, N, n_components, arr_one, prod_N_nc):
    try:
        import cupy as cp
        X_lds = np.reshape(x, (N, n_components))
        X_g   = cp.asarray(X_lds, dtype=cp.float32)
        sq    = cp.sum(X_g**2, axis=1, keepdims=True)
        D2    = cp.maximum(sq+sq.T-2.0*(X_g@X_g.T), 0.0)
        cp.fill_diagonal(D2, 0.0); del sq
        D2_64      = D2.astype(cp.float64); del D2
        dsm_ld_one = 1.0+D2_64
        inv_one    = 1.0/cp.maximum(n_eps_np_float64, dsm_ld_one)
        t_ij_g     = inv_one.copy()
        del D2_64, dsm_ld_one
        diag_idx = cp.arange(N)
        t_ij_g[diag_idx,diag_idx] = 0.0
        t_ij_g /= cp.maximum(n_eps_np_float64, t_ij_g.sum())
        tau_g  = cp.asarray(tau_ij, dtype=cp.float64)
        c_ij_g = 4.0*(tau_g-t_ij_g)*inv_one
        del tau_g, t_ij_g, inv_one
        cp.get_default_memory_pool().free_all_blocks()
        X_g64     = X_g.astype(cp.float64); del X_g
        arr_one_g = cp.asarray(arr_one, dtype=cp.float64)
        grad_g    = (X_g64.T*cp.dot(c_ij_g,arr_one_g)).T - cp.dot(c_ij_g,X_g64)
        del c_ij_g, X_g64, arr_one_g
        cp.cuda.Stream.null.synchronize()
        result = cp.asnumpy(grad_g).flatten(); del grad_g
        cp.get_default_memory_pool().free_all_blocks()
        return result
    except Exception:
        X_lds  = np.reshape(x, (N, n_components))
        dsm_ld = sqeucl_dist_matr_gpu(X_lds)
        t_ij, log_t_ij, inv_dsm_ld_one = mstsne_ld_sim(dsm_ld)
        c_ij    = 4.0*(tau_ij-t_ij)*inv_dsm_ld_one
        grad_ld = (X_lds.T*np.dot(c_ij,arr_one)).T - np.dot(c_ij,X_lds)
        return np.reshape(grad_ld, prod_N_nc)

def mstsne_manage_seed(seed_mstsne=None):
    if seed_mstsne is None: seed_mstsne = seed_MstSNE_def
    return np.random.RandomState(seed_mstsne) if seed_mstsne > 0 else np.random

# ── Section 6: Optimizer runner ───────────────────────────────────────────────
def run_optimizer(X_lds, tau_ij, N, n_components, arr_one, prod_N_nc,
                  optimizer='L-BFGS-B', lr=100.0, n_iter=200,
                  momentum=0.5, beta1=0.9, beta2=0.999):
    args = (tau_ij, N, n_components, arr_one, prod_N_nc)
    if optimizer == 'L-BFGS-B':
        res = scipy.optimize.minimize(
            fun=mstsne_obj, x0=X_lds, args=args, method='L-BFGS-B',
            jac=mstsne_grad, bounds=None,
            options={'disp':False,'maxls':dr_maxls,'gtol':dr_gtol,
                     'maxiter':dr_nitmax,'maxcor':dr_maxcor,
                     'maxfun':np.inf,'ftol':dr_ftol})
        return res.x
    elif optimizer == 'SGD':
        x = X_lds.copy()
        for t in range(n_iter):
            g = mstsne_grad(x, *args); x = x - lr*g
            if np.sqrt(np.sum(g**2)) < dr_gtol: break
        return x
    elif optimizer == 'Momentum':
        x = X_lds.copy(); v = np.zeros_like(x)
        for t in range(n_iter):
            g = mstsne_grad(x, *args)
            v = momentum*v - lr*g; x = x + v
            if np.sqrt(np.sum(g**2)) < dr_gtol: break
        return x
    elif optimizer == 'Adam':
        x = X_lds.copy(); m = np.zeros_like(x); v = np.zeros_like(x); eps=1e-8
        for t in range(1, n_iter+1):
            g  = mstsne_grad(x, *args)
            m  = beta1*m + (1-beta1)*g
            v  = beta2*v + (1-beta2)*g**2
            mh = m/(1-beta1**t); vh = v/(1-beta2**t)
            x  = x - lr*mh/(np.sqrt(vh)+eps)
            if np.sqrt(np.sum(g**2)) < dr_gtol: break
        return x
    raise ValueError(f"Unknown optimizer: {optimizer}")

def mstsne_with_optimizer(X_hds, init='pca', n_components=2, dm_hds=None,
                           seed_mstsne=None, optimizer='L-BFGS-B',
                           lr=100.0, n_iter=200, momentum=0.5,
                           beta1=0.9, beta2=0.999, progress_cb=None):
    dm_hds_none = dm_hds is None
    dsm_hds     = None if dm_hds_none else (dm_hds**2).astype(np.float64)
    rand_state  = mstsne_manage_seed(seed_mstsne)
    N           = X_hds.shape[0] if dm_hds_none else dsm_hds.shape[0]
    prod_N_nc   = N * n_components
    L, K_h      = ms_perplexities(N=N, K_star=2)
    X_lds       = init_lds(X_hds, N, init, n_components, rand_state)
    X_lds       = np.reshape(X_lds, prod_N_nc)
    sigma_ij    = np.zeros((N,N), dtype=np.float64)
    tau_ij      = np.empty((N,N), dtype=np.float64)
    arr_one     = np.ones(N, dtype=np.float64)
    N_2         = np.float64(2*N)
    for n_perp in range(1, L+1):
        h = L-n_perp; perp_h = K_h[h]
        sim_h    = sne_hd_similarities(dsm_hds, perp_h, compute_log=False)[0]
        scale_t0 = time.time()
        sigma_ij = (sigma_ij*(np.float64(n_perp)-1.0)+sim_h)/np.float64(n_perp)
        tau_ij   = (sigma_ij+sigma_ij.T)/N_2
        del sim_h; gc.collect()
        X_lds = run_optimizer(X_lds, tau_ij, N, n_components, arr_one,
                              prod_N_nc, optimizer=optimizer, lr=lr,
                              n_iter=n_iter, momentum=momentum,
                              beta1=beta1, beta2=beta2)
        try:
            import cupy as cp
            cp.get_default_memory_pool().free_all_blocks()
        except Exception:
            pass
        gc.collect()
        scale_time = time.time()-scale_t0
        if progress_cb:
            cost = mstsne_obj(X_lds, tau_ij, N, n_components, arr_one, prod_N_nc)
            progress_cb(n_perp, L, perp_h, cost, scale_time)
    return np.reshape(X_lds, (N, n_components))

# ── Quality metrics (Sections 5) ──────────────────────────────────────────────
def coranking(d_hd, d_ld):
    perm_hd = d_hd.argsort(axis=-1, kind='mergesort')
    perm_ld = d_ld.argsort(axis=-1, kind='mergesort')
    N = d_hd.shape[0]; i = np.arange(N, dtype=np.int64)
    R = np.empty((N,N), dtype=np.int64)
    for j in range(N): R[perm_ld[j,i], j] = i
    Q = np.zeros((N,N), dtype=np.int64)
    for j in range(N): Q[i, R[perm_hd[j,i], j]] += 1
    return Q[1:,1:]

@numba.jit(nopython=True)
def eval_auc(arr):
    i_all_k = 1.0/(np.arange(arr.size)+1.0)
    return np.float64(np.dot(arr, i_all_k))/(i_all_k.sum())

@numba.jit(nopython=True)
def eval_rnx(Q):
    N_1 = Q.shape[0]; N = N_1+1
    qnxk = np.empty(N_1, dtype=np.float64); acc_q = 0.0
    for K in range(N_1):
        acc_q += (Q[K,K]+np.sum(Q[K,:K])+np.sum(Q[:K,K]))
        qnxk[K] = acc_q/((K+1)*N)
    arr_K = np.arange(N_1)[1:].astype(np.float64)
    return (N_1*qnxk[:N_1-1]-arr_K)/(N_1-arr_K)

def eval_dr_quality(d_hd, d_ld):
    rnxk = eval_rnx(Q=coranking(d_hd=d_hd, d_ld=d_ld))
    return rnxk, eval_auc(rnxk)
