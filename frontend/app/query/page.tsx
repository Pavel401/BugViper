"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import * as api from "@/lib/api";

type QueryDef = {
  label: string;
  placeholder: string;
  fn: (q: string) => Promise<unknown>;
  needsInput: boolean;
};

const queryGroups: Record<string, QueryDef[]> = {
  Search: [
    { label: "Full-text Search", placeholder: "Search query...", fn: api.searchCode, needsInput: true },
    { label: "Symbol Search", placeholder: "Symbol name...", fn: api.searchSymbols, needsInput: true },
  ],
  Analysis: [
    { label: "Method Usages", placeholder: "Method name...", fn: api.getMethodUsages, needsInput: true },
    { label: "Find Callers", placeholder: "Symbol name...", fn: api.findCallers, needsInput: true },
    { label: "Class Hierarchy", placeholder: "Class name...", fn: api.getClassHierarchy, needsInput: true },
    { label: "Change Impact", placeholder: "Symbol name...", fn: api.getChangeImpact, needsInput: true },
  ],
  CodeFinder: [
    { label: "Function", placeholder: "Function name...", fn: api.findFunction, needsInput: true },
    { label: "Class", placeholder: "Class name...", fn: api.findClass, needsInput: true },
    { label: "Variable", placeholder: "Variable name...", fn: api.findVariable, needsInput: true },
    { label: "Content", placeholder: "Content query...", fn: api.findContent, needsInput: true },
    { label: "Module", placeholder: "Module name...", fn: api.findModule, needsInput: true },
    { label: "Imports", placeholder: "Import name...", fn: api.findImports, needsInput: true },
  ],
  Metrics: [
    { label: "Graph Stats", placeholder: "", fn: api.getGraphStats, needsInput: false },
    { label: "Language Stats", placeholder: "", fn: api.getLanguageStats, needsInput: false },
    { label: "Top Complex Functions", placeholder: "", fn: api.getTopComplexFunctions, needsInput: false },
  ],
};

export default function QueryPage() {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<unknown>(null);
  const [activeQuery, setActiveQuery] = useState<string>("");

  // Diff context state
  const [diffRepoId, setDiffRepoId] = useState("");
  const [diffChangesText, setDiffChangesText] = useState("");
  const [diffLoading, setDiffLoading] = useState(false);
  const [diffResults, setDiffResults] = useState<unknown>(null);

  const runQuery = async (qDef: QueryDef) => {
    if (qDef.needsInput && !input.trim()) {
      toast.error("Please enter a query");
      return;
    }
    setLoading(true);
    setActiveQuery(qDef.label);
    try {
      const data = await qDef.fn(input.trim());
      setResults(data);
    } catch (e) {
      toast.error(`Query failed: ${e instanceof Error ? e.message : "Unknown error"}`);
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  const runDiffContext = async () => {
    if (!diffRepoId.trim()) {
      toast.error("Please enter a repository ID");
      return;
    }
    // Parse changes: one per line, format: file_path:start_line-end_line
    const lines = diffChangesText.trim().split("\n").filter(Boolean);
    const changes = lines.map((line) => {
      const [filePath, range] = line.split(":");
      if (range) {
        const [start, end] = range.split("-").map(Number);
        return { file_path: filePath.trim(), start_line: start || 1, end_line: end || 999999 };
      }
      return { file_path: filePath.trim() };
    });

    if (changes.length === 0) {
      toast.error("Please enter at least one file change");
      return;
    }

    setDiffLoading(true);
    setDiffResults(null);
    try {
      const data = await api.getDiffContext({ repo_id: diffRepoId.trim(), changes });
      setDiffResults(data);
    } catch (e) {
      toast.error(`Diff context failed: ${e instanceof Error ? e.message : "Unknown error"}`);
    } finally {
      setDiffLoading(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Query</h1>

      <Tabs defaultValue="Search">
        <TabsList>
          {Object.keys(queryGroups).map((group) => (
            <TabsTrigger key={group} value={group}>
              {group}
            </TabsTrigger>
          ))}
          <TabsTrigger value="DiffContext">Code Review</TabsTrigger>
        </TabsList>

        {Object.entries(queryGroups).map(([group, queries]) => (
          <TabsContent key={group} value={group} className="space-y-4 pt-4">
            <Input
              placeholder="Enter search term or symbol name..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className="text-base"
              onKeyDown={(e) => {
                if (e.key === "Enter" && activeQuery) {
                  const allQueries = Object.values(queryGroups).flat();
                  const q = allQueries.find((q) => q.label === activeQuery);
                  if (q) runQuery(q);
                }
              }}
            />
            <div className="flex flex-wrap gap-2">
              {queries.map((q) => (
                <Button
                  key={q.label}
                  variant={activeQuery === q.label ? "default" : "secondary"}
                  size="sm"
                  onClick={() => runQuery(q)}
                  disabled={loading}
                >
                  {q.label}
                </Button>
              ))}
            </div>
          </TabsContent>
        ))}

        <TabsContent value="DiffContext" className="space-y-4 pt-4">
          <Card>
            <CardHeader>
              <CardTitle>Diff Context Builder</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Build RAG context for code review. Provide the repository and changed files
                to get affected symbols, their callers, class hierarchy, and source code.
              </p>
              <div className="space-y-2">
                <Label>Repository ID</Label>
                <Input
                  placeholder="owner/repo_name"
                  value={diffRepoId}
                  onChange={(e) => setDiffRepoId(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Changed Files</Label>
                <Textarea
                  placeholder={"One per line — file_path:start_line-end_line\n\nExamples:\nsrc/main.py:10-30\nsrc/utils.py:1-50\nREADME.md"}
                  value={diffChangesText}
                  onChange={(e) => setDiffChangesText(e.target.value)}
                  rows={6}
                  className="font-mono text-sm"
                />
              </div>
              <Button onClick={runDiffContext} disabled={diffLoading}>
                {diffLoading ? "Loading..." : "Get Diff Context"}
              </Button>
            </CardContent>
          </Card>

          {diffResults !== null && (
            <DiffContextResults data={diffResults as DiffContextData} />
          )}
        </TabsContent>
      </Tabs>

      {/* Standard query results */}
      {loading && (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            Loading...
          </CardContent>
        </Card>
      )}

      {!loading && results !== null && activeQuery !== "" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">
              Results: {activeQuery}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ResultsView data={results} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// --- Diff Context Results ---

interface DiffContextData {
  affected_symbols: {
    type: string;
    name: string;
    start_line: number;
    end_line: number;
    source: string | null;
    docstring: string | null;
    change_file: string;
    file_path?: string;
  }[];
  callers: {
    symbol: string;
    symbol_type: string;
    callers: { type: string; name: string; path: string; source: string | null }[];
  }[];
  class_hierarchy: {
    class: string;
    hierarchy: { name: string; path: string; source: string | null }[];
  }[];
  file_sources: Record<string, string>;
  total_affected: number;
  total_files: number;
}

function DiffContextResults({ data }: { data: DiffContextData }) {
  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="flex gap-3">
        <Badge variant="secondary">{data.total_files} files</Badge>
        <Badge variant="secondary">{data.total_affected} affected symbols</Badge>
        <Badge variant="secondary">{data.callers.length} caller chains</Badge>
        <Badge variant="secondary">{data.class_hierarchy.length} class hierarchies</Badge>
      </div>

      {/* Affected Symbols */}
      {data.affected_symbols.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Affected Symbols</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 max-h-[400px] overflow-y-auto">
            {data.affected_symbols.map((sym, i) => (
              <div key={i} className="p-3 rounded border border-border space-y-1">
                <div className="flex items-center gap-2">
                  <Badge variant={sym.type === "function" ? "default" : "secondary"}>{sym.type}</Badge>
                  <span className="font-medium font-mono">{sym.name}</span>
                  <span className="text-xs text-muted-foreground">
                    {sym.change_file}:{sym.start_line}-{sym.end_line}
                  </span>
                </div>
                {sym.docstring && (
                  <p className="text-xs text-muted-foreground">{sym.docstring}</p>
                )}
                {sym.source && (
                  <pre className="text-xs font-mono bg-muted p-2 rounded overflow-x-auto max-h-48">
                    {sym.source}
                  </pre>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Callers */}
      {data.callers.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Callers of Affected Symbols</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 max-h-[400px] overflow-y-auto">
            {data.callers.map((group, i) => (
              <div key={i} className="space-y-1">
                <p className="text-sm font-medium">
                  <Badge variant="outline" className="mr-1">{group.symbol_type}</Badge>
                  <span className="font-mono">{group.symbol}</span>
                  <span className="text-muted-foreground ml-1">called by:</span>
                </p>
                {group.callers.map((caller, j) => (
                  <div key={j} className="ml-4 p-2 rounded border border-border text-sm">
                    <span className="font-mono">{caller.name}</span>
                    <span className="text-xs text-muted-foreground ml-2">{caller.path}</span>
                    {caller.source && (
                      <pre className="text-xs font-mono bg-muted p-2 rounded mt-1 overflow-x-auto max-h-32">
                        {caller.source}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Class Hierarchy */}
      {data.class_hierarchy.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Class Hierarchy</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 max-h-[300px] overflow-y-auto">
            {data.class_hierarchy.map((h, i) => (
              <div key={i} className="space-y-1">
                <p className="text-sm font-medium font-mono">{h.class}</p>
                <div className="ml-4 space-y-1">
                  {h.hierarchy.map((parent, j) => (
                    <div key={j} className="flex items-center gap-2 text-sm">
                      <span className="text-muted-foreground">{j === 0 ? "" : "\u2514\u2500"}</span>
                      <span className="font-mono">{parent.name}</span>
                      <span className="text-xs text-muted-foreground">{parent.path}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* File Sources */}
      {Object.keys(data.file_sources).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">File Sources</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 max-h-[400px] overflow-y-auto">
            {Object.entries(data.file_sources).map(([path, source]) => (
              <div key={path} className="space-y-1">
                <p className="text-sm font-mono text-primary">{path}</p>
                <pre className="text-xs font-mono bg-muted p-3 rounded overflow-x-auto max-h-64">
                  {source}
                </pre>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// --- Generic Results ---

function ResultsView({ data }: { data: unknown }) {
  if (data === null || data === undefined) {
    return <p className="text-muted-foreground">No results</p>;
  }

  if (Array.isArray(data)) {
    if (data.length === 0) return <p className="text-muted-foreground">No results found</p>;
    return (
      <div className="space-y-2 max-h-[600px] overflow-y-auto">
        {data.map((item, i) => (
          <div key={i} className="p-3 rounded border border-border text-sm font-mono whitespace-pre-wrap break-all">
            {typeof item === "object" ? <ObjectView obj={item} /> : String(item)}
          </div>
        ))}
      </div>
    );
  }

  if (typeof data === "object") {
    return <ObjectView obj={data as Record<string, unknown>} />;
  }

  return <pre className="text-sm font-mono">{String(data)}</pre>;
}

function ObjectView({ obj }: { obj: Record<string, unknown> }) {
  return (
    <div className="space-y-1">
      {Object.entries(obj).map(([key, value]) => (
        <div key={key} className="flex gap-2">
          <span className="text-primary font-medium shrink-0">{key}:</span>
          <span className="text-muted-foreground break-all">
            {typeof value === "object" && value !== null
              ? JSON.stringify(value, null, 2)
              : String(value ?? "\u2014")}
          </span>
        </div>
      ))}
    </div>
  );
}
