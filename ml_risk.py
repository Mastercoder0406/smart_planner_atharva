"""
ml_risk.py  -  Edge-aware obstacle-risk model for Smart Planner.

WHY THIS EXISTS
The old risk model used only time features, so every edge got the SAME multiplier.
Multiplying every edge by the same number never changes which route A* picks.
This model predicts risk PER EDGE from:
    hour, day_of_week, is_rush_hour, is_weekend      (time)
    road_class      0=footway/path ... 4=primary/trunk/motorway   (from OSM highway tag)
    nearby_reports  community obstacle reports within 150 m (0..3)
    rush_x_road     rush hour x road class (busy roads clog at rush hour)
so footways and busy roads really get different penalties at different times.

SPEED: sklearn is called ONCE per request/hour for all (road_class, nearby) combinations;
A* then does an O(1) dictionary lookup per edge.
"""
import os
import math
from datetime import datetime

import joblib
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "obstacle_risk_model.pkl")

FEATURES = ["hour", "day_of_week", "is_rush_hour", "is_weekend",
            "road_class", "nearby_reports", "rush_x_road"]
MAX_NEARBY = 3
NEARBY_RADIUS_M = 150
ALPHA = {"comfortable": 1.0, "accessible": 1.5, "balanced": 1.2}   # penalty strength

ROAD_CLASS = {
    "footway": 0, "pedestrian": 0, "path": 0, "steps": 0, "cycleway": 0,
    "living_street": 1, "residential": 1, "service": 1, "unknown": 1,
    "unclassified": 2, "tertiary": 2,
    "secondary": 3,
    "primary": 4, "trunk": 4, "motorway": 4,
}


def road_class_of(highway):
    if isinstance(highway, list):
        highway = highway[0] if highway else "unknown"
    return ROAD_CLASS.get(highway, 1)


def is_rush(hour):
    return 1 if (7 <= hour <= 9 or 17 <= hour <= 19) else 0


def make_row(hour, dow, road_class, nearby):
    rush = is_rush(hour)
    return [hour, dow, rush, 1 if dow >= 5 else 0, road_class, nearby, rush * road_class]


def synthetic_probability(hour, dow, road_class, nearby):
    """Assumed ground truth used to GENERATE synthetic training labels and as a
    fallback when no trained model file exists. Replace with real data over time."""
    p = 0.04 + 0.015 * road_class
    if is_rush(hour):
        p += 0.04 + 0.05 * road_class          # busy roads clog at rush hour
    if dow >= 5 and 10 <= hour <= 16:
        p += 0.03                               # weekend crowds
    if hour >= 22 or hour <= 5:
        p -= 0.02                               # quiet at night
    p += 0.12 * min(nearby, MAX_NEARBY)         # community reports nearby
    return min(max(p, 0.01), 0.95)


def haversine_m(lat1, lng1, lat2, lng2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def count_nearby(lat, lng, obstacles, radius=NEARBY_RADIUS_M):
    n = 0
    for olat, olng in obstacles or []:
        if haversine_m(lat, lng, olat, olng) <= radius:
            n += 1
    return min(n, MAX_NEARBY)


def risk_level(p):
    return "Low" if p < 0.10 else ("Moderate" if p < 0.20 else "High")


class ObstacleRiskModel:
    def __init__(self, path=MODEL_PATH):
        self.path = path
        self.model = None
        self.metrics = {}
        self._key = None
        self._table = None
        self.load()

    def load(self):
        try:
            bundle = joblib.load(self.path)
            self.model = bundle["model"]
            self.metrics = bundle.get("metrics", {})
        except Exception:
            self.model = None
            self.metrics = {}

    @property
    def source(self):
        return "trained logistic regression" if self.model is not None else "rule-based prior (no model file)"

    def _table_for(self, now):
        key = (now.date(), now.hour)
        if key == self._key:
            return self._table
        combos = [(rc, nb) for rc in range(5) for nb in range(MAX_NEARBY + 1)]
        rows = [make_row(now.hour, now.weekday(), rc, nb) for rc, nb in combos]
        if self.model is not None:
            probs = self.model.predict_proba(pd.DataFrame(rows, columns=FEATURES))[:, 1]
        else:
            probs = [synthetic_probability(now.hour, now.weekday(), rc, nb) for rc, nb in combos]
        self._table = {c: float(p) for c, p in zip(combos, probs)}
        self._key = key
        return self._table

    def probability(self, highway, nearby=0, now=None):
        now = now or datetime.now()
        return self._table_for(now)[(road_class_of(highway), min(int(nearby), MAX_NEARBY))]

    def multiplier(self, highway, nearby=0, alpha=1.2, now=None):
        """P_risk(e) = 1 + alpha * Prob_ML(e)   (always >= 1.0)"""
        return 1.0 + alpha * self.probability(highway, nearby, now)

    def summary(self, now=None):
        now = now or datetime.now()
        t = self._table_for(now)
        base = t[(1, 0)]
        names = [("footway", 0), ("residential", 1), ("tertiary", 2), ("secondary", 3), ("primary", 4)]
        return {
            "time": now.strftime("%a %H:%M"),
            "is_rush_hour": bool(is_rush(now.hour)),
            "probability": round(base, 3),
            "level": risk_level(base),
            "by_road_type": {n: round(t[(rc, 0)], 3) for n, rc in names},
            "model_source": self.source,
            "metrics": self.metrics,
        }

    def route_risk(self, G, route, edge_getter, obstacles, now=None):
        """Length-weighted average and worst-case risk along a finished route."""
        now = now or datetime.now()
        total_len = weighted = worst = 0.0
        high = 0
        for u, v in zip(route[:-1], route[1:]):
            e = edge_getter(G, u, v)
            if not e:
                continue
            node = G.nodes[u]
            p = self.probability(e.get("highway_type", "unknown"),
                                 count_nearby(node["y"], node["x"], obstacles), now)
            length = e.get("length", 0) or 0
            total_len += length
            weighted += p * length
            worst = max(worst, p)
            high += 1 if p >= 0.20 else 0
        avg = weighted / total_len if total_len else 0.0
        return {"avg_probability": round(avg, 3), "max_probability": round(worst, 3),
                "level": risk_level(avg), "high_risk_segments": high}


RISK = ObstacleRiskModel()   # singleton used by app.py