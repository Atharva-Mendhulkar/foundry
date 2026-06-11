from typing import TypedDict, List, Dict, Any, Optional

class FoundryState(TypedDict):
    # Job Context
    job_id: str
    document_id: str
    facility_id: str
    input_type: str  # e.g., 'document', 'voice', 'shift'
    doc_type: str    # e.g., 'sop', 'work_order'
    
    # Text Payload
    raw_text: str
    
    # Processed Output
    extracted_entities: List[Dict[str, Any]]
    observations: List[Dict[str, Any]]
    pending_actions: List[Dict[str, Any]]
    risk_events: List[Dict[str, Any]]
    
    # Query Context
    query: Optional[str]
    session_id: Optional[str]
    user_id: Optional[str]
    equipment_context: Optional[str]
    
    # Query Results
    resolved_entities: Optional[List[Dict[str, Any]]]
    vector_results: Optional[List[Dict[str, Any]]]
    graph_context: Optional[Dict[str, Any]]
    merged_context: Optional[str]
    
    # Copilot Output
    response: Optional[str]
    sources: Optional[List[Dict[str, Any]]]
    confidence: Optional[float]
    
    # Errors & Status
    error: Optional[str]
    status: str
    current_stage: str
