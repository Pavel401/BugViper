"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import {
  listRepositories,
  deleteRepository,
  ingestGithub,
  getRepositoryStats,
  type RepositoryStatsResponse,
  type RepositoryStatistics,
} from "@/lib/api";

interface Repository {
  id: string;
  name?: string;
  repo_name?: string;
  owner?: string;
  username?: string;
}

export default function RepositoriesPage() {
  // Repository list state
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [isLoadingRepos, setIsLoadingRepos] = useState(true);

  // Stats state
  const [repoStats, setRepoStats] = useState<Record<string, RepositoryStatistics>>({});
  const [loadingStats, setLoadingStats] = useState<Record<string, boolean>>({});

  // Ingestion form state
  const [githubUrl, setGithubUrl] = useState("");
  const [owner, setOwner] = useState("");
  const [repoName, setRepoName] = useState("");
  const [branch, setBranch] = useState("");
  const [clearExisting, setClearExisting] = useState(false);
  const [isIngesting, setIsIngesting] = useState(false);

  // Parse GitHub URL to extract owner and repo
  function parseGithubUrl(url: string): { owner: string; repo: string } | null {
    try {
      const cleanUrl = url.trim().replace(".git", "");
      const match = cleanUrl.match(/github\.com\/([^/]+)\/([^/]+)/i);
      if (!match) return null;
      return { owner: match[1], repo: match[2] };
    } catch {
      return null;
    }
  }

  // Fetch repository statistics
  async function fetchRepositoryStats(repo: Repository) {
    const repoOwner = repo.owner ?? repo.username;
    const repoNameVal = repo.name ?? repo.repo_name;

    if (!repoOwner || !repoNameVal) {
      console.warn("Missing owner or name for repo:", repo);
      return;
    }

    const key = repo.id;
    console.log(`📊 Fetching stats for: ${repoOwner}/${repoNameVal}`);

    setLoadingStats((prev) => ({ ...prev, [key]: true }));

    try {
      const response: RepositoryStatsResponse = await getRepositoryStats(
        repoOwner,
        repoNameVal
      );
      console.log(`✅ Stats loaded for ${repoOwner}/${repoNameVal}:`, response);

      setRepoStats((prev) => ({
        ...prev,
        [key]: response.statistics,
      }));
    } catch (error) {
      console.error(`❌ Failed to load stats for ${repoOwner}/${repoNameVal}:`, error);
      toast.error(`Failed to load stats for ${repoOwner}/${repoNameVal}`);
    } finally {
      setLoadingStats((prev) => ({ ...prev, [key]: false }));
    }
  }

  // Load all repositories and their stats
  async function loadRepositories() {
    setIsLoadingRepos(true);
    try {
      const data = await listRepositories();
      const repoList: Repository[] = Array.isArray(data) ? data : data?.repositories ?? [];

      console.log(`📚 Loaded ${repoList.length} repositories:`, repoList);
      setRepositories(repoList);

      // Fetch stats for each repository
      for (const repo of repoList) {
        fetchRepositoryStats(repo);
      }
    } catch (error) {
      console.error("❌ Failed to load repositories:", error);
      toast.error("Failed to load repositories");
    } finally {
      setIsLoadingRepos(false);
    }
  }

  // Handle GitHub repository ingestion
  async function handleIngest() {
    let finalOwner = owner;
    let finalRepo = repoName;

    // If URL is provided, parse it
    if (githubUrl) {
      const parsed = parseGithubUrl(githubUrl);
      if (!parsed) {
        toast.error("Invalid GitHub URL");
        return;
      }
      finalOwner = parsed.owner;
      finalRepo = parsed.repo;
    }

    if (!finalOwner || !finalRepo) {
      toast.error("Please provide owner and repository name");
      return;
    }

    setIsIngesting(true);
    try {
      await ingestGithub({
        owner: finalOwner,
        repo_name: finalRepo,
        branch: branch || undefined,
        clear_existing: clearExisting,
      });

      toast.success(`Successfully ingested ${finalOwner}/${finalRepo}`);

      // Reset form
      setGithubUrl("");
      setOwner("");
      setRepoName("");
      setBranch("");
      setClearExisting(false);

      // Reload repositories
      loadRepositories();
    } catch (error) {
      console.error("❌ Ingestion failed:", error);
      toast.error(
        `Ingestion failed: ${error instanceof Error ? error.message : "Unknown error"}`
      );
    } finally {
      setIsIngesting(false);
    }
  }

  // Handle repository deletion
  async function handleDelete(repoId: string) {
    if (!confirm("Are you sure you want to delete this repository?")) {
      return;
    }

    try {
      await deleteRepository(repoId);
      toast.success("Repository deleted successfully");
      loadRepositories();
    } catch (error) {
      console.error("❌ Failed to delete repository:", error);
      toast.error("Failed to delete repository");
    }
  }

  // Load repositories on mount
  useEffect(() => {
    loadRepositories();
  }, []);

  return (
    <div className="container py-8 space-y-6 max-w-6xl mx-auto">
      <div>
        <h1 className="text-3xl font-bold">Repositories</h1>
        <p className="text-muted-foreground mt-2">
          Manage and ingest repositories for code analysis
        </p>
      </div>

      {/* Ingestion Form */}
      <Card>
        <CardHeader>
          <CardTitle>Ingest GitHub Repository</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* GitHub URL Input */}
          <div className="space-y-2">
            <Label htmlFor="github-url">GitHub Repository URL</Label>
            <Input
              id="github-url"
              placeholder="https://github.com/owner/repository"
              value={githubUrl}
              onChange={(e) => setGithubUrl(e.target.value)}
              disabled={isIngesting}
            />
          </div>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-background px-2 text-muted-foreground">Or</span>
            </div>
          </div>

          {/* Manual Owner/Repo Input */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="owner">Owner</Label>
              <Input
                id="owner"
                placeholder="Pavel401"
                value={owner}
                onChange={(e) => setOwner(e.target.value)}
                disabled={isIngesting}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="repo-name">Repository Name</Label>
              <Input
                id="repo-name"
                placeholder="FinanceBro"
                value={repoName}
                onChange={(e) => setRepoName(e.target.value)}
                disabled={isIngesting}
              />
            </div>
          </div>

          {/* Branch Input */}
          <div className="space-y-2">
            <Label htmlFor="branch">Branch (optional)</Label>
            <Input
              id="branch"
              placeholder="main"
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
              disabled={isIngesting}
            />
          </div>

          {/* Clear Existing Switch */}
          <div className="flex items-center gap-2">
            <Switch
              id="clear-existing"
              checked={clearExisting}
              onCheckedChange={setClearExisting}
              disabled={isIngesting}
            />
            <Label htmlFor="clear-existing">Clear existing data</Label>
          </div>

          {/* Ingest Button */}
          <Button
            onClick={handleIngest}
            disabled={isIngesting || (!githubUrl && (!owner || !repoName))}
            className="w-full"
          >
            {isIngesting ? "Ingesting..." : "Ingest Repository"}
          </Button>
        </CardContent>
      </Card>

      {/* Repository List */}
      <Card>
        <CardHeader>
          <CardTitle>Your Repositories ({repositories.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoadingRepos ? (
            <div className="space-y-4">
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-24 w-full" />
            </div>
          ) : repositories.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <p>No repositories found</p>
              <p className="text-sm mt-2">Ingest a repository to get started</p>
            </div>
          ) : (
            <div className="space-y-4">
              {repositories.map((repo) => {
                const repoOwner = repo.owner ?? repo.username;
                const repoNameVal = repo.name ?? repo.repo_name;
                const stats = repoStats[repo.id];
                const isLoadingStats = loadingStats[repo.id];

                return (
                  <div
                    key={repo.id}
                    className="flex items-start justify-between p-4 rounded-lg border bg-card hover:bg-accent/50 transition-colors"
                  >
                    <div className="space-y-3 flex-1">
                      {/* Repository Name */}
                      <div>
                        <h3 className="font-semibold text-lg">
                          {repoOwner}/{repoNameVal}
                        </h3>
                        <p className="text-sm text-muted-foreground">{repo.id}</p>
                      </div>

                      {/* Statistics */}
                      {isLoadingStats ? (
                        <Skeleton className="h-8 w-full max-w-md" />
                      ) : stats ? (
                        <div className="flex flex-wrap gap-2">
                          <Badge variant="outline" className="gap-1">
                            <span>📁</span>
                            <span>{stats.files.toLocaleString()} files</span>
                          </Badge>
                          <Badge variant="outline" className="gap-1">
                            <span>🧱</span>
                            <span>{stats.classes.toLocaleString()} classes</span>
                          </Badge>
                          <Badge variant="outline" className="gap-1">
                            <span>⚙️</span>
                            <span>{stats.functions.toLocaleString()} functions</span>
                          </Badge>
                          <Badge variant="outline" className="gap-1">
                            <span>📏</span>
                            <span>{stats.lines.toLocaleString()} lines</span>
                          </Badge>
                          {stats.languages && stats.languages.length > 0 && (
                            <>
                              {stats.languages.map((lang) => (
                                <Badge key={lang} variant="secondary">
                                  {lang}
                                </Badge>
                              ))}
                            </>
                          )}
                        </div>
                      ) : (
                        <p className="text-sm text-muted-foreground">
                          Stats not available
                        </p>
                      )}
                    </div>

                    {/* Delete Button */}
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => handleDelete(repo.id)}
                    >
                      Delete
                    </Button>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
