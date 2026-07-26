import math
import statistics as _stats_module
from collections import Counter

from .base_plugin import AnikaPlugin
from core.interpreter import NativeFunction
from core.errors import FMS_Error

class StatsPlugin(AnikaPlugin):
    def _get_scipy(self):
        try:
            import scipy.stats as sps
            return sps
        except ImportError:
            raise FMS_Error("Advanced stats require scipy. Run: pip install scipy", error_type="Import Error")

    def _clean_list(self, data):
        cleaned = []
        for v in data:
            if v is None: continue
            try:
                n = float(v)
                if not math.isnan(n) and not math.isinf(n): cleaned.append(n)
            except (ValueError, TypeError): continue
        return cleaned

    def register(self, env, interpreter):
        # ==========================================================================
        # HELPER FUNCTIONS
        # ==========================================================================
        def stats_describe(i, a):
            data = self._clean_list(a[0])
            if len(data) == 0:
                raise FMS_Error("STATS_DESCRIBE requires non-empty numeric data", error_type="Stats Error")
            data_sorted = sorted(data)
            n = len(data)
            mean_val = sum(data) / n
            median_val = _stats_module.median(data)
            variance_val = _stats_module.variance(data) if n > 1 else 0
            stdev_val = _stats_module.stdev(data) if n > 1 else 0
            sem_val = stdev_val / (n ** 0.5) if n > 0 else 0
            try:
                mode_val = _stats_module.mode(data).mode if hasattr(_stats_module.mode(data), 'mode') else _stats_module.mode(data)
                if isinstance(mode_val, (list, tuple)): mode_val = mode_val[0]
            except: mode_val = None
            def percentile(d, p):
                k = (len(d) - 1) * p / 100
                f = int(k)
                c = f + 1 if f + 1 < len(d) else f
                return d[f] + (k - f) * (d[c] - d[f])
            q1 = percentile(data_sorted, 25)
            q3 = percentile(data_sorted, 75)
            iqr = q3 - q1
            sps = self._get_scipy()
            skew_val = float(sps.skew(data))
            kurt_val = float(sps.kurtosis(data))
            return {"n": n, "mean": mean_val, "median": median_val, "mode": mode_val,
                    "min": min(data), "max": max(data), "range": max(data) - min(data),
                    "sum": sum(data), "variance": variance_val, "stdev": stdev_val, "sem": sem_val,
                    "q1": q1, "q3": q3, "iqr": iqr, "skewness": skew_val, "kurtosis": kurt_val}

        env.define("STATS_DESCRIBE", NativeFunction("STATS_DESCRIBE", 1, stats_describe))
        env.define("STATS_MEAN", NativeFunction("STATS_MEAN", 1, lambda i, a: sum(self._clean_list(a[0])) / len(self._clean_list(a[0])) if self._clean_list(a[0]) else 0))
        env.define("STATS_MEDIAN", NativeFunction("STATS_MEDIAN", 1, lambda i, a: _stats_module.median(self._clean_list(a[0])) if self._clean_list(a[0]) else 0))
        env.define("STATS_VARIANCE", NativeFunction("STATS_VARIANCE", 1, lambda i, a: _stats_module.variance(self._clean_list(a[0])) if len(self._clean_list(a[0])) > 1 else 0))
        env.define("STATS_STDEV", NativeFunction("STATS_STDEV", 1, lambda i, a: _stats_module.stdev(self._clean_list(a[0])) if len(self._clean_list(a[0])) > 1 else 0))

        def stats_mode(i, a):
            d = self._clean_list(a[0])
            if not d: return None
            counter = Counter(d)
            max_count = max(counter.values())
            modes = [k for k, v in counter.items() if v == max_count]
            return modes[0] if len(modes) == 1 else modes

        def stats_percentile(i, a):
            d = sorted(self._clean_list(a[0]))
            p = float(a[1])
            if not d: return 0
            k = (len(d) - 1) * p / 100
            f = int(k)
            c = f + 1 if f + 1 < len(d) else f
            return d[f] + (k - f) * (d[c] - d[f])

        def stats_quartiles(i, a):
            d = sorted(self._clean_list(a[0]))
            if not d: return {"q1": 0, "q2": 0, "q3": 0, "iqr": 0}
            def pct(lst, p):
                k = (len(lst) - 1) * p / 100
                f = int(k)
                c = f + 1 if f + 1 < len(lst) else f
                return lst[f] + (k - f) * (lst[c] - lst[f])
            q1, q2, q3 = pct(d, 25), pct(d, 50), pct(d, 75)
            return {"q1": q1, "q2": q2, "q3": q3, "iqr": q3 - q1}

        def stats_skewness(i, a):
            sps = self._get_scipy()
            d = self._clean_list(a[0])
            return float(sps.skew(d)) if len(d) > 2 else 0

        def stats_kurtosis(i, a):
            sps = self._get_scipy()
            d = self._clean_list(a[0])
            return float(sps.kurtosis(d)) if len(d) > 3 else 0

        def stats_frequency(i, a): return dict(Counter(a[0]))

        def stats_crosstab(i, a):
            x, y = a[0], a[1]
            if len(x) != len(y): raise FMS_Error("STATS_CROSSTAB requires equal-length lists", error_type="Stats Error")
            rows = sorted(set(x)); cols = sorted(set(y))
            table = []
            for r in rows:
                row_data = []
                for c in cols:
                    count = sum(1 for xi, yi in zip(x, y) if xi == r and yi == c)
                    row_data.append(count)
                table.append(row_data)
            row_totals = [sum(row) for row in table]
            col_totals = [sum(table[i][j] for i in range(len(rows))) for j in range(len(cols))]
            grand_total = sum(row_totals)
            return {"rows": rows, "cols": cols, "table": table, "row_totals": row_totals, "col_totals": col_totals, "grand_total": grand_total}

        def stats_ttest_1sample(i, a):
            sps = self._get_scipy(); d = self._clean_list(a[0]); mu = float(a[1])
            if len(d) < 2: raise FMS_Error("One-sample t-test requires at least 2 observations", error_type="Stats Error")
            t_stat, p_val = sps.ttest_1samp(d, mu)
            return {"t": float(t_stat), "p": float(p_val), "df": len(d) - 1, "mean": sum(d)/len(d), "mu": mu, "significant": p_val < 0.05}

        def stats_ttest_ind(i, a):
            sps = self._get_scipy(); d1, d2 = self._clean_list(a[0]), self._clean_list(a[1])
            equal_var = bool(a[2]) if len(a) > 2 else True
            if len(d1) < 2 or len(d2) < 2: raise FMS_Error("Each group needs at least 2 observations", error_type="Stats Error")
            t_stat, p_val = sps.ttest_ind(d1, d2, equal_var=equal_var)
            return {"t": float(t_stat), "p": float(p_val), "mean1": sum(d1)/len(d1), "mean2": sum(d2)/len(d2), "n1": len(d1), "n2": len(d2), "significant": p_val < 0.05}

        def stats_ttest_paired(i, a):
            sps = self._get_scipy(); d1, d2 = self._clean_list(a[0]), self._clean_list(a[1])
            if len(d1) != len(d2): raise FMS_Error("Paired t-test requires equal-length lists", error_type="Stats Error")
            if len(d1) < 2: raise FMS_Error("Paired t-test requires at least 2 pairs", error_type="Stats Error")
            t_stat, p_val = sps.ttest_rel(d1, d2)
            return {"t": float(t_stat), "p": float(p_val), "n": len(d1), "mean_diff": sum(x-y for x,y in zip(d1,d2))/len(d1), "significant": p_val < 0.05}

        def stats_anova(i, a):
            sps = self._get_scipy(); groups = [self._clean_list(g) for g in a]
            if len(groups) < 2: raise FMS_Error("ANOVA requires at least 2 groups", error_type="Stats Error")
            for g in groups:
                if len(g) < 2: raise FMS_Error("Each ANOVA group needs at least 2 observations", error_type="Stats Error")
            f_stat, p_val = sps.f_oneway(*groups)
            return {"F": float(f_stat), "p": float(p_val), "k_groups": len(groups), "group_means": [sum(g)/len(g) for g in groups], "significant": p_val < 0.05}

        def stats_chisquare(i, a):
            sps = self._get_scipy(); observed = self._clean_list(a[0])
            expected = self._clean_list(a[1]) if len(a) > 1 else None
            if len(observed) < 2: raise FMS_Error("Chi-square requires at least 2 categories", error_type="Stats Error")
            chi2, p_val = sps.chisquare(observed, f_exp=expected)
            return {"chi2": float(chi2), "p": float(p_val), "df": len(observed) - 1, "significant": p_val < 0.05}

        def stats_chisquare_indep(i, a):
            sps = self._get_scipy(); ct = stats_crosstab(i, a)
            chi2, p_val, df, expected = sps.chi2_contingency(ct["table"])
            return {"chi2": float(chi2), "p": float(p_val), "df": int(df), "crosstab": ct, "significant": p_val < 0.05}

        def stats_correlation(i, a):
            sps = self._get_scipy(); x, y = self._clean_list(a[0]), self._clean_list(a[1])
            if len(x) != len(y): raise FMS_Error("Correlation requires equal-length lists", error_type="Stats Error")
            if len(x) < 3: raise FMS_Error("Correlation requires at least 3 pairs", error_type="Stats Error")
            r, p_val = sps.pearsonr(x, y)
            return {"r": float(r), "p": float(p_val), "n": len(x), "r_squared": float(r**2), "significant": p_val < 0.05}

        def stats_spearman(i, a):
            sps = self._get_scipy(); x, y = self._clean_list(a[0]), self._clean_list(a[1])
            if len(x) != len(y): raise FMS_Error("Spearman requires equal-length lists", error_type="Stats Error")
            rho, p_val = sps.spearmanr(x, y)
            return {"rho": float(rho), "p": float(p_val), "n": len(x), "significant": p_val < 0.05}

        def stats_regression(i, a):
            sps = self._get_scipy(); x, y = self._clean_list(a[0]), self._clean_list(a[1])
            if len(x) != len(y): raise FMS_Error("Regression requires equal-length lists", error_type="Stats Error")
            if len(x) < 3: raise FMS_Error("Regression requires at least 3 pairs", error_type="Stats Error")
            res = sps.linregress(x, y)
            return {"slope": float(res.slope), "intercept": float(res.intercept), "r_value": float(res.rvalue), "r_squared": float(res.rvalue**2), "p": float(res.pvalue), "stderr": float(res.stderr), "significant": res.pvalue < 0.05}

        def stats_mannwhitney(i, a):
            sps = self._get_scipy(); d1, d2 = self._clean_list(a[0]), self._clean_list(a[1])
            u_stat, p_val = sps.mannwhitneyu(d1, d2, alternative='two-sided')
            return {"U": float(u_stat), "p": float(p_val), "median1": float(_stats_module.median(d1)), "median2": float(_stats_module.median(d2)), "significant": p_val < 0.05}

        def stats_wilcoxon(i, a):
            sps = self._get_scipy(); d1, d2 = self._clean_list(a[0]), self._clean_list(a[1])
            if len(d1) != len(d2): raise FMS_Error("Wilcoxon requires equal-length lists", error_type="Stats Error")
            w_stat, p_val = sps.wilcoxon(d1, d2)
            return {"W": float(w_stat), "p": float(p_val), "n": len(d1), "significant": p_val < 0.05}

        def stats_kruskal(i, a):
            sps = self._get_scipy(); groups = [self._clean_list(g) for g in a]
            h_stat, p_val = sps.kruskal(*groups)
            return {"H": float(h_stat), "p": float(p_val), "k_groups": len(groups), "significant": p_val < 0.05}

        def stats_zscore(i, a):
            d = self._clean_list(a[0])
            if len(d) < 2: raise FMS_Error("Z-score requires at least 2 values", error_type="Stats Error")
            mean_val = sum(d) / len(d); sd = _stats_module.stdev(d)
            if sd == 0: return [0.0] * len(d)
            return [(x - mean_val) / sd for x in d]

        def stats_clean(i, a): return self._clean_list(a[0])
        def stats_recode(i, a): return [a[1].get(v, v) for v in a[0]]

        def stats_group_by(i, a):
            data, group_key, val_key = a[0], str(a[1]), str(a[2])
            agg = str(a[3]).lower() if len(a) > 3 else "mean"
            groups = {}
            for row in data:
                k = row.get(group_key); v = row.get(val_key)
                if k not in groups: groups[k] = []
                try: groups[k].append(float(v))
                except (ValueError, TypeError): continue
            result = []
            for k, vals in groups.items():
                if agg == "mean": agg_val = sum(vals)/len(vals) if vals else 0
                elif agg == "sum": agg_val = sum(vals)
                elif agg == "count": agg_val = len(vals)
                elif agg == "min": agg_val = min(vals) if vals else 0
                elif agg == "max": agg_val = max(vals) if vals else 0
                elif agg == "median": agg_val = _stats_module.median(vals) if vals else 0
                else: agg_val = sum(vals)/len(vals) if vals else 0
                result.append({group_key: k, val_key + "_" + agg: agg_val, "n": len(vals)})
            return result

        def stats_bin(i, a):
            d = self._clean_list(a[0]); n_bins = int(a[1]) if len(a) > 1 else 5
            if not d: return []
            min_v, max_v = min(d), max(d)
            width = (max_v - min_v) / n_bins if n_bins > 0 else 1
            bins = []
            for v in d:
                b = int((v - min_v) / width) if width > 0 else 0
                if b >= n_bins: b = n_bins - 1
                low = min_v + b * width; high = low + width
                bins.append(f"{low:.2f}-{high:.2f}")
            return bins

        def stats_report(i, a):
            results = a[0]
            if not isinstance(results, dict): return str(results)
            lines = ["=" * 50, "  STATISTICAL ANALYSIS REPORT", "=" * 50]
            for key, val in results.items():
                if isinstance(val, float): lines.append(f"  {key:<20}: {val:.4f}")
                elif isinstance(val, (list, dict)): lines.append(f"  {key:<20}: {str(val)}")
                else: lines.append(f"  {key:<20}: {val}")
            if "significant" in results:
                lines.append(""); lines.append(f"  >> {'SIGNIFICANT (p < 0.05)' if results['significant'] else 'NOT SIGNIFICANT (p >= 0.05)'}")
            lines.append("=" * 50)
            return "\n".join(lines)

        env.define("STATS_MODE", NativeFunction("STATS_MODE", 1, stats_mode))
        env.define("STATS_PERCENTILE", NativeFunction("STATS_PERCENTILE", 2, stats_percentile))
        env.define("STATS_QUARTILES", NativeFunction("STATS_QUARTILES", 1, stats_quartiles))
        env.define("STATS_SKEWNESS", NativeFunction("STATS_SKEWNESS", 1, stats_skewness))
        env.define("STATS_KURTOSIS", NativeFunction("STATS_KURTOSIS", 1, stats_kurtosis))
        env.define("STATS_FREQUENCY", NativeFunction("STATS_FREQUENCY", 1, stats_frequency))
        env.define("STATS_CROSSTAB", NativeFunction("STATS_CROSSTAB", 2, stats_crosstab))
        env.define("STATS_TTEST_1SAMPLE", NativeFunction("STATS_TTEST_1SAMPLE", 2, stats_ttest_1sample))
        env.define("STATS_TTEST_IND", NativeFunction("STATS_TTEST_IND", -1, stats_ttest_ind))
        env.define("STATS_TTEST_PAIRED", NativeFunction("STATS_TTEST_PAIRED", 2, stats_ttest_paired))
        env.define("STATS_ANOVA", NativeFunction("STATS_ANOVA", -1, stats_anova))
        env.define("STATS_CHISQUARE", NativeFunction("STATS_CHISQUARE", -1, stats_chisquare))
        env.define("STATS_CHISQUARE_INDEP", NativeFunction("STATS_CHISQUARE_INDEP", 2, stats_chisquare_indep))
        env.define("STATS_CORRELATION", NativeFunction("STATS_CORRELATION", 2, stats_correlation))
        env.define("STATS_SPEARMAN", NativeFunction("STATS_SPEARMAN", 2, stats_spearman))
        env.define("STATS_REGRESSION", NativeFunction("STATS_REGRESSION", 2, stats_regression))
        env.define("STATS_MANNWHITNEY", NativeFunction("STATS_MANNWHITNEY", 2, stats_mannwhitney))
        env.define("STATS_WILCOXON", NativeFunction("STATS_WILCOXON", 2, stats_wilcoxon))
        env.define("STATS_KRUSKAL", NativeFunction("STATS_KRUSKAL", -1, stats_kruskal))
        env.define("STATS_ZSCORE", NativeFunction("STATS_ZSCORE", 1, stats_zscore))
        env.define("STATS_CLEAN", NativeFunction("STATS_CLEAN", 1, stats_clean))
        env.define("STATS_RECODE", NativeFunction("STATS_RECODE", 2, stats_recode))
        env.define("STATS_GROUP_BY", NativeFunction("STATS_GROUP_BY", -1, stats_group_by))
        env.define("STATS_BIN", NativeFunction("STATS_BIN", -1, stats_bin))
        env.define("STATS_REPORT", NativeFunction("STATS_REPORT", 1, stats_report))