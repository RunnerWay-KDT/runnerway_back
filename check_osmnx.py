import osmnx as ox
print(f"OSMnx version: {ox.__version__}")
try:
    print(f"ox.graph_from_point exists: {hasattr(ox, 'graph_from_point')}")
    print(f"ox.graph.graph_from_point exists: {hasattr(ox.graph, 'graph_from_point')}")
except Exception as e:
    print(f"Error checking attributes: {e}")
