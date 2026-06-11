import hashlib
import uuid
import logging
from datetime import datetime
from app.db.neo4j import neo4j_db

logger = logging.getLogger(__name__)

def resolve_entity_id(entity_type: str, name: str, facility_id: str = "nexus-01") -> str:
    """Generate a deterministic UUID from SHA256 hash of entity properties."""
    base = f"{entity_type}:{name}:{facility_id}".lower()
    hash_val = hashlib.sha256(base.encode()).hexdigest()
    return str(uuid.UUID(hash_val[:32]))

class GraphService:
    @staticmethod
    async def upsert_equipment(entity: dict, facility_id: str = "nexus-01") -> str:
        """Upsert Equipment node into Neo4j."""
        driver = neo4j_db.driver
        if not driver:
            raise Exception("Neo4j not connected")
            
        name = entity.get("name", "Unknown Equipment")
        equipment_id = resolve_entity_id("equipment", name, facility_id)
        
        query = """
        MERGE (e:Equipment {id: $id})
        ON CREATE SET 
            e.name = $name,
            e.type = $type,
            e.facility_id = $facility_id,
            e.status = $status,
            e.created_at = datetime()
        ON MATCH SET
            e.updated_at = datetime()
        RETURN e.id AS id
        """
        
        async with driver.session() as session:
            result = await session.run(
                query, 
                id=equipment_id,
                name=name,
                type=entity.get("type", "unknown"),
                facility_id=facility_id,
                status=entity.get("status", "operational")
            )
            record = await result.single()
            return record["id"]

    @staticmethod
    async def upsert_failure(failure: dict, equipment_id: str) -> str:
        """Upsert Failure node and link to Equipment."""
        driver = neo4j_db.driver
        if not driver:
            raise Exception("Neo4j not connected")
            
        desc = failure.get("description", "Unknown Failure")
        failure_mode = failure.get("failure_mode", "unknown")
        failure_id = resolve_entity_id("failure", f"{equipment_id}:{failure_mode}:{desc}", "nexus-01")
        
        query = """
        MERGE (f:Failure {id: $id})
        ON CREATE SET
            f.description = $description,
            f.failure_mode = $failure_mode,
            f.severity = $severity,
            f.timestamp = datetime($timestamp)
        WITH f
        MATCH (e:Equipment {id: $eq_id})
        MERGE (e)-[r:EXPERIENCED]->(f)
        ON CREATE SET r.at = datetime($timestamp), r.count = 1
        ON MATCH SET r.count = r.count + 1
        RETURN f.id AS id
        """
        
        timestamp = failure.get("timestamp", datetime.utcnow().isoformat() + "Z")
        
        async with driver.session() as session:
            result = await session.run(
                query,
                id=failure_id,
                description=desc,
                failure_mode=failure_mode,
                severity=failure.get("severity", "medium"),
                timestamp=timestamp,
                eq_id=equipment_id
            )
            record = await result.single()
            return record["id"] if record else failure_id

    @staticmethod
    async def upsert_procedure(procedure: dict) -> str:
        """Upsert Procedure node."""
        driver = neo4j_db.driver
        if not driver:
            raise Exception("Neo4j not connected")
            
        code = procedure.get("code", "")
        title = procedure.get("title", "Unknown Procedure")
        proc_id = resolve_entity_id("procedure", f"{code}:{title}", "global")
        
        query = """
        MERGE (p:Procedure {id: $id})
        ON CREATE SET
            p.code = $code,
            p.title = $title,
            p.type = $type
        RETURN p.id AS id
        """
        
        async with driver.session() as session:
            result = await session.run(
                query,
                id=proc_id,
                code=code,
                title=title,
                type=procedure.get("type", "sop")
            )
            record = await result.single()
            return record["id"]

    @staticmethod
    async def link_failure_to_procedure(failure_id: str, procedure_id: str, success: bool = True):
        driver = neo4j_db.driver
        if not driver:
            raise Exception("Neo4j not connected")
            
        query = """
        MATCH (f:Failure {id: $f_id}), (p:Procedure {id: $p_id})
        MERGE (f)-[r:RESOLVED_BY]->(p)
        ON CREATE SET r.success = $success, r.attempts = 1
        ON MATCH SET r.attempts = r.attempts + 1
        """
        
        async with driver.session() as session:
            await session.run(query, f_id=failure_id, p_id=procedure_id, success=success)

    @staticmethod
    async def get_equipment_subgraph(equipment_id: str, depth: int = 2) -> dict:
        """Returns nodes and edges around a specific equipment."""
        driver = neo4j_db.driver
        if not driver:
            raise Exception("Neo4j not connected")
            
        # For simplicity in hackathon, depth=2 graph fetch. 
        query = """
        MATCH path = (e:Equipment {id: $id})-[*1..2]-(connected)
        WITH e, connected, path
        RETURN 
            [n IN nodes(path) | n] AS all_nodes,
            [r IN relationships(path) | r] AS all_edges
        """
        
        async with driver.session() as session:
            result = await session.run(query, id=equipment_id)
            records = await result.data()
            
            nodes_dict = {}
            edges_list = []
            seen_edges = set()
            
            for record in records:
                for n in record["all_nodes"]:
                    element_id = n.element_id
                    if element_id not in nodes_dict:
                        labels = list(n.labels)
                        nodes_dict[element_id] = {
                            "id": n.get("id", element_id),
                            "label": labels[0] if labels else "Unknown",
                            "properties": dict(n)
                        }
                for r in record["all_edges"]:
                    if r.element_id not in seen_edges:
                        seen_edges.add(r.element_id)
                        
                        # Handle Neo4j Node objects to extract their properties.
                        # r.nodes[0] returns a neo4j.graph.Node object which has 'element_id' and get('id')
                        nodes = list(r.nodes)
                        edges_list.append({
                            "id": r.element_id,
                            "type": r.type,
                            "source": nodes[0].get("id", nodes[0].element_id),
                            "target": nodes[1].get("id", nodes[1].element_id),
                            "properties": dict(r)
                        })
                        
            return {
                "nodes": list(nodes_dict.values()),
                "edges": edges_list
            }
            
    @staticmethod
    async def search_entities(query: str, type_filter: str = None) -> list:
        driver = neo4j_db.driver
        if not driver:
            raise Exception("Neo4j not connected")
            
        cypher = """
        MATCH (n)
        WHERE (toLower(n.name) CONTAINS toLower($q) OR toLower(n.title) CONTAINS toLower($q) OR toLower(n.description) CONTAINS toLower($q))
        """
        if type_filter and type_filter.lower() != "all":
            cypher += f" AND '{type_filter}' IN labels(n) "
            
        cypher += """
        RETURN n.id AS id, labels(n)[0] AS type, coalesce(n.name, n.title, n.description) AS display_name
        LIMIT 20
        """
        
        async with driver.session() as session:
            result = await session.run(cypher, q=query)
            return await result.data()
            
    @staticmethod
    async def get_stats() -> dict:
        driver = neo4j_db.driver
        if not driver:
            raise Exception("Neo4j not connected")
            
        query = """
        MATCH (e:Equipment) WITH count(e) AS equipment_count
        MATCH (f:Failure) WITH equipment_count, count(f) AS failure_count
        MATCH (p:Procedure) WITH equipment_count, failure_count, count(p) AS procedure_count
        MATCH ()-[r]->() WITH equipment_count, failure_count, procedure_count, count(r) AS relationship_count
        RETURN equipment_count, failure_count, procedure_count, relationship_count
        """
        
        async with driver.session() as session:
            result = await session.run(query)
            record = await result.single()
            if record:
                return dict(record)
            return {"equipment_count": 0, "failure_count": 0, "procedure_count": 0, "relationship_count": 0}

    @staticmethod
    async def get_copilot_context(entity_names: list) -> dict:
        """Fetches a rich contextual subgraph for given entity names to augment LLM prompts."""
        driver = neo4j_db.driver
        if not driver:
            return {"nodes": [], "edges": []}
            
        if not entity_names:
            return {"nodes": [], "edges": []}

        # Normalize names for case-insensitive CONTAINS
        names = [n.lower() for n in entity_names]
        
        # We find Equipment nodes that match the extracted names and pull 2-hops
        query = """
        UNWIND $names AS name
        MATCH (e:Equipment)
        WHERE toLower(e.name) CONTAINS name OR toLower(e.type) CONTAINS name
        OPTIONAL MATCH path = (e)-[*1..2]-(connected)
        RETURN 
            e.id AS root_id,
            e.name AS root_name,
            [n IN nodes(path) | n] AS all_nodes,
            [r IN relationships(path) | r] AS all_edges
        LIMIT 50
        """
        
        async with driver.session() as session:
            result = await session.run(query, names=names)
            records = await result.data()
            
            nodes_dict = {}
            edges_list = []
            seen_edges = set()
            
            for record in records:
                # Always add the root equipment even if path is null
                if "all_nodes" in record and record["all_nodes"]:
                    for n in record["all_nodes"]:
                        element_id = n.element_id
                        if element_id not in nodes_dict:
                            labels = list(n.labels)
                            nodes_dict[element_id] = {
                                "id": n.get("id", element_id),
                                "label": labels[0] if labels else "Unknown",
                                "properties": dict(n)
                            }
                if "all_edges" in record and record["all_edges"]:
                    for r in record["all_edges"]:
                        if r.element_id not in seen_edges:
                            seen_edges.add(r.element_id)
                            nodes = list(r.nodes)
                            edges_list.append({
                                "id": r.element_id,
                                "type": r.type,
                                "source": nodes[0].get("id", nodes[0].element_id),
                                "target": nodes[1].get("id", nodes[1].element_id),
                                "properties": dict(r)
                            })
                            
            return {
                "nodes": list(nodes_dict.values()),
                "edges": edges_list
            }
