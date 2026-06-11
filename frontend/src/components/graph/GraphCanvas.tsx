"use client";

import React, { useEffect, useRef } from 'react';
import cytoscape from 'cytoscape';
import coseBilkent from 'cytoscape-cose-bilkent';
import CytoscapeComponent from 'react-cytoscapejs';
import { useRouter } from 'next/navigation';

cytoscape.use(coseBilkent);

interface GraphCanvasProps {
  elements: any[];
  onNodeClick?: (node: any) => void;
}

export default function GraphCanvas({ elements, onNodeClick }: GraphCanvasProps) {
  const cyRef = useRef<cytoscape.Core | undefined>(undefined);
  const router = useRouter();

  const layout = {
    name: 'cose-bilkent',
    animate: true,
    randomize: true,
    nodeDimensionsIncludeLabels: true,
  };

  const style: cytoscape.Stylesheet[] = [
    {
      selector: 'node',
      style: {
        'label': 'data(label)',
        'text-valign': 'center',
        'text-halign': 'center',
        'font-size': '12px',
        'color': '#fff',
        'text-outline-width': 2,
        'text-outline-color': '#333',
        'width': '60px',
        'height': '60px',
      }
    },
    {
      selector: 'node[type="Equipment"]',
      style: { 'background-color': '#3B82F6', 'shape': 'hexagon' }
    },
    {
      selector: 'node[type="Failure"]',
      style: { 'background-color': '#EF4444', 'shape': 'diamond' }
    },
    {
      selector: 'node[type="Procedure"]',
      style: { 'background-color': '#10B981', 'shape': 'round-rectangle' }
    },
    {
      selector: 'edge',
      style: {
        'width': 2,
        'line-color': '#94a3b8',
        'target-arrow-color': '#94a3b8',
        'target-arrow-shape': 'triangle',
        'curve-style': 'bezier',
        'label': 'data(type)',
        'font-size': '10px',
        'text-rotation': 'autorotate',
        'color': '#cbd5e1',
        'text-background-opacity': 1,
        'text-background-color': '#0f172a'
      }
    }
  ];

  return (
    <div className="w-full h-full min-h-[600px] border border-zinc-800 rounded-lg overflow-hidden bg-zinc-950">
      <CytoscapeComponent
        elements={elements}
        style={{ width: '100%', height: '100%' }}
        stylesheet={style}
        layout={layout}
        cy={(cy) => {
          cyRef.current = cy;
          cy.on('tap', 'node', (evt) => {
            if (onNodeClick) {
              onNodeClick(evt.target.data());
            }
          });
          cy.on('dbltap', 'node', (evt) => {
            const data = evt.target.data();
            if (data.type === 'Equipment') {
              router.push(`/dashboard/graph/${data.id}`);
            }
          });
        }}
      />
    </div>
  );
}
