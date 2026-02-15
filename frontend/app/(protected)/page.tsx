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
 

}
