from .base_plugin import AnikaPlugin
from core.interpreter import NativeFunction
from core.errors import FMS_Error

class MLPlugin(AnikaPlugin):
    def _get_numpy(self):
        try:
            import numpy as np
            return np
        except ImportError:
            raise FMS_Error("ML requires numpy. Run: pip install numpy", error_type="Import Error")

    def _get_sklearn(self):
        try: import sklearn; return sklearn
        except ImportError:
            raise FMS_Error("ML requires scikit-learn. Run: pip install scikit-learn", error_type="Import Error")

    def _extract_features(self, data, feature_keys):
        np = self._get_numpy()
        if not isinstance(data, list) or len(data) == 0:
            raise FMS_Error("Data must be a non-empty list of dictionaries", error_type="ML Error")
        if not isinstance(feature_keys, list): feature_keys = [feature_keys]
        rows = []
        for row in data:
            try: rows.append([float(row[k]) for k in feature_keys])
            except (KeyError, ValueError, TypeError) as e:
                raise FMS_Error(f"Feature extraction failed: {str(e)}", error_type="ML Error")
        return np.array(rows)

    def _extract_target(self, data, target_key):
        np = self._get_numpy()
        return np.array([row.get(target_key) for row in data])

    def _train_classifier(self, model, data, feature_keys, target_key):
        np = self._get_numpy()
        X = self._extract_features(data, feature_keys)
        y = self._extract_target(data, target_key)
        model.fit(X, y)
        train_acc = float(model.score(X, y))
        return {"model": model, "train_accuracy": train_acc, "n_samples": len(data), "n_features": X.shape[1]}

    def register(self, env, interpreter):
        def ml_train_test_split(i, a):
            from sklearn.model_selection import train_test_split as sk_split
            data, feature_keys, target_key = a[0], a[1], str(a[2])
            test_size = float(a[3]) if len(a) > 3 else 0.2
            random_state = int(a[4]) if len(a) > 4 else 42
            X = self._extract_features(data, feature_keys); y = self._extract_target(data, target_key)
            X_train, X_test, y_train, y_test = sk_split(X, y, test_size=test_size, random_state=random_state)
            indices = list(range(len(data)))
            _, test_idx, _, _ = sk_split(indices, indices, test_size=test_size, random_state=random_state)
            train_data = [data[i] for i in range(len(data)) if i not in test_idx]
            test_data = [data[i] for i in test_idx]
            return {"train": train_data, "test": test_data, "X_train": X_train.tolist(), "X_test": X_test.tolist(), "y_train": y_train.tolist(), "y_test": y_test.tolist(), "train_size": len(train_data), "test_size": len(test_data)}

        def ml_standardize(i, a):
            from sklearn.preprocessing import StandardScaler
            np = self._get_numpy()
            data, feature_keys = a[0], a[1]
            X = self._extract_features(data, feature_keys)
            scaler = StandardScaler(); X_scaled = scaler.fit_transform(X)
            result = []
            for idx, row in enumerate(data):
                new_row = dict(row)
                for j, key in enumerate(feature_keys): new_row[key + "_scaled"] = float(X_scaled[idx][j])
                result.append(new_row)
            return {"data": result, "mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist()}

        def ml_label_encode(i, a):
            from sklearn.preprocessing import LabelEncoder
            data, key = a[0], str(a[1])
            le = LabelEncoder(); values = [row.get(key) for row in data]
            encoded = le.fit_transform(values).tolist()
            result = []
            for idx, row in enumerate(data):
                new_row = dict(row); new_row[key + "_encoded"] = encoded[idx]
                result.append(new_row)
            return {"data": result, "classes": le.classes_.tolist(), "mapping": {str(c): int(idx) for idx, c in enumerate(le.classes_)}}

        def ml_knn(i, a):
            from sklearn.neighbors import KNeighborsClassifier
            data, feature_keys, target_key = a[0], a[1], str(a[2])
            k = int(a[3]) if len(a) > 3 else 5
            model = KNeighborsClassifier(n_neighbors=k)
            result = self._train_classifier(model, data, feature_keys, target_key)
            result.update({"algorithm": "KNN", "k": k, "model_obj": model})
            return result

        def ml_decision_tree(i, a):
            from sklearn.tree import DecisionTreeClassifier
            data, feature_keys, target_key = a[0], a[1], str(a[2])
            max_depth = int(a[3]) if len(a) > 3 else None
            model = DecisionTreeClassifier(max_depth=max_depth, random_state=42)
            result = self._train_classifier(model, data, feature_keys, target_key)
            result.update({"algorithm": "Decision Tree", "max_depth": max_depth, "model_obj": model})
            return result

        def ml_random_forest(i, a):
            from sklearn.ensemble import RandomForestClassifier
            data, feature_keys, target_key = a[0], a[1], str(a[2])
            n_estimators = int(a[3]) if len(a) > 3 else 100
            model = RandomForestClassifier(n_estimators=n_estimators, random_state=42)
            result = self._train_classifier(model, data, feature_keys, target_key)
            if hasattr(model, 'feature_importances_'):
                result["feature_importances"] = {str(k): float(v) for k, v in zip(feature_keys, model.feature_importances_)}
            result.update({"algorithm": "Random Forest", "n_estimators": n_estimators, "model_obj": model})
            return result

        def ml_logistic(i, a):
            from sklearn.linear_model import LogisticRegression
            data, feature_keys, target_key = a[0], a[1], str(a[2])
            model = LogisticRegression(max_iter=1000, random_state=42)
            result = self._train_classifier(model, data, feature_keys, target_key)
            result.update({"algorithm": "Logistic Regression", "model_obj": model})
            return result

        def ml_svm(i, a):
            from sklearn.svm import SVC
            data, feature_keys, target_key = a[0], a[1], str(a[2])
            kernel = str(a[3]) if len(a) > 3 else "rbf"
            model = SVC(kernel=kernel, random_state=42)
            result = self._train_classifier(model, data, feature_keys, target_key)
            result.update({"algorithm": "SVM", "kernel": kernel, "model_obj": model})
            return result

        def ml_linear_regression(i, a):
            from sklearn.linear_model import LinearRegression
            data, feature_keys, target_key = a[0], a[1], str(a[2])
            X = self._extract_features(data, feature_keys); y = self._extract_target(data, target_key)
            model = LinearRegression(); model.fit(X, y); r2 = float(model.score(X, y))
            return {"algorithm": "Linear Regression", "r_squared": r2, "coefficients": {str(k): float(v) for k, v in zip(feature_keys, model.coef_)}, "intercept": float(model.intercept_), "train_score": r2, "n_samples": len(data), "model_obj": model}

        def ml_polynomial_regression(i, a):
            from sklearn.linear_model import LinearRegression
            from sklearn.preprocessing import PolynomialFeatures
            data, feature_keys, target_key = a[0], a[1], str(a[2])
            degree = int(a[3]) if len(a) > 3 else 2
            X = self._extract_features(data, feature_keys); y = self._extract_target(data, target_key)
            poly = PolynomialFeatures(degree=degree); X_poly = poly.fit_transform(X)
            model = LinearRegression(); model.fit(X_poly, y); r2 = float(model.score(X_poly, y))
            return {"algorithm": "Polynomial Regression", "degree": degree, "r_squared": r2, "intercept": float(model.intercept_), "n_coefficients": len(model.coef_), "train_score": r2, "model_obj": model, "poly_obj": poly}

        def ml_ridge(i, a):
            from sklearn.linear_model import Ridge
            data, feature_keys, target_key = a[0], a[1], str(a[2])
            alpha = float(a[3]) if len(a) > 3 else 1.0
            X = self._extract_features(data, feature_keys); y = self._extract_target(data, target_key)
            model = Ridge(alpha=alpha, random_state=42); model.fit(X, y); r2 = float(model.score(X, y))
            return {"algorithm": "Ridge Regression", "alpha": alpha, "r_squared": r2, "coefficients": {str(k): float(v) for k, v in zip(feature_keys, model.coef_)}, "intercept": float(model.intercept_), "model_obj": model}

        def ml_lasso(i, a):
            from sklearn.linear_model import Lasso
            data, feature_keys, target_key = a[0], a[1], str(a[2])
            alpha = float(a[3]) if len(a) > 3 else 1.0
            X = self._extract_features(data, feature_keys); y = self._extract_target(data, target_key)
            model = Lasso(alpha=alpha, random_state=42); model.fit(X, y); r2 = float(model.score(X, y))
            return {"algorithm": "Lasso Regression", "alpha": alpha, "r_squared": r2, "coefficients": {str(k): float(v) for k, v in zip(feature_keys, model.coef_)}, "intercept": float(model.intercept_), "model_obj": model}

        def ml_kmeans(i, a):
            from sklearn.cluster import KMeans
            data, feature_keys = a[0], a[1]
            n_clusters = int(a[2]) if len(a) > 2 else 3
            X = self._extract_features(data, feature_keys)
            model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels = model.fit_predict(X).tolist()
            result = []
            for idx, row in enumerate(data):
                new_row = dict(row); new_row["cluster"] = labels[idx]; result.append(new_row)
            return {"data": result, "labels": labels, "n_clusters": n_clusters, "centers": model.cluster_centers_.tolist(), "inertia": float(model.inertia_), "algorithm": "K-Means"}

        def ml_dbscan(i, a):
            from sklearn.cluster import DBSCAN
            data, feature_keys = a[0], a[1]
            eps = float(a[2]) if len(a) > 2 else 0.5; min_samples = int(a[3]) if len(a) > 3 else 5
            X = self._extract_features(data, feature_keys)
            model = DBSCAN(eps=eps, min_samples=min_samples)
            labels = model.fit_predict(X).tolist()
            result = []
            for idx, row in enumerate(data):
                new_row = dict(row); new_row["cluster"] = labels[idx]; result.append(new_row)
            n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
            return {"data": result, "labels": labels, "n_clusters": n_clusters, "n_noise": labels.count(-1), "algorithm": "DBSCAN"}

        def ml_pca(i, a):
            from sklearn.decomposition import PCA
            data, feature_keys = a[0], a[1]
            n_components = int(a[2]) if len(a) > 2 else 2
            X = self._extract_features(data, feature_keys)
            pca = PCA(n_components=n_components); X_pca = pca.fit_transform(X)
            result = []
            for idx, row in enumerate(data):
                new_row = dict(row)
                for j in range(n_components): new_row[f"PC{j+1}"] = float(X_pca[idx][j])
                result.append(new_row)
            return {"data": result, "explained_variance_ratio": pca.explained_variance_ratio_.tolist(), "total_variance_explained": float(sum(pca.explained_variance_ratio_)), "n_components": n_components, "algorithm": "PCA"}

        def ml_predict(i, a):
            model_result, data, feature_keys = a[0], a[1], a[2]
            model = model_result.get("model_obj")
            if model is None: raise FMS_Error("ml_predict requires a trained model with model_obj", error_type="ML Error")
            X = self._extract_features(data, feature_keys)
            preds = model.predict(X).tolist()
            result = []
            for idx, row in enumerate(data):
                new_row = dict(row); new_row["prediction"] = preds[idx]; result.append(new_row)
            return result

        def ml_accuracy(i, a):
            from sklearn.metrics import accuracy_score
            return float(accuracy_score(a[0], a[1]))
        def ml_confusion_matrix(i, a):
            from sklearn.metrics import confusion_matrix
            cm = confusion_matrix(a[0], a[1]).tolist()
            return {"matrix": cm, "shape": [len(cm), len(cm[0]) if cm else 0]}
        def ml_classification_report(i, a):
            from sklearn.metrics import classification_report
            return classification_report(a[0], a[1], output_dict=True)
        def ml_r2_score(i, a):
            from sklearn.metrics import r2_score
            return float(r2_score(a[0], a[1]))
        def ml_mean_squared_error(i, a):
            from sklearn.metrics import mean_squared_error
            return float(mean_squared_error(a[0], a[1]))
        def ml_mean_absolute_error(i, a):
            from sklearn.metrics import mean_absolute_error
            return float(mean_absolute_error(a[0], a[1]))

        env.define("ML_TRAIN_TEST_SPLIT", NativeFunction("ML_TRAIN_TEST_SPLIT", -1, ml_train_test_split))
        env.define("ML_STANDARDIZE", NativeFunction("ML_STANDARDIZE", 2, ml_standardize))
        env.define("ML_LABEL_ENCODE", NativeFunction("ML_LABEL_ENCODE", 2, ml_label_encode))
        env.define("ML_KNN", NativeFunction("ML_KNN", -1, ml_knn))
        env.define("ML_DECISION_TREE", NativeFunction("ML_DECISION_TREE", -1, ml_decision_tree))
        env.define("ML_RANDOM_FOREST", NativeFunction("ML_RANDOM_FOREST", -1, ml_random_forest))
        env.define("ML_LOGISTIC", NativeFunction("ML_LOGISTIC", 3, ml_logistic))
        env.define("ML_SVM", NativeFunction("ML_SVM", -1, ml_svm))
        env.define("ML_LINEAR_REGRESSION", NativeFunction("ML_LINEAR_REGRESSION", 3, ml_linear_regression))
        env.define("ML_POLYNOMIAL_REGRESSION", NativeFunction("ML_POLYNOMIAL_REGRESSION", -1, ml_polynomial_regression))
        env.define("ML_RIDGE", NativeFunction("ML_RIDGE", -1, ml_ridge))
        env.define("ML_LASSO", NativeFunction("ML_LASSO", -1, ml_lasso))
        env.define("ML_KMEANS", NativeFunction("ML_KMEANS", -1, ml_kmeans))
        env.define("ML_DBSCAN", NativeFunction("ML_DBSCAN", -1, ml_dbscan))
        env.define("ML_PCA", NativeFunction("ML_PCA", -1, ml_pca))
        env.define("ML_PREDICT", NativeFunction("ML_PREDICT", 3, ml_predict))
        env.define("ML_ACCURACY", NativeFunction("ML_ACCURACY", 2, ml_accuracy))
        env.define("ML_CONFUSION_MATRIX", NativeFunction("ML_CONFUSION_MATRIX", 2, ml_confusion_matrix))
        env.define("ML_CLASSIFICATION_REPORT", NativeFunction("ML_CLASSIFICATION_REPORT", 2, ml_classification_report))
        env.define("ML_R2_SCORE", NativeFunction("ML_R2_SCORE", 2, ml_r2_score))
        env.define("ML_MSE", NativeFunction("ML_MSE", 2, ml_mean_squared_error))
        env.define("ML_MAE", NativeFunction("ML_MAE", 2, ml_mean_absolute_error))