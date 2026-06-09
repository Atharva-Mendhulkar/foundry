'use client';

import React, { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { UploadCloud } from 'lucide-react';
import { cn } from '@/lib/utils';

interface DropZoneProps {
  onUpload: (file: File) => void;
  disabled?: boolean;
}

export function DropZone({ onUpload, disabled = false }: DropZoneProps) {
  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      onUpload(acceptedFiles[0]);
    }
  }, [onUpload]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
    },
    maxFiles: 1,
    disabled
  });

  return (
    <div
      {...getRootProps()}
      className={cn(
        "border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors",
        isDragActive ? "border-primary bg-primary/5" : "border-muted-foreground/25 hover:border-primary/50",
        disabled && "opacity-50 cursor-not-allowed"
      )}
    >
      <input {...getInputProps()} />
      <UploadCloud className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
      <h3 className="text-lg font-semibold mb-1">
        {isDragActive ? "Drop the PDF here" : "Drag & drop a PDF here"}
      </h3>
      <p className="text-sm text-muted-foreground">
        or click to select a file (SOP, Work Order, Incident Report)
      </p>
    </div>
  );
}
