"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { ArrowLeft, Activity } from "lucide-react";
import { Button } from "@/components/ui/button";

const GraphCanvas = dynamic(() => import("@/components/graph/GraphCanvas"), { ssr: false });

export default function EntityDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  
  const [data, setData] = useState<{node: any, subgraph: any} | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    fetch(`http://localhost:8008/api/v1/graph/equipment/${id}`)
      .then(res => res.json())
      .then(d => {
        setData(d);
        setLoading(false);
      })
      .catch(e => {
        console.error(e);
        setLoading(false);
      });
  }, [id]);

  if (loading) {
    return <div className="p-8 flex justify-center"><div className="animate-spin h-8 w-8 border-4 border-blue-500 rounded-full border-t-transparent"></div></div>;
  }

  if (!data || !data.subgraph) {
    return <div className="p-8 text-center text-red-400">Entity not found.</div>;
  }

  // Format elements for Cytoscape
  const elements = [
    ...data.subgraph.nodes.map((n: any) => ({
      data: {
        id: n.id,
        label: n.properties.name || n.properties.title || n.properties.description || n.label,
        type: n.label,
        ...n.properties
      }
    })),
    ...data.subgraph.edges.map((e: any) => ({
      data: {
        id: e.id,
        source: e.source,
        target: e.target,
        type: e.type,
        ...e.properties
      }
    }))
  ];

  return (
    <div className="flex flex-col h-full p-4">
      <div className="mb-4 flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.back()}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold text-zinc-100 flex items-center gap-2">
            <Activity className="h-6 w-6 text-blue-500" />
            {data.node.name || data.node.title || data.node.description || "Entity Detail"}
          </h1>
          <div className="flex gap-2 mt-1">
            <span className="px-2 py-0.5 bg-blue-900/50 text-blue-400 rounded text-xs font-medium border border-blue-800">
              {data.node.id}
            </span>
          </div>
        </div>
      </div>
      
      <div className="flex-1 min-h-0 bg-zinc-950 border border-zinc-800 rounded-lg shadow-xl relative overflow-hidden">
        <GraphCanvas elements={elements} />
        
        {/* Detail Panel overlay */}
        <div className="absolute top-4 right-4 w-80 bg-zinc-900/90 backdrop-blur border border-zinc-700 rounded-lg p-4 shadow-2xl">
          <h3 className="font-semibold text-lg border-b border-zinc-700 pb-2 mb-3">Properties</h3>
          <div className="space-y-2 text-sm max-h-96 overflow-y-auto">
            {Object.entries(data.node).map(([k, v]) => {
              if (k === 'id') return null;
              return (
                <div key={k} className="flex flex-col">
                  <span className="text-zinc-500 uppercase text-xs">{k}</span>
                  <span className="text-zinc-200">{String(v)}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
