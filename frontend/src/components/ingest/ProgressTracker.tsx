import React from 'react';
import { CheckCircle2, Circle, Loader2, XCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface IngestStage {
  stage: string;
  status: 'started' | 'completed' | 'error';
}

interface ProgressTrackerProps {
  stages: IngestStage[];
  status: string;
}

const ALL_STAGES = [
  { id: 'started', label: 'Upload & Queue' },
  { id: 'process_document', label: 'Extract Text (OCR)' },
  { id: 'extract_entities', label: 'Extract Entities (LLM)' },
  { id: 'embed_document', label: 'Generate Embeddings' },
];

export function ProgressTracker({ stages, status }: ProgressTrackerProps) {
  // Find current stage index based on the stages log
  const stageLogIds = stages.map(s => s.stage);
  
  const getStageStatus = (stageId: string, index: number) => {
    if (status === 'error' && stageLogIds[stageLogIds.length - 1] === stageId) {
      return 'error';
    }
    
    if (stageLogIds.includes(stageId)) {
      const stage = stages.find(s => s.stage === stageId);
      return stage?.status === 'error' ? 'error' : 'completed';
    }
    
    if (stages.length === 0 && index === 0) {
      return status === 'processing' || status === 'queued' ? 'active' : 'pending';
    }
    
    // If the previous stage is completed, this might be active
    const prevStage = index > 0 ? ALL_STAGES[index - 1].id : null;
    if (prevStage && stageLogIds.includes(prevStage) && status === 'processing') {
      // It's the current active stage if the last logged stage was the previous one
      // OR if it's currently logging as 'started'
      const thisStageLog = stages.find(s => s.stage === stageId);
      if (thisStageLog?.status === 'started' || !thisStageLog) {
          return 'active';
      }
    }
    
    return 'pending';
  };

  return (
    <div className="space-y-4">
      {ALL_STAGES.map((s, idx) => {
        const stageStatus = getStageStatus(s.id, idx);
        
        return (
          <div key={s.id} className="flex items-center space-x-3">
            {stageStatus === 'completed' && <CheckCircle2 className="h-5 w-5 text-green-500" />}
            {stageStatus === 'active' && <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />}
            {stageStatus === 'error' && <XCircle className="h-5 w-5 text-red-500" />}
            {stageStatus === 'pending' && <Circle className="h-5 w-5 text-muted-foreground" />}
            
            <span className={cn(
              "text-sm font-medium",
              stageStatus === 'active' ? "text-primary" : "text-muted-foreground",
              stageStatus === 'error' && "text-red-500"
            )}>
              {s.label}
            </span>
          </div>
        );
      })}
      
      {status === 'completed' && (
        <div className="mt-4 p-3 bg-green-500/10 text-green-600 rounded-md flex items-center">
          <CheckCircle2 className="h-5 w-5 mr-2" />
          Document processing complete. Ready for search.
        </div>
      )}
      
      {status === 'failed' && (
        <div className="mt-4 p-3 bg-red-500/10 text-red-600 rounded-md flex items-center">
          <XCircle className="h-5 w-5 mr-2" />
          Processing failed. Please try again.
        </div>
      )}
    </div>
  );
}
