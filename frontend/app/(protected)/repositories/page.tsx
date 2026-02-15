"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import {
  listRepositories,
  deleteRepository,
  ingestGithub,
  getIngestionJobStatus,
  getRepositoryStats,
  getGitHubRepos,
  type RepositoryStatsResponse,
  type RepositoryStatistics,
  type GitHubRepo,
} from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────────

interface Repository {
  id: string;
  name?: string;
  repo_name?: string;
  owner?: string;
  username?: string;
}

interface IngestingJob {
  jobId: string;
  status: string;
  repo: GitHubRepo;
}

/**
 * Render a small status badge representing a repository ingestion status.
 *
 * @param status - Ingestion status; accepted values: "pending", "dispatched", "running", "completed", "failed"
 * @returns A JSX element with a visual badge for syncing, synced, or failed states, or `null` for any other status
 */

function SyncBadge({ status }: { status: string }) {
  if (["pending", "dispatched", "running"].includes(status)) {
    return (
      <div className="flex items-center gap-1.5 text-amber-500">
        <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 00-8 8h4z" />
        </svg>
        <span className="text-xs font-medium">Syncing</span>
      </div>
    );
  }
  if (status === "completed") {
    return (
      <div className="flex items-center gap-1.5 text-emerald-500">
        <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
        <span className="text-xs font-medium">Synced</span>
      </div>
    );
  }
  if (status === "failed") {
    return (
      <div className="flex items-center gap-1.5 text-destructive">
        <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
        <span className="text-xs font-medium">Failed</span>
      </div>
    );
  }
  return null;
}


/**
 * Render the repositories management page with repository list, GitHub picker, ingestion status badges, and delete confirmation modal.
 *
 * Renders UI for viewing synced repositories and optimistic pending ingestion cards, starting new ingestions via a GitHub repo picker, polling ingestion job statuses, displaying per-repository statistics, and confirming repository deletion.
 *
 * @returns The React element tree for the repositories management page.
 */
export default function RepositoriesPage() {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [isLoadingRepos, setIsLoadingRepos] = useState(true);
  const [repoStats, setRepoStats] = useState<Record<string, RepositoryStatistics>>({});
  const [loadingStats, setLoadingStats] = useState<Record<string, boolean>>({});

  // GitHub picker
  const [showPicker, setShowPicker] = useState(false);
  const [githubRepos, setGithubRepos] = useState<GitHubRepo[]>([]);
  const [loadingGithubRepos, setLoadingGithubRepos] = useState(false);
  const [pickerSearch, setPickerSearch] = useState("");
  const [startingRepo, setStartingRepo] = useState<string | null>(null);

  // Delete dialog
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Active ingestion jobs (keyed by full_name)
  const [ingestingJobs, setIngestingJobs] = useState<Record<string, IngestingJob>>({});
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Data loading ─────────────────────────────────────────────────────────────

  async function fetchStats(repo: Repository) {
    const repoOwner = repo.owner ?? repo.username;
    const repoNameVal = repo.name ?? repo.repo_name;
    if (!repoOwner || !repoNameVal) return;
    const repoId = repo.id ?? `${repoOwner}/${repoNameVal}`;
    setLoadingStats((prev) => ({ ...prev, [repoId]: true }));
    try {
      const res: RepositoryStatsResponse = await getRepositoryStats(repoOwner, repoNameVal);
      setRepoStats((prev) => ({ ...prev, [repoId]: res.statistics }));
    } catch {
      // stats are optional
    } finally {
      setLoadingStats((prev) => ({ ...prev, [repoId]: false }));
    }
  }

  async function loadRepositories() {
    setIsLoadingRepos(true);
    try {
      const data = await listRepositories();
      const list: Repository[] = Array.isArray(data) ? data : data?.repositories ?? [];
      setRepositories(list);
      list.forEach(fetchStats);
    } catch {
      toast.error("Failed to load repositories");
    } finally {
      setIsLoadingRepos(false);
    }
  }

  useEffect(() => { loadRepositories(); }, []);


  useEffect(() => {
    const active = Object.values(ingestingJobs).filter(
      (j) => !["completed", "failed"].includes(j.status)
    );

    if (active.length === 0) {
      if (pollRef.current) clearInterval(pollRef.current);
      return;
    }

    async function poll() {
      for (const job of active) {
        try {
          const res = await getIngestionJobStatus(job.jobId);
          const next = res.status;

          setIngestingJobs((prev) => {
            if (!prev[job.repo.full_name]) return prev;
            return { ...prev, [job.repo.full_name]: { ...prev[job.repo.full_name], status: next } };
          });

          if (next === "completed") {
            toast.success(`${job.repo.full_name} synced successfully`);
            loadRepositories();
            setTimeout(() => {
              setIngestingJobs((prev) => {
                const copy = { ...prev };
                delete copy[job.repo.full_name];
                return copy;
              });
            }, 3000);
          } else if (next === "failed") {
            toast.error(`Sync failed for ${job.repo.full_name}`);
          }
        } catch {
          // silent
        }
      }
    }

    poll();
    pollRef.current = setInterval(poll, 3000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [ingestingJobs]);


  async function openPicker() {
    setShowPicker(true);
    setPickerSearch("");
    if (githubRepos.length > 0) return;
    setLoadingGithubRepos(true);
    try {
      setGithubRepos(await getGitHubRepos());
    } catch {
      toast.error("Failed to load GitHub repositories");
    } finally {
      setLoadingGithubRepos(false);
    }
  }

  async function handleStart(repo: GitHubRepo) {
    setStartingRepo(repo.full_name);
    try {
      const [owner, repoName] = repo.full_name.split("/");
      const res = await ingestGithub({ owner, repo_name: repoName, branch: repo.default_branch });
      setShowPicker(false);
      setIngestingJobs((prev) => ({
        ...prev,
        [repo.full_name]: { jobId: res.job_id, status: res.status, repo },
      }));
    } catch (err) {
      toast.error(`Failed to start: ${err instanceof Error ? err.message : "Unknown error"}`);
    } finally {
      setStartingRepo(null);
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      await deleteRepository(deleteTarget);
      toast.success("Repository deleted");
      setDeleteTarget(null);
      loadRepositories();
    } catch {
      toast.error("Failed to delete repository");
    } finally {
      setIsDeleting(false);
    }
  }


  const existingKeys = new Set(
    repositories.map((r) => `${r.owner ?? r.username}/${r.name ?? r.repo_name}`)
  );
  const pendingCards = Object.values(ingestingJobs).filter(
    (j) => !existingKeys.has(j.repo.full_name)
  );

  const filteredRepos = githubRepos.filter(
    (r) =>
      r.full_name.toLowerCase().includes(pickerSearch.toLowerCase()) ||
      (r.description ?? "").toLowerCase().includes(pickerSearch.toLowerCase())
  );


  return (
    <div className="container py-8 space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Repositories</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {repositories.length + pendingCards.length} repositories
          </p>
        </div>
        <Button onClick={openPicker} size="sm" className="gap-1.5">
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          Add Repository
        </Button>
      </div>

      {/* Repository list */}
      <div className="space-y-2">
        {isLoadingRepos ? (
          <>
            <Skeleton className="h-20 w-full rounded-lg" />
            <Skeleton className="h-20 w-full rounded-lg" />
          </>
        ) : repositories.length === 0 && pendingCards.length === 0 ? (
          <div className="text-center py-16 text-muted-foreground border rounded-xl border-dashed">
            <p className="font-medium">No repositories yet</p>
            <p className="text-sm mt-1">Click <strong>Add Repository</strong> to get started</p>
          </div>
        ) : (
          <>
            {/* Optimistic cards for repos being ingested */}
            {pendingCards.map((job) => {
              const [owner, repoName] = job.repo.full_name.split("/");
              return (
                <div
                  key={job.repo.full_name}
                  className="flex items-center justify-between px-4 py-3.5 rounded-lg border bg-card"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2.5">
                      <span className="font-medium text-sm">{owner}/{repoName}</span>
                      <SyncBadge status={job.status} />
                    </div>
                    {job.repo.language && (
                      <span className="text-xs text-muted-foreground">{job.repo.language}</span>
                    )}
                  </div>
                </div>
              );
            })}

            {/* Synced repositories */}
            {repositories.map((repo) => {
              const repoOwner = repo.owner ?? repo.username;
              const repoNameVal = repo.name ?? repo.repo_name;
              const key = `${repoOwner}/${repoNameVal}`;
              const repoId = repo.id ?? `${repoOwner}/${repoNameVal}`;
              const job = ingestingJobs[key];
              const stats = repoStats[repoId];
              const isLoadingStatsForRepo = loadingStats[repoId];

              return (
                <div
                  key={repoId}
                  className="flex items-center justify-between px-4 py-3.5 rounded-lg border bg-card hover:bg-accent/30 transition-colors"
                >
                  <div className="space-y-1.5 flex-1 min-w-0">
                    <div className="flex items-center gap-2.5">
                      <span className="font-medium text-sm">{repoOwner}/{repoNameVal}</span>
                      {job ? (
                        <SyncBadge status={job.status} />
                      ) : (
                        <div className="flex items-center gap-1.5 text-emerald-500">
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                          </svg>
                          <span className="text-xs font-medium">Synced</span>
                        </div>
                      )}
                    </div>
                    {isLoadingStatsForRepo ? (
                      <Skeleton className="h-4 w-48" />
                    ) : stats ? (
                      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                        <span>{stats.files.toLocaleString()} files</span>
                        <span>{stats.functions.toLocaleString()} functions</span>
                        <span>{stats.classes.toLocaleString()} classes</span>
                        <span>{stats.lines.toLocaleString()} lines</span>
                        {stats.languages?.slice(0, 3).map((lang) => (
                          <Badge key={lang} variant="secondary" className="text-xs h-4 px-1.5">{lang}</Badge>
                        ))}
                      </div>
                    ) : null}
                  </div>
                  <button
                    onClick={() => setDeleteTarget(repo.id ?? `${repoOwner}/${repoNameVal}`)}
                    className="p-2 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors shrink-0 ml-3"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              );
            })}
          </>
        )}
      </div>

      {/* Delete confirmation modal */}
      {deleteTarget !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={() => { if (!isDeleting) setDeleteTarget(null); }}
          />
          <div className="relative z-10 w-full max-w-sm mx-4 bg-background border rounded-xl shadow-2xl">
            {/* Icon + title */}
            <div className="flex items-start gap-3 px-6 pt-6 pb-4">
              <div className="flex items-center justify-center w-9 h-9 rounded-full bg-destructive/10 shrink-0 mt-0.5">
                <svg className="w-4 h-4 text-destructive" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </div>
              <div className="space-y-1">
                <p className="font-semibold text-sm">Delete repository</p>
                <p className="text-sm text-muted-foreground">
                  Are you sure you want to delete{" "}
                  <span className="font-medium text-foreground">{deleteTarget}</span>?
                  This will remove all ingested graph data and cannot be undone.
                </p>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center justify-end gap-2 px-6 py-4 border-t">
              <button
                onClick={() => setDeleteTarget(null)}
                disabled={isDeleting}
                className="px-3 py-1.5 text-sm rounded-md border hover:bg-accent transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                disabled={isDeleting}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md bg-destructive text-white hover:bg-destructive/90 transition-colors disabled:opacity-50"
              >
                {isDeleting ? (
                  <>
                    <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 00-8 8h4z" />
                    </svg>
                    Deleting…
                  </>
                ) : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* GitHub Repo Picker Modal */}
      {showPicker && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={() => setShowPicker(false)}
          />
          <div className="relative z-10 w-full max-w-md mx-4 bg-background border rounded-xl shadow-2xl flex flex-col max-h-[75vh]">
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b">
              <h2 className="font-semibold">Add Repository</h2>
              <button
                onClick={() => setShowPicker(false)}
                className="text-muted-foreground hover:text-foreground transition-colors p-1 rounded-md hover:bg-accent"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Search */}
            <div className="px-4 py-3 border-b">
              <Input
                placeholder="Search repositories..."
                value={pickerSearch}
                onChange={(e) => setPickerSearch(e.target.value)}
                autoFocus
                className="h-8 text-sm"
              />
            </div>

            {/* List */}
            <div className="flex-1 overflow-y-auto py-1">
              {loadingGithubRepos ? (
                <div className="space-y-1 p-3">
                  {[1, 2, 3, 4, 5].map((n) => <Skeleton key={n} className="h-14 w-full rounded-lg" />)}
                </div>
              ) : filteredRepos.length === 0 ? (
                <div className="text-center py-10 text-sm text-muted-foreground">
                  {pickerSearch ? "No matching repositories" : "No repositories found"}
                </div>
              ) : (
                filteredRepos.map((repo) => {
                  const isStarting = startingRepo === repo.full_name;
                  const alreadyIngesting = repo.full_name in ingestingJobs;
                  const alreadyIngested = existingKeys.has(repo.full_name);
                  const disabled = isStarting || alreadyIngesting || alreadyIngested;

                  return (
                    <div
                      key={repo.full_name}
                      className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-accent/50 transition-colors"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm truncate">{repo.full_name}</span>
                          {repo.private && (
                            <span className="text-xs text-muted-foreground border rounded px-1 shrink-0">
                              Private
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 mt-0.5">
                          {repo.language && (
                            <span className="text-xs text-muted-foreground">{repo.language}</span>
                          )}
                          {repo.stargazers_count > 0 && (
                            <span className="text-xs text-muted-foreground">★ {repo.stargazers_count}</span>
                          )}
                          {repo.description && (
                            <span className="text-xs text-muted-foreground truncate">{repo.description}</span>
                          )}
                        </div>
                      </div>
                      <Button
                        size="sm"
                        variant={alreadyIngested ? "outline" : "default"}
                        disabled={disabled}
                        onClick={() => handleStart(repo)}
                        className="shrink-0 h-7 text-xs px-3"
                      >
                        {isStarting ? (
                          <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 00-8 8h4z" />
                          </svg>
                        ) : alreadyIngested ? "Synced" : alreadyIngesting ? "Syncing" : "Start"}
                      </Button>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}