"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { BugViperFullLogo } from "@/components/logo";
import { getGraphStats, getGitHubRepos, type GitHubRepo } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export default function Dashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState<Record<string, number> | null>(null);
  const [loading, setLoading] = useState(true);
  const [repos, setRepos] = useState<GitHubRepo[]>([]);
  const [reposLoading, setReposLoading] = useState(true);

  useEffect(() => {
    getGraphStats()
      .then(setStats)
      .catch(() => setStats(null))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    getGitHubRepos()
      .then((data) => { if (!cancelled) setRepos(data); })
      .catch(() => { if (!cancelled) setRepos([]); })
      .finally(() => { if (!cancelled) setReposLoading(false); });
    return () => { cancelled = true; };
  }, [user]);

  const statCards = [
    { label: "Repositories", key: "repositories", fallback: "total_repositories" },
    { label: "Files", key: "files", fallback: "total_files" },
    { label: "Functions", key: "functions", fallback: "total_functions" },
    { label: "Classes", key: "classes", fallback: "total_classes" },
  ];

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      {/* Greeting */}
      <div className="flex items-center gap-4 py-4">
        {user?.photoURL ? (
          <img
            src={user.photoURL}
            alt=""
            className="w-12 h-12 rounded-full"
            referrerPolicy="no-referrer"
          />
        ) : (
          <div className="w-12 h-12 rounded-full bg-primary/20 flex items-center justify-center text-lg font-medium text-primary">
            {(user?.displayName?.[0] || "?").toUpperCase()}
          </div>
        )}
        <div>
          <h1 className="text-2xl font-bold">
            Welcome back, {user?.displayName || "there"}
          </h1>
          <p className="text-muted-foreground">
            Here&apos;s an overview of your codebase
          </p>
        </div>
      </div>

      {/* Logo + description */}
      <div className="flex flex-col items-center text-center space-y-4 py-4">
        <BugViperFullLogo width={350} height={100} />
        <p className="text-muted-foreground text-lg max-w-md">
          Code intelligence and repository analysis platform. Ingest repositories and query your codebase.
        </p>
      </div>

      {/* Graph stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {statCards.map((s) => (
          <Card key={s.key}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">{s.label}</CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <Skeleton className="h-8 w-16" />
              ) : (
                <p className="text-2xl font-bold text-primary">
                  {stats?.[s.key] ?? stats?.[s.fallback] ?? 0}
                </p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex gap-4 justify-center">
        <Button asChild>
          <Link href="/repositories">Ingest Repository</Link>
        </Button>
        <Button variant="secondary" asChild>
          <Link href="/query">Query Code</Link>
        </Button>
      </div>

      {/* GitHub repos */}
      <div className="space-y-4">
        <h2 className="text-xl font-semibold">Your GitHub Repositories</h2>
        {reposLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-36 w-full" />
            ))}
          </div>
        ) : repos.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-muted-foreground">
              No repositories found. Your GitHub repos will appear here after sign-in.
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {repos.map((repo) => (
              <Card key={repo.full_name} className="flex flex-col">
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between gap-2">
                    <CardTitle className="text-base font-semibold truncate">
                      {repo.name}
                    </CardTitle>
                    <Badge variant={repo.private ? "secondary" : "outline"}>
                      {repo.private ? "Private" : "Public"}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="flex-1 flex flex-col justify-between gap-3">
                  <p className="text-sm text-muted-foreground line-clamp-2">
                    {repo.description || "No description"}
                  </p>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3 text-sm text-muted-foreground">
                      {repo.language && (
                        <span className="flex items-center gap-1">
                          <span className="w-2.5 h-2.5 rounded-full bg-primary inline-block" />
                          {repo.language}
                        </span>
                      )}
                      {repo.stargazers_count > 0 && (
                        <span className="flex items-center gap-1">
                          <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M12 .587l3.668 7.431L24 9.168l-6 5.848L19.335 24 12 20.013 4.665 24 6 15.016 0 9.168l8.332-1.15z" />
                          </svg>
                          {repo.stargazers_count}
                        </span>
                      )}
                    </div>
                    <Button variant="outline" size="sm" asChild>
                      <Link
                        href={`/repositories?url=${encodeURIComponent(repo.html_url)}`}
                      >
                        Ingest
                      </Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
