"""
Integration topology model for TensorGuardFlow.

This module defines the data structures for representing the integration graph,
used for visualization, auditing, and diagnostics.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from tensorguard.integrations.framework.config_schema import (
    IntegrationCategory,
    CategoryName,
    NodeStatus,
    EdgeProtocol,
    EdgeStatus,
    EdgeDirection,
    EndpointType,
    EndpointProtocol,
    AuthMethod,
    ArtifactType,
    OverallHealth,
    CATEGORY_TO_NAME,
)


class EndpointUsage(BaseModel):
    """Endpoint usage details."""
    endpoint: str
    type: EndpointType
    protocol: Optional[EndpointProtocol] = None
    auth_method: Optional[AuthMethod] = None
    last_used: Optional[datetime] = None

    class Config:
        use_enum_values = True


class ArtifactInfo(BaseModel):
    """Information about generated artifacts."""
    name: str
    type: ArtifactType
    path: Optional[str] = None
    checksum: Optional[str] = None
    generated_at: Optional[datetime] = None

    class Config:
        use_enum_values = True


class IntegrationNode(BaseModel):
    """A node in the integration topology graph."""
    id: str = Field(..., pattern=r"^[a-z0-9-]+$")
    category: IntegrationCategory
    category_name: Optional[CategoryName] = None
    provider: str
    provider_display: Optional[str] = None
    status: NodeStatus = NodeStatus.UNKNOWN
    status_message: Optional[str] = None
    last_health_check: Optional[datetime] = None
    health_check_latency_ms: Optional[int] = Field(None, ge=0)
    capabilities: List[str] = []
    endpoints_used: List[EndpointUsage] = []
    artifacts_generated: List[ArtifactInfo] = []
    config_fingerprint: Optional[str] = None
    enabled: bool = True
    metadata: Dict[str, Any] = {}

    class Config:
        use_enum_values = True

    def __init__(self, **data):
        super().__init__(**data)
        # Auto-set category_name based on category if not provided
        if self.category_name is None:
            self.category_name = CATEGORY_TO_NAME.get(
                IntegrationCategory(self.category)
                if isinstance(self.category, str)
                else self.category
            )


class IntegrationEdge(BaseModel):
    """A connection between integration nodes."""
    from_node: str
    to_node: str
    protocol: EdgeProtocol
    direction: EdgeDirection = EdgeDirection.UNIDIRECTIONAL
    artifacts: List[str] = []
    data_types: List[str] = []
    status: EdgeStatus = EdgeStatus.ACTIVE
    last_transfer: Optional[datetime] = None
    notes: Optional[str] = None

    class Config:
        use_enum_values = True


class TopologySummary(BaseModel):
    """Aggregate summary of topology health."""
    total_nodes: int = Field(..., ge=0)
    nodes_by_status: Dict[str, int] = {}
    nodes_by_category: Dict[str, int] = {}
    total_edges: int = Field(..., ge=0)
    overall_health: OverallHealth = OverallHealth.HEALTHY
    capabilities: List[str] = []
    last_full_check: Optional[datetime] = None

    class Config:
        use_enum_values = True


class IntegrationTopology(BaseModel):
    """Complete integration topology for a tenant."""
    version: str = "1.0.0"
    tenant_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    nodes: List[IntegrationNode] = []
    edges: List[IntegrationEdge] = []
    summary: Optional[TopologySummary] = None

    class Config:
        use_enum_values = True

    def compute_summary(self) -> TopologySummary:
        """Compute summary from nodes and edges."""
        nodes_by_status: Dict[str, int] = {}
        nodes_by_category: Dict[str, int] = {}
        all_capabilities: Set[str] = set()

        for node in self.nodes:
            status_key = (
                node.status.value
                if isinstance(node.status, NodeStatus)
                else node.status
            )
            nodes_by_status[status_key] = nodes_by_status.get(status_key, 0) + 1

            category_key = (
                node.category.value
                if isinstance(node.category, IntegrationCategory)
                else node.category
            )
            nodes_by_category[category_key] = (
                nodes_by_category.get(category_key, 0) + 1
            )
            all_capabilities.update(node.capabilities)

        # Determine overall health
        fail_count = nodes_by_status.get("FAIL", 0)
        warn_count = nodes_by_status.get("WARN", 0)

        if fail_count > 0:
            overall_health = OverallHealth.UNHEALTHY
        elif warn_count > 0:
            overall_health = OverallHealth.DEGRADED
        else:
            overall_health = OverallHealth.HEALTHY

        return TopologySummary(
            total_nodes=len(self.nodes),
            nodes_by_status=nodes_by_status,
            nodes_by_category=nodes_by_category,
            total_edges=len(self.edges),
            overall_health=overall_health,
            capabilities=sorted(all_capabilities),
            last_full_check=self.timestamp,
        )

    def add_node(self, node: IntegrationNode) -> None:
        """Add a node to the topology."""
        # Check for duplicate ID
        existing_ids = {n.id for n in self.nodes}
        if node.id in existing_ids:
            raise ValueError(f"Node with ID '{node.id}' already exists")
        self.nodes.append(node)

    def add_edge(self, edge: IntegrationEdge) -> None:
        """Add an edge to the topology."""
        # Validate that endpoints exist
        node_ids = {n.id for n in self.nodes}
        if edge.from_node not in node_ids:
            raise ValueError(f"Source node '{edge.from_node}' not found")
        if edge.to_node not in node_ids:
            raise ValueError(f"Target node '{edge.to_node}' not found")
        self.edges.append(edge)

    def get_node(self, node_id: str) -> Optional[IntegrationNode]:
        """Get a node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_nodes_by_category(self, category: IntegrationCategory) -> List[IntegrationNode]:
        """Get all nodes in a category."""
        return [
            n
            for n in self.nodes
            if (
                n.category == category
                or n.category == category.value
            )
        ]

    def get_nodes_by_status(self, status: NodeStatus) -> List[IntegrationNode]:
        """Get all nodes with a specific status."""
        return [
            n
            for n in self.nodes
            if (n.status == status or n.status == status.value)
        ]

    def get_edges_from(self, node_id: str) -> List[IntegrationEdge]:
        """Get all edges originating from a node."""
        return [e for e in self.edges if e.from_node == node_id]

    def get_edges_to(self, node_id: str) -> List[IntegrationEdge]:
        """Get all edges pointing to a node."""
        return [e for e in self.edges if e.to_node == node_id]

    def update_node_status(
        self,
        node_id: str,
        status: NodeStatus,
        message: Optional[str] = None,
        latency_ms: Optional[int] = None,
    ) -> bool:
        """Update the status of a node."""
        node = self.get_node(node_id)
        if node is None:
            return False
        node.status = status
        node.status_message = message
        node.last_health_check = datetime.utcnow()
        if latency_ms is not None:
            node.health_check_latency_ms = latency_ms
        return True

    def validate(self) -> List[str]:
        """Validate the topology and return list of errors."""
        errors = []

        # Check for duplicate node IDs
        node_ids = [n.id for n in self.nodes]
        duplicates = set([x for x in node_ids if node_ids.count(x) > 1])
        if duplicates:
            errors.append(f"Duplicate node IDs: {duplicates}")

        # Check edge references
        node_id_set = set(node_ids)
        for edge in self.edges:
            if edge.from_node not in node_id_set:
                errors.append(f"Edge references unknown source node: {edge.from_node}")
            if edge.to_node not in node_id_set:
                errors.append(f"Edge references unknown target node: {edge.to_node}")

        # Check for at least one E category node (registry)
        e_nodes = self.get_nodes_by_category(IntegrationCategory.E)
        if len(e_nodes) == 0:
            errors.append("Topology must have at least one Category E (registry) node")

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        # Ensure summary is computed
        if self.summary is None:
            self.summary = self.compute_summary()

        return {
            "version": self.version,
            "tenant_id": self.tenant_id,
            "timestamp": self.timestamp.isoformat(),
            "nodes": [n.model_dump() for n in self.nodes],
            "edges": [e.model_dump() for e in self.edges],
            "summary": self.summary.model_dump() if self.summary else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IntegrationTopology":
        """Create topology from dictionary."""
        nodes = [IntegrationNode(**n) for n in data.get("nodes", [])]
        edges = [IntegrationEdge(**e) for e in data.get("edges", [])]
        summary = (
            TopologySummary(**data["summary"])
            if data.get("summary")
            else None
        )

        return cls(
            version=data.get("version", "1.0.0"),
            tenant_id=data["tenant_id"],
            timestamp=(
                datetime.fromisoformat(data["timestamp"])
                if isinstance(data.get("timestamp"), str)
                else data.get("timestamp", datetime.utcnow())
            ),
            nodes=nodes,
            edges=edges,
            summary=summary,
        )


class TopologyBuilder:
    """Builder for constructing integration topologies."""

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.nodes: List[IntegrationNode] = []
        self.edges: List[IntegrationEdge] = []

    def add_data_source(
        self,
        id: str,
        provider: str,
        provider_display: str,
        status: NodeStatus = NodeStatus.UNKNOWN,
        status_message: Optional[str] = None,
        capabilities: List[str] = None,
        **kwargs,
    ) -> "TopologyBuilder":
        """Add a data source node (Category C)."""
        self.nodes.append(
            IntegrationNode(
                id=id,
                category=IntegrationCategory.C,
                provider=provider,
                provider_display=provider_display,
                status=status,
                status_message=status_message,
                capabilities=capabilities or [],
                **kwargs,
            )
        )
        return self

    def add_training(
        self,
        id: str,
        provider: str,
        provider_display: str,
        status: NodeStatus = NodeStatus.UNKNOWN,
        status_message: Optional[str] = None,
        capabilities: List[str] = None,
        **kwargs,
    ) -> "TopologyBuilder":
        """Add a training execution node (Category D)."""
        self.nodes.append(
            IntegrationNode(
                id=id,
                category=IntegrationCategory.D,
                provider=provider,
                provider_display=provider_display,
                status=status,
                status_message=status_message,
                capabilities=capabilities or [],
                **kwargs,
            )
        )
        return self

    def add_registry(
        self,
        id: str = "tgf-registry",
        provider: str = "tgf_internal",
        provider_display: str = "TGF Internal Registry",
        status: NodeStatus = NodeStatus.OK,
        status_message: str = "Database connected",
        capabilities: List[str] = None,
        **kwargs,
    ) -> "TopologyBuilder":
        """Add the TGF internal registry node (Category E)."""
        default_capabilities = [
            "adapter_registry",
            "channel_management",
            "evidence_chain",
            "gate_evaluation",
            "tgsp_packaging",
        ]
        self.nodes.append(
            IntegrationNode(
                id=id,
                category=IntegrationCategory.E,
                provider=provider,
                provider_display=provider_display,
                status=status,
                status_message=status_message,
                capabilities=capabilities or default_capabilities,
                **kwargs,
            )
        )
        return self

    def add_tracking(
        self,
        id: str,
        provider: str,
        provider_display: str,
        status: NodeStatus = NodeStatus.UNKNOWN,
        status_message: Optional[str] = None,
        capabilities: List[str] = None,
        **kwargs,
    ) -> "TopologyBuilder":
        """Add a tracking/metrics sink node (Category E)."""
        self.nodes.append(
            IntegrationNode(
                id=id,
                category=IntegrationCategory.E,
                provider=provider,
                provider_display=provider_display,
                status=status,
                status_message=status_message,
                capabilities=capabilities or ["metrics_sink", "experiment_tracking"],
                **kwargs,
            )
        )
        return self

    def add_serving(
        self,
        id: str,
        provider: str,
        provider_display: str,
        status: NodeStatus = NodeStatus.UNKNOWN,
        status_message: Optional[str] = None,
        capabilities: List[str] = None,
        **kwargs,
    ) -> "TopologyBuilder":
        """Add a serving/inference node (Category F)."""
        self.nodes.append(
            IntegrationNode(
                id=id,
                category=IntegrationCategory.F,
                provider=provider,
                provider_display=provider_display,
                status=status,
                status_message=status_message,
                capabilities=capabilities or ["serving_pack_export", "resolve_integration"],
                **kwargs,
            )
        )
        return self

    def add_trust(
        self,
        id: str,
        provider: str,
        provider_display: str,
        status: NodeStatus = NodeStatus.UNKNOWN,
        status_message: Optional[str] = None,
        capabilities: List[str] = None,
        **kwargs,
    ) -> "TopologyBuilder":
        """Add a trust & privacy node (Category G)."""
        self.nodes.append(
            IntegrationNode(
                id=id,
                category=IntegrationCategory.G,
                provider=provider,
                provider_display=provider_display,
                status=status,
                status_message=status_message,
                capabilities=capabilities or ["sign", "verify"],
                **kwargs,
            )
        )
        return self

    def connect(
        self,
        from_node: str,
        to_node: str,
        protocol: EdgeProtocol,
        data_types: List[str] = None,
        artifacts: List[str] = None,
        notes: Optional[str] = None,
    ) -> "TopologyBuilder":
        """Add an edge between nodes."""
        self.edges.append(
            IntegrationEdge(
                from_node=from_node,
                to_node=to_node,
                protocol=protocol,
                data_types=data_types or [],
                artifacts=artifacts or [],
                notes=notes,
            )
        )
        return self

    def build(self) -> IntegrationTopology:
        """Build and return the topology."""
        topology = IntegrationTopology(
            tenant_id=self.tenant_id,
            timestamp=datetime.utcnow(),
            nodes=self.nodes,
            edges=self.edges,
        )
        topology.summary = topology.compute_summary()

        # Validate before returning
        errors = topology.validate()
        if errors:
            raise ValueError(f"Invalid topology: {errors}")

        return topology
