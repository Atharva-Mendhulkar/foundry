"use client";

import { useEffect, useState } from "react";
import EntitySearch from "@/components/graph/EntitySearch";
import { Layers } from "lucide-react";

export default function GraphExplorerPage() {
  const [stats, setStats] = useState({ equipment_count: 0, failure_count: 0, procedure_count: 0, relationship_count: 0 });

  useEffect(() => {
    fetch('http://localhost:8008/api/v1/graph/stats')
      .then(r => r.json())
      .then(d => setStats(d))
      .catch(console.error);
  }, []);

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2 flex items-center gap-3">
          <Layers className="h-8 w-8 text-blue-500" />
          Knowledge Graph Explorer
        </h1>
        <p className="text-zinc-400">Search the Neo4j ontology for Equipment, Failures, and Procedures.</p>
      </div>

      <div className="mb-10">
        <EntitySearch />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-zinc-900 border border-zinc-800 p-6 rounded-lg text-center">
          <div className="text-3xl font-bold text-blue-400">{stats.equipment_count}</div>
          <div className="text-sm text-zinc-500 uppercase tracking-wider mt-2">Equipment</div>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 p-6 rounded-lg text-center">
          <div className="text-3xl font-bold text-red-400">{stats.failure_count}</div>
          <div className="text-sm text-zinc-500 uppercase tracking-wider mt-2">Failures</div>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 p-6 rounded-lg text-center">
          <div className="text-3xl font-bold text-green-400">{stats.procedure_count}</div>
          <div className="text-sm text-zinc-500 uppercase tracking-wider mt-2">Procedures</div>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 p-6 rounded-lg text-center">
          <div className="text-3xl font-bold text-zinc-300">{stats.relationship_count}</div>
          <div className="text-sm text-zinc-500 uppercase tracking-wider mt-2">Relationships</div>
        </div>
      </div>
      
      <div className="bg-zinc-900 border border-zinc-800 p-6 rounded-lg">
        <h2 className="text-xl font-medium mb-4">How to use</h2>
        <ul className="list-disc list-inside space-y-2 text-zinc-400">
          <li>Use the search bar above to find specific entities.</li>
          <li>Clicking on an entity will navigate to its detail page.</li>
          <li>The detail page will render the local graph around the entity.</li>
          <li>Double-click nodes in the graph to traverse further.</li>
        </ul>
      </div>
    </div>
  );
}
