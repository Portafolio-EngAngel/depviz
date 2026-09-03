import networkx as nx

from app.schemas.graph import GraphResult, Node, Edge


# Known pip package names used for ecosystem detection heuristic
_PIP_KNOWN = {
    "flask", "django", "fastapi", "sqlalchemy", "requests", "numpy", "pandas",
    "scipy", "pytest", "uvicorn", "pydantic", "celery", "redis", "boto3",
    "pillow", "aiohttp", "httpx", "starlette", "alembic", "click", "rich",
    "tensorflow", "torch", "sklearn", "scikit-learn", "matplotlib", "seaborn",
    "gunicorn", "python-dotenv", "mypy", "black", "flake8", "isort", "ruff",
}


def _get_ecosystem(name: str, dep_map: dict[str, list[str]]) -> str:
    """
    Determine the ecosystem of a node.

    Rules (in priority order):
    1. If the node owns its own dep list → it is an internal package.
    2. If the name is a well-known pip package → pip.
    3. If the name starts with '@' (npm scoped package) → npm.
    4. Default → npm (most common case for external deps).
    """
    if name in dep_map:
        return "internal"
    if name.lower() in _PIP_KNOWN:
        return "pip"
    if name.startswith("@"):
        return "npm"
    return "npm"


def build_graph(dep_map: dict[str, list[str]]) -> GraphResult:
    """
    Build a directed dependency graph from the parsed dep_map and compute
    graph analytics: circular dependencies, max depth, and node impact.

    Args:
        dep_map: {package_name: [direct_dependency_names, ...]}

    Returns:
        GraphResult with nodes, edges, circular_deps, and stats.
    """
    G: nx.DiGraph = nx.DiGraph()

    # Add all nodes explicitly so isolated packages appear in the graph
    for pkg in dep_map:
        G.add_node(pkg)

    # Add edges: pkg → dep means pkg depends on dep
    for pkg, deps in dep_map.items():
        for dep in deps:
            if pkg != dep:  # skip self-loops from malformed manifests
                G.add_edge(pkg, dep)

    # --- Cycle detection ---
    cycles: list[list[str]] = list(nx.simple_cycles(G))

    cycle_edge_set: set[tuple[str, str]] = set()
    for cycle in cycles:
        cycle_len = len(cycle)
        for i in range(cycle_len):
            cycle_edge_set.add((cycle[i], cycle[(i + 1) % cycle_len]))

    # --- Build node list ---
    nodes: list[Node] = []
    for node_id in G.nodes():
        in_degree = G.in_degree(node_id)  # number of packages that depend on this
        nodes.append(
            Node(
                id=node_id,
                label=node_id,
                ecosystem=_get_ecosystem(node_id, dep_map),
                package_count=in_degree,
            )
        )

    # --- Build edge list ---
    edges: list[Edge] = []
    for src, tgt in G.edges():
        edges.append(
            Edge(
                source=src,
                target=tgt,
                is_circular=(src, tgt) in cycle_edge_set,
            )
        )

    # --- Compute max depth (longest dependency chain) ---
    try:
        if nx.is_directed_acyclic_graph(G):
            max_depth = nx.dag_longest_path_length(G)
        else:
            # Graph has cycles — compute longest path on the condensation DAG
            condensation = nx.condensation(G)
            max_depth = nx.dag_longest_path_length(condensation)
    except Exception:
        max_depth = -1

    return GraphResult(
        nodes=nodes,
        edges=edges,
        circular_deps=cycles,
        stats={
            "total_packages": G.number_of_nodes(),
            "total_edges": G.number_of_edges(),
            "circular_count": len(cycles),
            "max_depth": max_depth,
        },
    )
