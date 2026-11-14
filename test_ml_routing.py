"""
test_ml_routing.py  -  Proof that ML risk now CHANGES the chosen route.
Run:  python test_ml_routing.py
Toy network: A -> B via a SHORT busy primary road (400 m) or a LONGER footway (460 m).
"""
from datetime import datetime
import networkx as nx
from ml_risk import RISK
from routing_costs import make_cost_function

G = nx.MultiDiGraph()
for n, (y, x) in {"A": (19.0, 73.0), "M1": (19.001, 73.0), "B": (19.002, 73.0), "M2": (19.001, 73.001)}.items():
    G.add_node(n, y=y, x=x)
E = {("A", "M1"): ("primary", 200), ("M1", "B"): ("primary", 200),
     ("A", "M2"): ("footway", 230), ("M2", "B"): ("footway", 230)}
for (u, v), (hw, ln) in E.items():
    G.add_edge(u, v, 0, length=ln, highway_type=hw, slope=0, surface="asphalt")
getter = lambda g, u, v: g.get_edge_data(u, v, 0)

def route_for(route_type, when):
    cost = make_cost_function(route_type, G, getter, {"weather": "Clear", "obstacles": [], "profile": {}, "now": when}, RISK)
    return nx.astar_path(G, "A", "B", weight=cost, heuristic=lambda u, v: 0)

rush = datetime(2026, 11, 16, 8, 30)    # Monday 08:30
night = datetime(2026, 11, 15, 3, 0)    # Sunday 03:00
print("Model source:", RISK.source)
for rt in ["fastest", "comfortable", "accessible"]:
    r1, r2 = route_for(rt, rush), route_for(rt, night)
    print(f"{rt:12s} rush hour -> {'footway' if 'M2' in r1 else 'primary road'} | 3 AM -> {'footway' if 'M2' in r2 else 'primary road'}")
print("Primary-road risk  rush:", round(RISK.probability("primary", 0, rush), 3), " night:", round(RISK.probability("primary", 0, night), 3))
print("Footway risk       rush:", round(RISK.probability("footway", 0, rush), 3), " night:", round(RISK.probability("footway", 0, night), 3))