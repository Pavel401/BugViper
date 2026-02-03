"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { BugViperLogo } from "@/components/logo";
import { getGraphStats } from "@/lib/api";

export default function Dashboard() {
  const [stats, setStats] = useState<Record<string, number> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getGraphStats()
      .then(setStats)
      .catch(() => setStats(null))
      .finally(() => setLoading(false));
  }, []);

  const statCards = [
    { label: "Repositories", key: "repositories", fallback: "total_repositories" },
    { label: "Files", key: "files", fallback: "total_files" },
    { label: "Functions", key: "functions", fallback: "total_functions" },
    { label: "Classes", key: "classes", fallback: "total_classes" },
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="flex flex-col items-center text-center space-y-4 py-8">
        <BugViperLogo size={80} />
        <h1 className="text-4xl font-bold">
          Bug<span className="text-primary">Viper</span>
        </h1>
        <p className="text-muted-foreground text-lg max-w-md">
          Code intelligence and repository analysis platform. Ingest repositories and query your codebase.
        </p>
      </div>

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
    </div>
  );
}
