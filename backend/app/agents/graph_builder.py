import logging
from langgraph.graph import StateGraph, END
from app.agents.state import FoundryState
from app.agents.nodes.supervisor import supervisor_node, route_from_supervisor, check_error
from app.agents.nodes.document import document_processing_node
from app.agents.nodes.entity import entity_extraction_node
from app.agents.nodes.entity_resolution import entity_resolution_node
from app.agents.nodes.graph_write import graph_write_node
from app.agents.nodes.embedding import embedding_node
from app.agents.nodes.retrieval import retrieval_node

logger = logging.getLogger(__name__)

def build_ingestion_graph():
    """Build the LangGraph for the ingestion pipeline."""
    logger.info("Building ingestion graph")
    
    workflow = StateGraph(FoundryState)
    
    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("document_processing_node", document_processing_node)
    workflow.add_node("entity_extraction_node", entity_extraction_node)
    workflow.add_node("entity_resolution_node", entity_resolution_node)
    workflow.add_node("graph_write_node", graph_write_node)
    workflow.add_node("embedding_node", embedding_node)
    workflow.add_node("retrieval_node", retrieval_node)
    
    # Set entry point
    workflow.set_entry_point("supervisor")
    
    # Supervisor routes to initial processing
    workflow.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "document_processing_node": "document_processing_node",
            "retrieval_node": "retrieval_node",
            "end": END,
            "error_end": END
        }
    )
    
    # After document processing, check error or route to entity
    workflow.add_conditional_edges(
        "document_processing_node",
        check_error,
        {
            "entity_extraction_node": "entity_extraction_node",
            "error_end": END,
            "end": END
        }
    )
    
    # After entity extraction, route to entity resolution
    workflow.add_conditional_edges(
        "entity_extraction_node",
        check_error,
        {
            "entity_resolution_node": "entity_resolution_node",
            "error_end": END,
            "end": END
        }
    )
    
    # After entity resolution, route to graph write
    workflow.add_conditional_edges(
        "entity_resolution_node",
        check_error,
        {
            "graph_write_node": "graph_write_node",
            "error_end": END,
            "end": END
        }
    )
    
    # After graph write, route to embedding
    workflow.add_conditional_edges(
        "graph_write_node",
        check_error,
        {
            "embedding_node": "embedding_node",
            "error_end": END,
            "end": END
        }
    )
    
    # After embedding, end
    workflow.add_conditional_edges(
        "embedding_node",
        check_error,
        {
            "end": END,
            "error_end": END
        }
    )
    
    # After retrieval, end
    workflow.add_conditional_edges(
        "retrieval_node",
        check_error,
        {
            "end": END,
            "error_end": END
        }
    )
    
    # Compile
    return workflow.compile()

# Singleton instance
ingestion_graph = build_ingestion_graph()
