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
    
    # Errors & Status
    error: Optional[str]
    status: str
    current_stage: str
