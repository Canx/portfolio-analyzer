# src/optimizer.py

import pandas as pd
import numpy as np
from scipy.optimize import minimize
from scipy.cluster.hierarchy import linkage

def hrp_allocation(cov: pd.DataFrame, corr: pd.DataFrame) -> pd.Series:
    """
    Implementación de Hierarchical Risk Parity (HRP).
    Devuelve una serie de pesos indexada por los ISINs.
    """
    labels = list(cov.index)
    dist = ((1 - corr) / 2.0) ** 0.5
    link = linkage(dist, method="ward")

    def get_quasi_diag(link):
        link = link.astype(int)
        sort_ix = pd.Series([link[-1, 0], link[-1, 1]])
        num_items = link[-1, 3]
        while sort_ix.max() >= num_items:
            sort_ix.index = range(0, sort_ix.shape[0] * 2, 2)
            df0 = sort_ix[sort_ix >= num_items]
            i = df0.index
            j = df0.values - num_items
            sort_ix[i] = link[j, 0]
            df1 = pd.Series(link[j, 1], index=i + 1)
            sort_ix = pd.concat([sort_ix, df1])
            sort_ix = sort_ix.sort_index()
        return sort_ix.tolist()

    sort_ix_indices = get_quasi_diag(link)
    sort_ix = [labels[i] for i in sort_ix_indices]

    def get_cluster_var(cov, cluster_items):
        cov_ = cov.loc[cluster_items, cluster_items]
        w = np.ones(len(cov_)) / len(cov_)
        return np.dot(w, np.dot(cov_, w))

    def recursive_bisection(cov, sort_ix):
        w = pd.Series(1, index=sort_ix)
        clusters = [sort_ix]
        while len(clusters) > 0:
            clusters_ = []
            for cluster_items in clusters:
                if len(cluster_items) <= 1:
                    continue
                split = int(len(cluster_items) / 2)
                c1 = cluster_items[:split]
                c2 = cluster_items[split:]
                var1 = get_cluster_var(cov, c1)
                var2 = get_cluster_var(cov, c2)
                alpha = 1 - var1 / (var1 + var2)
                w[c1] *= alpha
                w[c2] *= 1 - alpha
                clusters_ += [c1, c2]
            clusters = clusters_
        return w

    hrp_weights = recursive_bisection(cov, sort_ix)
    return hrp_weights / hrp_weights.sum()