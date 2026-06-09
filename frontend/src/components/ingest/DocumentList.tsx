'use client';

import React, { useEffect, useState } from 'react';
import { format } from 'date-fns';
import { FileText, Clock, CheckCircle2, XCircle } from 'lucide-react';
import { api } from '@/lib/api';

interface Document {
  id: string;
  filename: string;
  doc_type: string;
  status: string;
  created_at: string;
}

export function DocumentList() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchDocuments = async () => {
    try {
      const res = await api.get('/ingest/documents');
      if (res.data.items) {
        setDocuments(res.data.items);
      }
    } catch (e) {
      console.error('Failed to fetch documents', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
    const interval = setInterval(fetchDocuments, 10000); // Poll every 10s
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return <div className="text-sm text-muted-foreground">Loading documents...</div>;
  }

  if (documents.length === 0) {
    return <div className="text-sm text-muted-foreground">No documents ingested yet.</div>;
  }

  return (
    <div className="space-y-4">
      {documents.map(doc => (
        <div key={doc.id} className="flex items-center justify-between p-4 border rounded-lg bg-card">
          <div className="flex items-center space-x-4">
            <div className="p-2 bg-primary/10 rounded-full">
              <FileText className="h-5 w-5 text-primary" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="font-medium truncate">{doc.filename}</p>
              <div className="flex items-center space-x-2 text-xs text-muted-foreground mt-1">
                <span className="capitalize">{doc.doc_type.replace('_', ' ')}</span>
                <span>•</span>
                <span>{format(new Date(doc.created_at), 'MMM d, h:mm a')}</span>
              </div>
            </div>
          </div>
          
          <div>
            {doc.status === 'completed' && <CheckCircle2 className="h-5 w-5 text-green-500" />}
            {doc.status === 'failed' && <XCircle className="h-5 w-5 text-red-500" />}
            {(doc.status === 'processing' || doc.status === 'queued') && (
              <Clock className="h-5 w-5 text-blue-500 animate-pulse" />
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
