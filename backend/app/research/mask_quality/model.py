from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict

import numpy as np


@dataclass
class RuleBasedMaskQualityModel:
    research_only: bool = True

    def predict(self, rows: list[list[float]]) -> list[str]:
        predictions = []
        for row in rows:
            rectangularity = row[3] if len(row) > 3 else 0.0
            hole_ratio = row[9] if len(row) > 9 else 0.0
            components = row[10] if len(row) > 10 else 0.0
            lower_leg = row[7] if len(row) > 7 else 0.0
            if components > 1:
                predictions.append("fragmented")
            elif hole_ratio > 0.05:
                predictions.append("holey")
            elif rectangularity > 0.85:
                predictions.append("rectangular")
            elif lower_leg > 0.8:
                predictions.append("lower_leg_like")
            else:
                predictions.append("valid")
        return predictions


@dataclass
class CentroidMaskQualityModel:
    centroids: dict[str, list[float]]
    research_only: bool = True

    @classmethod
    def fit(cls, features: list[list[float]], labels: list[str]) -> "CentroidMaskQualityModel":
        grouped: dict[str, list[list[float]]] = defaultdict(list)
        for feature, label in zip(features, labels, strict=False):
            grouped[label].append(feature)
        centroids = {
            label: np.mean(np.asarray(rows, dtype=np.float32), axis=0).astype(float).tolist()
            for label, rows in grouped.items()
            if rows
        }
        return cls(centroids=centroids)

    def predict(self, rows: list[list[float]]) -> list[str]:
        if not self.centroids:
            return ["unknown" for _ in rows]
        labels = list(self.centroids)
        centroid_array = np.asarray([self.centroids[label] for label in labels], dtype=np.float32)
        predictions: list[str] = []
        for row in rows:
            vector = np.asarray(row, dtype=np.float32)
            distances = np.linalg.norm(centroid_array - vector, axis=1)
            predictions.append(labels[int(np.argmin(distances))])
        return predictions
