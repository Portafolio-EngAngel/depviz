from pydantic import BaseModel


class Node(BaseModel):
    id: str           # package name (unique identifier)
    label: str        # display name
    ecosystem: str    # "npm" | "pip" | "internal"
    package_count: int  # how many packages depend on this (in-degree)


class Edge(BaseModel):
    source: str
    target: str
    is_circular: bool = False


class GraphResult(BaseModel):
    nodes: list[Node]
    edges: list[Edge]
    circular_deps: list[list[str]]  # each inner list is one cycle
    stats: dict  # total_packages, total_edges, circular_count, max_depth
