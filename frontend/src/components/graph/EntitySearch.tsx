"use client";

import React, { useState } from 'react';
import { Input } from '@/components/ui/input';
import { Search } from 'lucide-react';
import { useRouter } from 'next/navigation';

export default function EntitySearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const router = useRouter();

  const handleSearch = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    if (val.length > 2) {
      try {
        const res = await fetch(`http://localhost:8008/api/v1/graph/search?q=${val}`);
        if (res.ok) {
          const data = await res.json();
          setResults(data.results || []);
        }
      } catch (err) {
        console.error("Search failed", err);
      }
    } else {
      setResults([]);
    }
  };

  return (
    <div className="relative w-full max-w-md">
      <div className="relative">
        <Search className="absolute left-2 top-2.5 h-4 w-4 text-zinc-400" />
        <Input 
          type="text"
          placeholder="Search equipment, procedures..."
          value={query}
          onChange={handleSearch}
          className="pl-8 bg-zinc-900 border-zinc-700"
        />
      </div>
      {results.length > 0 && (
        <div className="absolute z-10 w-full mt-1 bg-zinc-800 border border-zinc-700 rounded-md shadow-lg max-h-60 overflow-y-auto">
          {results.map((r, i) => (
            <div 
              key={i} 
              className="px-4 py-2 hover:bg-zinc-700 cursor-pointer text-sm"
              onClick={() => {
                setQuery('');
                setResults([]);
                if (r.type === 'Equipment') {
                  router.push(`/dashboard/graph/${r.id}`);
                }
              }}
            >
              <div className="font-medium text-zinc-100">{r.display_name}</div>
              <div className="text-xs text-zinc-400">{r.type}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
