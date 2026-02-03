"use client";

import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import {
  listRepositories,
  deleteRepository,
  ingestGithub,
  ingestRepository,
} from "@/lib/api";

interface Repo {
  id: string;
  name?: string;
  repo_name?: string;
  owner?: string;
  username?: string;
  file_count?: number;
  language?: string;
  [key: string]: unknown;
}

export default function RepositoriesPage() {
  const [repos, setRepos] = useState<Repo[]>([]);
  const [loadingRepos, setLoadingRepos] = useState(true);
  const [ingesting, setIngesting] = useState(false);

  // GitHub form
  const [ghOwner, setGhOwner] = useState("");
  const [ghRepo, setGhRepo] = useState("");
  const [ghBranch, setGhBranch] = useState("");
  const [ghClear, setGhClear] = useState(false);

  // Local form
  const [localUrl, setLocalUrl] = useState("");
  const [localUsername, setLocalUsername] = useState("");
  const [localRepoName, setLocalRepoName] = useState("");
  const [localClear, setLocalClear] = useState(false);

  const loadRepos = useCallback(async () => {
    try {
      const data = await listRepositories();
      const raw: Repo[] = Array.isArray(data) ? data : data?.repositories ?? [];
      setRepos(raw.filter((r) => r.id));
    } catch {
      toast.error("Failed to load repositories");
    } finally {
      setLoadingRepos(false);
    }
  }, []);

  useEffect(() => {
    loadRepos();
  }, [loadRepos]);

  const handleGithubIngest = async () => {
    if (!ghOwner || !ghRepo) return;
    setIngesting(true);
    try {
      await ingestGithub({
        owner: ghOwner,
        repo_name: ghRepo,
        branch: ghBranch || undefined,
        clear_existing: ghClear,
      });
      toast.success("Repository ingested successfully");
      setGhOwner("");
      setGhRepo("");
      setGhBranch("");
      loadRepos();
    } catch (e) {
      toast.error(`Ingestion failed: ${e instanceof Error ? e.message : "Unknown error"}`);
    } finally {
      setIngesting(false);
    }
  };

  const handleLocalIngest = async () => {
    if (!localUrl || !localUsername || !localRepoName) return;
    setIngesting(true);
    try {
      await ingestRepository({
        repo_url: localUrl,
        username: localUsername,
        repo_name: localRepoName,
        clear_existing: localClear,
      });
      toast.success("Repository ingested successfully");
      setLocalUrl("");
      setLocalUsername("");
      setLocalRepoName("");
      loadRepos();
    } catch (e) {
      toast.error(`Ingestion failed: ${e instanceof Error ? e.message : "Unknown error"}`);
    } finally {
      setIngesting(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteRepository(id);
      toast.success("Repository deleted");
      loadRepos();
    } catch {
      toast.error("Failed to delete repository");
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <h1 className="text-2xl font-bold">Repositories</h1>

      {/* Ingest Section */}
      <Card>
        <CardHeader>
          <CardTitle>Ingest New Repository</CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="github">
            <TabsList>
              <TabsTrigger value="github">GitHub</TabsTrigger>
              <TabsTrigger value="local">Local Path</TabsTrigger>
            </TabsList>

            <TabsContent value="github" className="space-y-4 pt-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Owner</Label>
                  <Input placeholder="e.g. facebook" value={ghOwner} onChange={(e) => setGhOwner(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label>Repository Name</Label>
                  <Input placeholder="e.g. react" value={ghRepo} onChange={(e) => setGhRepo(e.target.value)} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Branch (optional)</Label>
                  <Input placeholder="main" value={ghBranch} onChange={(e) => setGhBranch(e.target.value)} />
                </div>
                <div className="flex items-center gap-2 pt-6">
                  <Switch checked={ghClear} onCheckedChange={setGhClear} />
                  <Label>Clear existing data</Label>
                </div>
              </div>
              <Button onClick={handleGithubIngest} disabled={ingesting || !ghOwner || !ghRepo}>
                {ingesting ? "Ingesting..." : "Ingest from GitHub"}
              </Button>
            </TabsContent>

            <TabsContent value="local" className="space-y-4 pt-4">
              <div className="space-y-2">
                <Label>Repository URL / Path</Label>
                <Input placeholder="/path/to/repo or https://..." value={localUrl} onChange={(e) => setLocalUrl(e.target.value)} />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Username</Label>
                  <Input placeholder="owner" value={localUsername} onChange={(e) => setLocalUsername(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label>Repository Name</Label>
                  <Input placeholder="my-repo" value={localRepoName} onChange={(e) => setLocalRepoName(e.target.value)} />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Switch checked={localClear} onCheckedChange={setLocalClear} />
                <Label>Clear existing data</Label>
              </div>
              <Button onClick={handleLocalIngest} disabled={ingesting || !localUrl || !localUsername || !localRepoName}>
                {ingesting ? "Ingesting..." : "Ingest Repository"}
              </Button>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* Repository List */}
      <Card>
        <CardHeader>
          <CardTitle>Ingested Repositories</CardTitle>
        </CardHeader>
        <CardContent>
          {loadingRepos ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : repos.length === 0 ? (
            <p className="text-muted-foreground text-sm">No repositories ingested yet.</p>
          ) : (
            <div className="space-y-3">
              {repos.map((repo) => (
                <div
                  key={repo.id}
                  className="flex items-center justify-between p-4 rounded-lg border border-border"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">
                        {repo.owner ?? repo.username}/{repo.name ?? repo.repo_name}
                      </span>
                      {repo.language && <Badge variant="secondary">{repo.language}</Badge>}
                    </div>
                    {repo.file_count != null && (
                      <p className="text-sm text-muted-foreground">{repo.file_count} files</p>
                    )}
                  </div>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => handleDelete(repo.id)}
                  >
                    Delete
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
