"use client";

import { useState, useRef, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { CodeBlock } from "@/components/ui/code-block";
import { toast } from "sonner";
import * as api from "@/lib/api";

// ─── Types ────────────────────────────────────────────────────────────────────

interface SearchHit {
  name?: string;
  type?: string;
  path?: string;
  line_number?: number;
  match_line?: string;
  score?: number;
}

interface PeekLine {
  line_number: number;
  content: string;
  is_anchor: boolean;
}

interface PeekResult {
  path: string;
  anchor_line: number;
  window: PeekLine[];
  total_lines: number;
}

// ─── PeekViewer ───────────────────────────────────────────────────────────────

function PeekViewer({ path, anchorLine }: { path: string; anchorLine: number }) {
  const STEP = 20;
  const [above, setAbove] = useState(10);
  const [below, setBelow] = useState(10);
  const [result, setResult] = useState<PeekResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [opened, setOpened] = useState(false);

  const load = useCallback(async (a: number, b: number) => {
    setLoading(true);
    try {
      const data = await api.peekFileLines(path, anchorLine, a, b);
      setResult(data as PeekResult);
      setAbove(a);
      setBelow(b);
    } catch {
      toast.error("Failed to load context");
    } finally {
      setLoading(false);
    }
  }, [path, anchorLine]);

  if (!opened) {
    return (
      <button
        className="text-xs text-primary underline-offset-2 hover:underline mt-1"
        onClick={() => { setOpened(true); load(above, below); }}
      >
        Show context
      </button>
    );
  }

  return (
    <div className="mt-2 space-y-1.5">
      <div className="flex flex-wrap gap-2 items-center text-xs text-muted-foreground">
        <button
          className="hover:text-foreground disabled:opacity-40"
          disabled={loading}
          onClick={() => load(above + STEP, below)}
        >
          ↑ {STEP} more above
        </button>
        <span>·</span>
        <button
          className="hover:text-foreground disabled:opacity-40"
          disabled={loading}
          onClick={() => load(above, below + STEP)}
        >
          {STEP} more below ↓
        </button>
        <span>·</span>
        <button className="hover:text-foreground" onClick={() => setOpened(false)}>
          collapse
        </button>
        {result && (
          <span className="ml-auto">
            lines {result.window[0]?.line_number}–{result.window[result.window.length - 1]?.line_number}
            {" "}/ {result.total_lines}
          </span>
        )}
      </div>

      {result && (
        <div className="rounded border border-border overflow-x-auto text-xs font-mono">
          {result.window.map((ln) => (
            <div
              key={ln.line_number}
              className={`flex ${ln.is_anchor
                ? "bg-yellow-400/15 dark:bg-yellow-500/15 border-l-2 border-yellow-500"
                : "hover:bg-muted/40"
              }`}
            >
              <span className="select-none w-12 text-right px-2 py-0.5 text-muted-foreground/60 shrink-0 border-r border-border">
                {ln.line_number}
              </span>
              <span className="px-3 py-0.5 whitespace-pre">{ln.content}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Type badge colours ───────────────────────────────────────────────────────

const TYPE_STYLES: Record<string, string> = {
  function: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20",
  class:    "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20",
  variable: "bg-green-500/10 text-green-600 dark:text-green-400 border-green-500/20",
  line:     "bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-500/20",
};

function TypeBadge({ type }: { type: string }) {
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium border ${TYPE_STYLES[type] ?? "bg-muted text-muted-foreground border-border"}`}>
      {type}
    </span>
  );
}

// ─── Search Result Card ───────────────────────────────────────────────────────

function SearchHitCard({ hit }: { hit: SearchHit }) {
  const filename = hit.path ? hit.path.split("/").pop() : null;
  const dirPath  = hit.path && filename ? hit.path.slice(0, hit.path.length - filename.length - 1) : null;
  const hasLine  = hit.line_number != null && hit.line_number > 0;

  return (
    <div className="group rounded-lg border border-border bg-card px-4 py-3 space-y-1.5 hover:border-primary/40 transition-colors">
      {/* Header */}
      <div className="flex items-start gap-2">
        {hit.type && <TypeBadge type={hit.type} />}
        <span className="font-mono font-semibold text-sm leading-tight break-all">
          {hit.name ?? hit.match_line?.trim()}
        </span>
        {hit.score != null && (
          <span className="ml-auto shrink-0 text-xs text-muted-foreground/50">
            {hit.score.toFixed(2)}
          </span>
        )}
      </div>

      {/* Path */}
      {hit.path && (
        <div className="flex items-center gap-1 text-xs text-muted-foreground font-mono">
          {dirPath && <span className="opacity-60 truncate">{dirPath}/</span>}
          {filename && <span className="text-foreground/80 font-medium">{filename}</span>}
          {hasLine && (
            <span className="shrink-0 px-1 rounded bg-muted text-foreground/70">:{hit.line_number}</span>
          )}
        </div>
      )}

      {/* Match snippet (for line-type results where name IS the code line) */}
      {hit.type === "line" && hit.name && (
        <pre className="text-xs text-muted-foreground bg-muted/50 rounded px-2 py-1 overflow-x-auto">{hit.name}</pre>
      )}

      {/* Peek */}
      {hit.path && hasLine && (
        <PeekViewer path={hit.path} anchorLine={hit.line_number!} />
      )}
    </div>
  );
}

// ─── Unified Search Results ───────────────────────────────────────────────────

function SearchResultsView({ data }: { data: unknown }) {
  let hits: SearchHit[] = [];
  if (Array.isArray(data)) {
    hits = data as SearchHit[];
  } else if (data && typeof data === "object") {
    const obj = data as Record<string, unknown>;
    const inner = obj.results ?? obj.symbols ?? obj.ranked_results ?? [];
    if (Array.isArray(inner)) hits = inner as SearchHit[];
  }

  if (hits.length === 0) {
    return (
      <div className="py-12 text-center text-muted-foreground text-sm">
        No results found.
      </div>
    );
  }

  const symbols = hits.filter((h) => h.type !== "line");
  const lines   = hits.filter((h) => h.type === "line");

  return (
    <div className="space-y-4">
      {/* Summary row */}
      <div className="flex gap-2 text-xs text-muted-foreground">
        <span>{hits.length} results</span>
        {symbols.length > 0 && <span>· {symbols.length} symbols</span>}
        {lines.length > 0   && <span>· {lines.length} file matches</span>}
      </div>

      {symbols.length > 0 && (
        <section className="space-y-2">
          {symbols.length > 0 && lines.length > 0 && (
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Symbols</h3>
          )}
          {symbols.map((hit, i) => <SearchHitCard key={i} hit={hit} />)}
        </section>
      )}

      {lines.length > 0 && (
        <section className="space-y-2">
          {symbols.length > 0 && lines.length > 0 && (
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">File matches</h3>
          )}
          {lines.map((hit, i) => <SearchHitCard key={i} hit={hit} />)}
        </section>
      )}
    </div>
  );
}

// ─── Unified Search Tab ───────────────────────────────────────────────────────

function SearchTab() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<unknown>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const runSearch = async (q = query) => {
    const term = q.trim();
    if (!term) { inputRef.current?.focus(); return; }
    setLoading(true);
    setResults(null);
    try {
      const data = await api.searchCode(term);
      setResults(data);
    } catch (e) {
      toast.error(`Search failed: ${e instanceof Error ? e.message : "Unknown error"}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4 pt-4">
      {/* Search bar */}
      <div className="flex gap-2">
        <Input
          ref={inputRef}
          placeholder="Search by name, snippet, or code pattern — e.g. GitHubRepo or class LoginRequest(BaseModel)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") runSearch(); }}
          className="text-sm"
          autoFocus
        />
        <Button onClick={() => runSearch()} disabled={loading} className="shrink-0">
          {loading ? "Searching…" : "Search"}
        </Button>
      </div>

      {/* Hint */}
      {results === null && !loading && (
        <p className="text-xs text-muted-foreground">
          Searches symbols (functions, classes, variables) and file content. Supports identifiers, code snippets, and keywords.
        </p>
      )}

      {/* Loading */}
      {loading && (
        <div className="py-10 text-center text-muted-foreground text-sm animate-pulse">Searching…</div>
      )}

      {/* Results */}
      {!loading && results !== null && <SearchResultsView data={results} />}
    </div>
  );
}

// ─── Analysis / CodeFinder / Metrics shared pattern ──────────────────────────

type QueryDef = {
  label: string;
  placeholder: string;
  fn: (q: string) => Promise<unknown>;
  needsInput: boolean;
};

const queryGroups: Record<string, QueryDef[]> = {
  Analysis: [
    { label: "Method Usages",  placeholder: "Method name…",  fn: api.getMethodUsages,  needsInput: true },
    { label: "Find Callers",   placeholder: "Symbol name…",  fn: api.findCallers,       needsInput: true },
    { label: "Class Hierarchy",placeholder: "Class name…",   fn: api.getClassHierarchy, needsInput: true },
    { label: "Change Impact",  placeholder: "Symbol name…",  fn: api.getChangeImpact,   needsInput: true },
  ],
  CodeFinder: [
    { label: "Function",    placeholder: "Function name…",   fn: api.findFunction,  needsInput: true },
    { label: "Class",       placeholder: "Class name…",      fn: api.findClass,     needsInput: true },
    { label: "Variable",    placeholder: "Variable name…",   fn: api.findVariable,  needsInput: true },
    { label: "Content",     placeholder: "Content query…",   fn: api.findContent,   needsInput: true },
    { label: "Module",      placeholder: "Module name…",     fn: api.findModule,    needsInput: true },
    { label: "Imports",     placeholder: "Import name…",     fn: api.findImports,   needsInput: true },
    { label: "Line Search", placeholder: "Code line to find…", fn: api.findByLine, needsInput: true },
  ],
  Metrics: [
    { label: "Graph Stats",           placeholder: "", fn: api.getGraphStats,          needsInput: false },
    { label: "Language Stats",        placeholder: "", fn: api.getLanguageStats,        needsInput: false },
    { label: "Top Complex Functions", placeholder: "", fn: api.getTopComplexFunctions,  needsInput: false },
  ],
};

function GenericQueryTab({ queries }: { queries: QueryDef[] }) {
  const [input, setInput]           = useState("");
  const [loading, setLoading]       = useState(false);
  const [results, setResults]       = useState<unknown>(null);
  const [activeLabel, setActiveLabel] = useState<string>("");

  const run = async (q: QueryDef) => {
    if (q.needsInput && !input.trim()) { toast.error("Enter a query first"); return; }
    setLoading(true);
    setActiveLabel(q.label);
    setResults(null);
    try {
      setResults(await q.fn(input.trim()));
    } catch (e) {
      toast.error(`Failed: ${e instanceof Error ? e.message : "Unknown error"}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4 pt-4">
      <Input
        placeholder="Enter name or query…"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && activeLabel) {
            const q = queries.find((q) => q.label === activeLabel);
            if (q) run(q);
          }
        }}
        className="text-sm"
      />
      <div className="flex flex-wrap gap-2">
        {queries.map((q) => (
          <Button
            key={q.label}
            variant={activeLabel === q.label ? "default" : "secondary"}
            size="sm"
            onClick={() => run(q)}
            disabled={loading}
          >
            {q.label}
          </Button>
        ))}
      </div>

      {loading && (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground animate-pulse">Loading…</CardContent>
        </Card>
      )}

      {!loading && results !== null && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">{activeLabel}</CardTitle>
          </CardHeader>
          <CardContent>
            <ResultsView data={results} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function QueryPage() {
  const [diffRepoId, setDiffRepoId]       = useState("");
  const [diffChangesText, setDiffChangesText] = useState("");
  const [diffLoading, setDiffLoading]     = useState(false);
  const [diffResults, setDiffResults]     = useState<unknown>(null);

  const runDiffContext = async () => {
    if (!diffRepoId.trim()) { toast.error("Enter a repository ID"); return; }
    const lines = diffChangesText.trim().split("\n").filter(Boolean);
    const changes = lines.map((line) => {
      const [filePath, range] = line.split(":");
      if (range) {
        const [start, end] = range.split("-").map(Number);
        return { file_path: filePath.trim(), start_line: start || 1, end_line: end || 999999 };
      }
      return { file_path: filePath.trim() };
    });
    if (changes.length === 0) { toast.error("Enter at least one file change"); return; }
    setDiffLoading(true);
    setDiffResults(null);
    try {
      setDiffResults(await api.getDiffContext({ repo_id: diffRepoId.trim(), changes }));
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
          <TabsTrigger value="Search">Search</TabsTrigger>
          <TabsTrigger value="Analysis">Analysis</TabsTrigger>
          <TabsTrigger value="CodeFinder">CodeFinder</TabsTrigger>
          <TabsTrigger value="Metrics">Metrics</TabsTrigger>
          <TabsTrigger value="DiffContext">Code Review</TabsTrigger>
        </TabsList>

        <TabsContent value="Search">
          <SearchTab />
        </TabsContent>

        {Object.entries(queryGroups).map(([group, queries]) => (
          <TabsContent key={group} value={group}>
            <GenericQueryTab queries={queries} />
          </TabsContent>
        ))}

        <TabsContent value="DiffContext" className="space-y-4 pt-4">
          <Card>
            <CardHeader><CardTitle>Diff Context Builder</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Build RAG context for code review. Provide the repository and changed files
                to get affected symbols, callers, class hierarchy, and source.
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
                  placeholder={"One per line — file_path:start_line-end_line\n\nExamples:\nsrc/main.py:10-30\nsrc/utils.py:1-50"}
                  value={diffChangesText}
                  onChange={(e) => setDiffChangesText(e.target.value)}
                  rows={6}
                  className="font-mono text-sm"
                />
              </div>
              <Button onClick={runDiffContext} disabled={diffLoading}>
                {diffLoading ? "Loading…" : "Get Diff Context"}
              </Button>
            </CardContent>
          </Card>
          {diffResults !== null && <DiffContextResults data={diffResults as DiffContextData} />}
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ─── Diff Context Results ──────────────────────────────────────────────────────

interface DiffContextData {
  affected_symbols: {
    type: string; name: string; start_line: number; end_line: number;
    source: string | null; docstring: string | null; change_file: string;
  }[];
  callers: {
    symbol: string; symbol_type: string;
    callers: { type: string; name: string; path: string; source: string | null }[];
  }[];
  class_hierarchy: { class: string; hierarchy: { name: string; path: string }[] }[];
  file_sources: Record<string, string>;
  total_affected: number;
  total_files: number;
}

function DiffContextResults({ data }: { data: DiffContextData }) {
  return (
    <div className="space-y-4">
      <div className="flex gap-3">
        <Badge variant="secondary">{data.total_files} files</Badge>
        <Badge variant="secondary">{data.total_affected} affected symbols</Badge>
        <Badge variant="secondary">{data.callers.length} caller chains</Badge>
        <Badge variant="secondary">{data.class_hierarchy.length} class hierarchies</Badge>
      </div>

      {data.affected_symbols.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-sm">Affected Symbols</CardTitle></CardHeader>
          <CardContent className="space-y-2 max-h-96 overflow-y-auto">
            {data.affected_symbols.map((sym, i) => (
              <div key={i} className="p-3 rounded border border-border space-y-1">
                <div className="flex items-center gap-2">
                  <Badge variant={sym.type === "function" ? "default" : "secondary"}>{sym.type}</Badge>
                  <span className="font-medium font-mono">{sym.name}</span>
                  <span className="text-xs text-muted-foreground">{sym.change_file}:{sym.start_line}-{sym.end_line}</span>
                </div>
                {sym.docstring && <p className="text-xs text-muted-foreground">{sym.docstring}</p>}
                {sym.source && <CodeBlock code={sym.source} startLine={sym.start_line} maxHeight="max-h-48" />}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {data.callers.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-sm">Callers</CardTitle></CardHeader>
          <CardContent className="space-y-3 max-h-96 overflow-y-auto">
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
                    {caller.source && <CodeBlock code={caller.source} maxHeight="max-h-32" className="mt-1" />}
                  </div>
                ))}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {data.class_hierarchy.length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-sm">Class Hierarchy</CardTitle></CardHeader>
          <CardContent className="space-y-2 max-h-72 overflow-y-auto">
            {data.class_hierarchy.map((h, i) => (
              <div key={i} className="space-y-1">
                <p className="text-sm font-medium font-mono">{h.class}</p>
                <div className="ml-4 space-y-1">
                  {h.hierarchy.map((parent, j) => (
                    <div key={j} className="flex items-center gap-2 text-sm">
                      <span className="text-muted-foreground">{j === 0 ? "" : "└─"}</span>
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

      {Object.keys(data.file_sources).length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-sm">File Sources</CardTitle></CardHeader>
          <CardContent className="space-y-3 max-h-96 overflow-y-auto">
            {Object.entries(data.file_sources).map(([path, source]) => (
              <div key={path} className="space-y-1">
                <p className="text-sm font-mono text-primary">{path}</p>
                <CodeBlock code={source} maxHeight="max-h-64" />
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ─── Generic JSON Results ─────────────────────────────────────────────────────

function ResultsView({ data }: { data: unknown }) {
  if (!data) return <p className="text-muted-foreground text-sm">No results</p>;

  if (Array.isArray(data)) {
    if (data.length === 0) return <p className="text-muted-foreground text-sm">No results found</p>;
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

  if (typeof data === "object") return <ObjectView obj={data as Record<string, unknown>} />;
  return <pre className="text-sm font-mono">{String(data)}</pre>;
}

function ObjectView({ obj }: { obj: Record<string, unknown> }) {
  return (
    <div className="space-y-1">
      {Object.entries(obj).map(([key, value]) => {
        if (key === "source" && typeof value === "string" && value) {
          const startLine = (obj.line_number as number) || (obj.start_line as number) || 1;
          return (
            <div key={key} className="space-y-1">
              <span className="text-primary font-medium">{key}:</span>
              <CodeBlock code={value} startLine={startLine} maxHeight="max-h-64" />
            </div>
          );
        }
        if (Array.isArray(value)) {
          return (
            <div key={key} className="space-y-1">
              <span className="text-primary font-medium">{key}:</span>
              {value.length === 0
                ? <span className="text-muted-foreground ml-2">[]</span>
                : (
                  <div className="ml-4 space-y-2">
                    {value.map((item, i) => (
                      <div key={i} className="p-3 rounded border border-border text-sm font-mono whitespace-pre-wrap break-all">
                        {typeof item === "object" && item !== null ? <ObjectView obj={item as Record<string, unknown>} /> : String(item)}
                      </div>
                    ))}
                  </div>
                )}
            </div>
          );
        }
        if (typeof value === "object" && value !== null) {
          return (
            <div key={key} className="space-y-1">
              <span className="text-primary font-medium">{key}:</span>
              <div className="ml-4 p-3 rounded border border-border text-sm font-mono whitespace-pre-wrap break-all">
                <ObjectView obj={value as Record<string, unknown>} />
              </div>
            </div>
          );
        }
        return (
          <div key={key} className="flex gap-2">
            <span className="text-primary font-medium shrink-0">{key}:</span>
            <span className="text-muted-foreground break-all">{String(value ?? "—")}</span>
          </div>
        );
      })}
    </div>
  );
}
