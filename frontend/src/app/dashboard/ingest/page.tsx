'use client';

import React, { useState, useEffect } from 'react';
import { DropZone } from '@/components/ingest/DropZone';
import { ProgressTracker, IngestStage } from '@/components/ingest/ProgressTracker';
import { DocumentList } from '@/components/ingest/DocumentList';
import { Button } from '@/components/ui/button';

export default function IngestPage() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>('idle');
  const [stages, setStages] = useState<IngestStage[]>([]);
  const [error, setError] = useState<string | null>(null);
  
  const handleUpload = async (file: File) => {
    try {
      setStatus('uploading');
      setError(null);
      
      const formData = new FormData();
      formData.append('file', file);
      formData.append('doc_type', 'sop'); // Simple hardcode for Phase 1
      
      // Get token manually since we can't use apiRequest easily with FormData
      const token = localStorage.getItem('token');
      
      const res = await fetch('http://localhost:8008/api/v1/ingest/document', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });
      
      const data = await res.json();
      
      if (!res.ok) {
        throw new Error(data.detail?.message || data.detail || 'Upload failed');
      }
      
      setJobId(data.job_id);
      setStatus('processing');
      setStages([]);
      
    } catch (e: any) {
      setStatus('error');
      setError(e.message || 'Failed to upload document');
    }
  };

  useEffect(() => {
    if (!jobId) return;

    // Connect WebSocket
    const token = localStorage.getItem('token'); // Technically WS needs auth, but keeping simple for now
    // NOTE: In a real app, passing token via WS URL query param or protocol is needed
    // Assuming backend isn't strictly validating WS auth for MVP simplicity
    const ws = new WebSocket(`ws://localhost:8008/ws/ingest/${jobId}`);
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === 'progress') {
        setStages(prev => {
          const newStages = [...prev];
          const existingIdx = newStages.findIndex(s => s.stage === data.stage);
          if (existingIdx >= 0) {
            newStages[existingIdx].status = data.status;
          } else {
            newStages.push({ stage: data.stage, status: data.status });
          }
          return newStages;
        });
      } else if (data.type === 'complete') {
        setStatus('completed');
        ws.close();
      } else if (data.type === 'error') {
        setStatus('failed');
        setError(data.message);
        ws.close();
      }
    };
    
    ws.onerror = (e) => {
      console.error('WebSocket error:', e);
    };
    
    return () => {
      ws.close();
    };
  }, [jobId]);

  return (
    <div className="max-w-5xl mx-auto space-y-8 p-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Knowledge Ingestion</h1>
        <p className="text-muted-foreground mt-2">
          Upload industrial documents to extract equipment, failure modes, and procedures.
        </p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="space-y-6">
          <div className="bg-card border rounded-lg p-6 shadow-sm">
            <h2 className="text-xl font-semibold mb-4">Upload Document</h2>
            {status !== 'processing' && status !== 'uploading' ? (
              <DropZone onUpload={handleUpload} disabled={status === 'uploading'} />
            ) : (
              <div className="p-8 text-center border-2 border-dashed rounded-lg border-muted">
                <p className="text-muted-foreground">Document processing in progress...</p>
              </div>
            )}
            
            {error && (
              <div className="mt-4 p-3 bg-red-500/10 text-red-600 rounded-md text-sm">
                {error}
              </div>
            )}
          </div>
          
          {(status === 'processing' || status === 'completed' || status === 'failed' || stages.length > 0) && (
            <div className="bg-card border rounded-lg p-6 shadow-sm">
              <h2 className="text-xl font-semibold mb-4">Processing Pipeline</h2>
              <ProgressTracker stages={stages} status={status} />
              
              {(status === 'completed' || status === 'failed') && (
                <Button 
                  className="mt-6 w-full" 
                  variant="outline"
                  onClick={() => {
                    setJobId(null);
                    setStatus('idle');
                    setStages([]);
                  }}
                >
                  Upload Another Document
                </Button>
              )}
            </div>
          )}
        </div>
        
        <div className="bg-card border rounded-lg p-6 shadow-sm h-fit">
          <h2 className="text-xl font-semibold mb-4">Recent Ingestions</h2>
          <DocumentList />
        </div>
      </div>
    </div>
  );
}
