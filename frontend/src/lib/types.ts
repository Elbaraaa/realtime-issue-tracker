export type Status = "todo" | "in_progress" | "in_review" | "done";
export type Priority = "low" | "medium" | "high" | "urgent";

export const STATUSES: { value: Status; label: string }[] = [
  { value: "todo", label: "To do" },
  { value: "in_progress", label: "In progress" },
  { value: "in_review", label: "In review" },
  { value: "done", label: "Done" },
];

export const PRIORITIES: Priority[] = ["low", "medium", "high", "urgent"];

export interface User {
  id: number;
  email: string;
  name: string;
}

export interface Project {
  id: number;
  key: string;
  name: string;
  description: string;
  created_at: string;
}

export interface Member {
  user: User;
  role: "owner" | "member";
}

export interface Issue {
  id: number;
  project_id: number;
  number: number;
  title: string;
  description: string;
  status: Status;
  priority: Priority;
  assignee: User | null;
  reporter: User;
  position: number;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface IssuePage {
  items: Issue[];
  total: number;
}

export interface Comment {
  id: number;
  issue_id: number;
  author: User;
  body: string;
  created_at: string;
}

export interface Activity {
  id: number;
  issue_id: number | null;
  actor: User;
  kind: string;
  data: Record<string, unknown>;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  user: User;
}
