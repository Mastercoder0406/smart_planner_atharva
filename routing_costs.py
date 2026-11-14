"""
routing_costs.py  -  Edge-cost functions for the four route types.
Each function is passed to nx.astar_path(weight=...). ML risk (ml_risk.py) is applied
inside 'comfortable', 'accessible' and 'balanced'. 'fastest' stays pure distance on purpose.

HEURISTIC_SCALE: A* needs h(n) <= true remaining cost. In fastest / comfortable / accessible
every multiplier is >= 1.0, so straight-line distance is admissible as is. In 'balanced' the
footway benefit is 0.8, so the heuristic is scaled by n_min = 0.8 (as in the IEEE paper).
"""
import json
from datetime import datetime

from ml_risk import ALPHA, count_nearby, haversine_m

HEURISTIC_SCALE = {"balanced": 0.8}

PATH_PENALTY = {"footway": 0.8, "pedestrian": 0.8, "path": 0.9, "residential": 1.2,
                "living_street": 1.1, "primary": 2.0, "secondary": 1.7, "tertiary": 1.4,
                "motorway": 5.0, "trunk": 4.0, "unknown": 1.0}
WEATHER_PENALTY = {"Rain": {"gravel": 3.0, "concrete": 1.3, "asphalt": 1.1},
                   "Snow": {"gravel": 5.0, "concrete": 2.5, "asphalt": 1.8},
                   "Clear": {"gravel": 1.0, "concrete": 1.0, "asphalt": 1.0}}
INF = float("inf")


def make_cost_function(route_type, G, edge_getter, ctx, risk):
    weather = ctx.get("weather", "Unknown")
    obstacles = ctx.get("obstacles") or []
    profile = ctx.get("profile") or {}
    now = ctx.get("now") or datetime.now()
    nearby_cache, mind_cache = {}, {}

    def nearby(u):
        if u not in nearby_cache:
            n = G.nodes[u]
            nearby_cache[u] = count_nearby(n["y"], n["x"], obstacles)
        return nearby_cache[u]

    def min_obstacle_dist(u):
        if u not in mind_cache:
            n = G.nodes[u]
            mind_cache[u] = min((haversine_m(n["y"], n["x"], a, b) for a, b in obstacles), default=INF)
        return mind_cache[u]

    def edge(u, v):
        e = edge_getter(G, u, v)
        if not e or e.get("is_train_line", False):
            return None
        return e

    def risk_mult(e, u, route_type_):
        return risk.multiplier(e.get("highway_type", "unknown"), nearby(u), ALPHA[route_type_], now)

    def fastest(u, v, d):
        e = edge(u, v)
        if e is None:
            return INF
        cost = e.get("length", 0)
        if e.get("surface", "asphalt") == "gravel":
            cost *= 1.15
        return cost

    def comfortable(u, v, d):
        e = edge(u, v)
        if e is None:
            return INF
        cost = e.get("length", 0)
        slope = e.get("slope", 0)
        cost *= 3.0 if slope > 8 else 2.0 if slope > 5 else 1.35 if slope > 3 else 1.0
        surface = e.get("surface", "asphalt")
        cost *= 2.0 if surface == "gravel" else 1.15 if surface == "concrete" else 1.0
        if weather == "Rain" and surface == "gravel":
            cost *= 2.5
        if min_obstacle_dist(u) < 40:
            cost *= 2.5
        return cost * risk_mult(e, u, "comfortable")              # <-- ML risk

    def accessible(u, v, d):
        e = edge(u, v)
        if e is None or min_obstacle_dist(u) < 40:
            return INF
        cost = e.get("length", 0)
        slope = e.get("slope", 0)
        cost *= 6.0 if slope > 10 else 3.5 if slope > 5 else 1.8 if slope > 3 else 1.0
        surface = e.get("surface", "asphalt")
        cost *= 3.5 if surface == "gravel" else 1.3 if surface == "concrete" else 1.0
        if weather == "Rain":
            cost *= 1.4
        return cost * risk_mult(e, u, "accessible")               # <-- ML risk

    def balanced(u, v, d):
        e = edge(u, v)
        if e is None or min_obstacle_dist(u) < 40:
            return INF
        cost = e.get("length", 0) * risk_mult(e, u, "balanced")    # <-- ML risk
        cost *= PATH_PENALTY.get(e.get("highway_type", "unknown"), 1.0)
        surface = e.get("surface", "asphalt")
        cost *= WEATHER_PENALTY.get(weather, WEATHER_PENALTY["Clear"]).get(surface, 1.0)
        slope = e.get("slope", 0)
        max_slope = profile.get("max_slope", 6)
        cost *= (4.0 + (slope - max_slope) * 0.5) if slope > max_slope else (1 + slope / 12)
        disliked = profile.get("disliked_surfaces", [])
        if isinstance(disliked, str):
            try:
                disliked = json.loads(disliked)
            except Exception:
                disliked = []
        if surface in disliked:
            cost *= 2.0
        cost *= 1 + profile.get("comfort_weight", 0.5) * slope / 8
        return cost

    return {"fastest": fastest, "comfortable": comfortable,
            "accessible": accessible}.get(route_type, balanced)