from .base_plugin import AnikaPlugin
from core.interpreter import NativeFunction
from core.errors import FMS_Error

class GraphsPlugin(AnikaPlugin):
    def _get_matplotlib(self):
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            return plt
        except ImportError:
            raise FMS_Error("Graphs require matplotlib. Run: pip install matplotlib", error_type="Import Error")

    def _get_numpy(self):
        try:
            import numpy as np
            return np
        except ImportError:
            raise FMS_Error("Graphs require numpy. Run: pip install numpy", error_type="Import Error")

    def register(self, env, interpreter):
        # Global state for the current graph
        self._graph_state = {"fig": None, "ax": None}

        def graph_line(i, a):
            plt = self._get_matplotlib()
            x, y = a[0], a[1]
            title = str(a[2]) if len(a) > 2 else "Line Chart"
            xlabel = str(a[3]) if len(a) > 3 else ""
            ylabel = str(a[4]) if len(a) > 4 else ""
            color = str(a[5]) if len(a) > 5 else "#007acc"
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.plot(x, y, color=color, linewidth=2, marker='o', markersize=4)
            ax.set_title(title, fontsize=14, fontweight='bold')
            if xlabel: ax.set_xlabel(xlabel)
            if ylabel: ax.set_ylabel(ylabel)
            ax.grid(True, alpha=0.3); fig.tight_layout()
            self._graph_state["fig"] = fig; self._graph_state["ax"] = ax
            return "SUCCESS"

        def graph_save(i, a):
            plt = self._get_matplotlib()
            path = str(a[0]); dpi = int(a[1]) if len(a) > 1 else 150
            if self._graph_state["fig"] is None: raise FMS_Error("No graph to save. Create a graph first.", error_type="Graph Error")
            try:
                import os
                os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
                self._graph_state["fig"].savefig(path, dpi=dpi, bbox_inches='tight')
                return "SUCCESS"
            except Exception as e: raise FMS_Error(f"Failed to save graph: {str(e)}", error_type="Graph Error")

        def graph_show(i, a):
            plt = self._get_matplotlib()
            if self._graph_state["fig"] is None: raise FMS_Error("No graph to show. Create a graph first.", error_type="Graph Error")
            plt.show(); return "SUCCESS"

        def graph_close(i, a):
            plt = self._get_matplotlib()
            if self._graph_state["fig"] is not None: plt.close(self._graph_state["fig"])
            self._graph_state["fig"] = None; self._graph_state["ax"] = None
            return None

        def graph_bar(i, a):
            plt = self._get_matplotlib()
            labels, values = a[0], a[1]
            title = str(a[2]) if len(a) > 2 else "Bar Chart"
            xlabel = str(a[3]) if len(a) > 3 else ""; ylabel = str(a[4]) if len(a) > 4 else ""
            color = str(a[5]) if len(a) > 5 else "#27ae60"
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.bar(labels, values, color=color)
            ax.set_title(title, fontsize=14, fontweight='bold')
            if xlabel: ax.set_xlabel(xlabel)
            if ylabel: ax.set_ylabel(ylabel)
            ax.grid(True, axis='y', alpha=0.3); plt.xticks(rotation=45, ha='right'); fig.tight_layout()
            self._graph_state["fig"] = fig; self._graph_state["ax"] = ax
            return "SUCCESS"

        def graph_scatter(i, a):
            plt = self._get_matplotlib()
            x, y = a[0], a[1]
            title = str(a[2]) if len(a) > 2 else "Scatter Plot"
            xlabel = str(a[3]) if len(a) > 3 else ""; ylabel = str(a[4]) if len(a) > 4 else ""
            color = str(a[5]) if len(a) > 5 else "#e74c3c"
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.scatter(x, y, color=color, alpha=0.7, s=50)
            ax.set_title(title, fontsize=14, fontweight='bold')
            if xlabel: ax.set_xlabel(xlabel)
            if ylabel: ax.set_ylabel(ylabel)
            ax.grid(True, alpha=0.3); fig.tight_layout()
            self._graph_state["fig"] = fig; self._graph_state["ax"] = ax
            return "SUCCESS"

        def graph_histogram(i, a):
            plt = self._get_matplotlib()
            data = a[0]; bins = int(a[1]) if len(a) > 1 else 10
            title = str(a[2]) if len(a) > 2 else "Histogram"
            xlabel = str(a[3]) if len(a) > 3 else ""; ylabel = str(a[4]) if len(a) > 4 else "Frequency"
            color = str(a[5]) if len(a) > 5 else "#8e44ad"
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.hist(data, bins=bins, color=color, edgecolor='black', alpha=0.7)
            ax.set_title(title, fontsize=14, fontweight='bold')
            if xlabel: ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel); ax.grid(True, axis='y', alpha=0.3); fig.tight_layout()
            self._graph_state["fig"] = fig; self._graph_state["ax"] = ax
            return "SUCCESS"

        def graph_pie(i, a):
            plt = self._get_matplotlib()
            labels, values = a[0], a[1]
            title = str(a[2]) if len(a) > 2 else "Pie Chart"
            colors = a[3] if len(a) > 3 else None
            fig, ax = plt.subplots(figsize=(8, 8))
            ax.pie(values, labels=labels, autopct='%1.1f%%', colors=colors, startangle=90)
            ax.set_title(title, fontsize=14, fontweight='bold'); fig.tight_layout()
            self._graph_state["fig"] = fig; self._graph_state["ax"] = ax
            return "SUCCESS"

        def graph_box(i, a):
            plt = self._get_matplotlib()
            data_groups = a[0]; labels = a[1] if len(a) > 1 else None
            title = str(a[2]) if len(a) > 2 else "Box Plot"
            fig, ax = plt.subplots(figsize=(10, 6))
            bp = ax.boxplot(data_groups, patch_artist=True)
            if labels is not None: ax.set_xticklabels(labels)
            colors = ['#3498db', '#e74c3c', '#27ae60', '#f39c12', '#8e44ad', '#16a085']
            for patch, color in zip(bp['boxes'], colors * 10):
                patch.set_facecolor(color); patch.set_alpha(0.7)
            ax.set_title(title, fontsize=14, fontweight='bold'); ax.grid(True, axis='y', alpha=0.3); fig.tight_layout()
            self._graph_state["fig"] = fig; self._graph_state["ax"] = ax
            return "SUCCESS"

        def graph_heatmap(i, a):
            plt = self._get_matplotlib(); np = self._get_numpy()
            matrix = a[0]
            title = str(a[1]) if len(a) > 1 else "Heatmap"
            xlabel = str(a[2]) if len(a) > 2 else ""; ylabel = str(a[3]) if len(a) > 3 else ""
            fig, ax = plt.subplots(figsize=(10, 8))
            im = ax.imshow(matrix, cmap='viridis', aspect='auto'); fig.colorbar(im, ax=ax)
            ax.set_title(title, fontsize=14, fontweight='bold')
            if xlabel: ax.set_xlabel(xlabel)
            if ylabel: ax.set_ylabel(ylabel)
            for i in range(len(matrix)):
                for j in range(len(matrix[0])):
                    ax.text(j, i, f'{matrix[i][j]:.2f}', ha='center', va='center', color='white' if matrix[i][j] < (max(max(row) for row in matrix) / 2) else 'black')
            fig.tight_layout()
            self._graph_state["fig"] = fig; self._graph_state["ax"] = ax
            return "SUCCESS"

        def graph_multi_line(i, a):
            plt = self._get_matplotlib()
            x = a[0]; series = a[1]
            title = str(a[2]) if len(a) > 2 else "Multi-Line Chart"
            xlabel = str(a[3]) if len(a) > 3 else ""; ylabel = str(a[4]) if len(a) > 4 else ""
            fig, ax = plt.subplots(figsize=(10, 6))
            colors = ['#3498db', '#e74c3c', '#27ae60', '#f39c12', '#8e44ad', '#16a085', '#d35400']
            for idx, (label, y) in enumerate(series.items()):
                ax.plot(x, y, label=str(label), color=colors[idx % len(colors)], linewidth=2, marker='o', markersize=4)
            ax.set_title(title, fontsize=14, fontweight='bold')
            if xlabel: ax.set_xlabel(xlabel)
            if ylabel: ax.set_ylabel(ylabel)
            ax.legend(); ax.grid(True, alpha=0.3); fig.tight_layout()
            self._graph_state["fig"] = fig; self._graph_state["ax"] = ax
            return "SUCCESS"

        def graph_regression_line(i, a):
            plt = self._get_matplotlib(); np = self._get_numpy()
            x, y = a[0], a[1]
            title = str(a[2]) if len(a) > 2 else "Regression Plot"
            xlabel = str(a[3]) if len(a) > 3 else ""; ylabel = str(a[4]) if len(a) > 4 else ""
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.scatter(x, y, color='#3498db', alpha=0.7, s=50, label='Data')
            z = np.polyfit(x, y, 1); p = np.poly1d(z)
            x_line = np.linspace(min(x), max(x), 100)
            ax.plot(x_line, p(x_line), color='#e74c3c', linewidth=2, label=f'y = {z[0]:.2f}x + {z[1]:.2f}')
            ax.set_title(title, fontsize=14, fontweight='bold')
            if xlabel: ax.set_xlabel(xlabel)
            if ylabel: ax.set_ylabel(ylabel)
            ax.legend(); ax.grid(True, alpha=0.3); fig.tight_layout()
            self._graph_state["fig"] = fig; self._graph_state["ax"] = ax
            return "SUCCESS"

        env.define("GRAPH_LINE", NativeFunction("GRAPH_LINE", -1, graph_line))
        env.define("GRAPH_SAVE", NativeFunction("GRAPH_SAVE", -1, graph_save))
        env.define("GRAPH_SHOW", NativeFunction("GRAPH_SHOW", 0, graph_show))
        env.define("GRAPH_CLOSE", NativeFunction("GRAPH_CLOSE", 0, graph_close))
        env.define("GRAPH_BAR", NativeFunction("GRAPH_BAR", -1, graph_bar))
        env.define("GRAPH_SCATTER", NativeFunction("GRAPH_SCATTER", -1, graph_scatter))
        env.define("GRAPH_HISTOGRAM", NativeFunction("GRAPH_HISTOGRAM", -1, graph_histogram))
        env.define("GRAPH_PIE", NativeFunction("GRAPH_PIE", -1, graph_pie))
        env.define("GRAPH_BOX", NativeFunction("GRAPH_BOX", -1, graph_box))
        env.define("GRAPH_HEATMAP", NativeFunction("GRAPH_HEATMAP", -1, graph_heatmap))
        env.define("GRAPH_MULTI_LINE", NativeFunction("GRAPH_MULTI_LINE", -1, graph_multi_line))
        env.define("GRAPH_REGRESSION_LINE", NativeFunction("GRAPH_REGRESSION_LINE", -1, graph_regression_line))