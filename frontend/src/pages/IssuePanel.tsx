import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { PRIORITIES, STATUSES } from "../lib/types";
import type { Activity, Comment, Issue, Member } from "../lib/types";

interface Props {
  issueId: number;
  projectKey: string;
  members: Member[];
  onClose: () => void;
}

export default function IssuePanel({ issueId, projectKey, members, onClose }: Props) {
  const qc = useQueryClient();
  const issue = useQuery({ queryKey: ["issue", issueId], queryFn: () => api<Issue>(`/issues/${issueId}`) });
  const comments = useQuery({
    queryKey: ["issue", issueId, "comments"],
    queryFn: () => api<Comment[]>(`/issues/${issueId}/comments`),
  });
  const activity = useQuery({
    queryKey: ["issue", issueId, "activity"],
    queryFn: () => api<Activity[]>(`/issues/${issueId}/activity`),
  });

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [comment, setComment] = useState("");

  useEffect(() => {
    if (issue.data) {
      setTitle(issue.data.title);
      setDescription(issue.data.description);
    }
  }, [issue.data]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["issue", issueId] });
    if (issue.data) qc.invalidateQueries({ queryKey: ["project", issue.data.project_id, "issues"] });
  };

  const update = useMutation({
    mutationFn: (changes: Partial<Issue> & { assignee_id?: number | null }) =>
      api<Issue>(`/issues/${issueId}`, {
        method: "PATCH",
        json: { version: issue.data!.version, ...changes },
      }),
    onSuccess: (updated) => qc.setQueryData(["issue", issueId], updated),
    onSettled: refresh,
  });

  const addComment = useMutation({
    mutationFn: () =>
      api<Comment>(`/issues/${issueId}/comments`, { method: "POST", json: { body: comment } }),
    onSuccess: () => {
      setComment("");
      refresh();
    },
  });

  const remove = useMutation({
    mutationFn: () => api<void>(`/issues/${issueId}`, { method: "DELETE" }),
    onSuccess: () => {
      refresh();
      onClose();
    },
  });

  const data = issue.data;
  const dirty = data && (title !== data.title || description !== data.description);
  const error = update.error ?? addComment.error ?? remove.error;

  return (
    <div className="overlay" onClick={onClose}>
      <aside className="panel" onClick={(e) => e.stopPropagation()} aria-label="Issue details">
        <div className="panel-head">
          <span className="muted">{data ? `${projectKey}-${data.number}` : "…"}</span>
          <button className="ghost" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        {!data ? (
          <p className="muted">Loading…</p>
        ) : (
          <>
            <input className="title-input" value={title} onChange={(e) => setTitle(e.target.value)} />
            <div className="fields">
              <label>
                Status
                <select
                  value={data.status}
                  onChange={(e) => update.mutate({ status: e.target.value as Issue["status"] })}
                >
                  {STATUSES.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Priority
                <select
                  value={data.priority}
                  onChange={(e) => update.mutate({ priority: e.target.value as Issue["priority"] })}
                >
                  {PRIORITIES.map((p) => (
                    <option key={p}>{p}</option>
                  ))}
                </select>
              </label>
              <label>
                Assignee
                <select
                  value={data.assignee?.id ?? ""}
                  onChange={(e) =>
                    update.mutate({ assignee_id: e.target.value ? Number(e.target.value) : null })
                  }
                >
                  <option value="">Unassigned</option>
                  {members.map((m) => (
                    <option key={m.user.id} value={m.user.id}>
                      {m.user.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <textarea
              placeholder="Add a description…"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={6}
            />
            <div className="row">
              <button disabled={!dirty || update.isPending} onClick={() => update.mutate({ title, description })}>
                Save
              </button>
              <button className="danger ghost" onClick={() => confirm("Delete this issue?") && remove.mutate()}>
                Delete
              </button>
            </div>
            {error && <p className="error">{error.message}</p>}

            <h3>Comments</h3>
            <ul className="comments">
              {comments.data?.map((c) => (
                <li key={c.id}>
                  <strong>{c.author.name}</strong>{" "}
                  <time className="muted small">{new Date(c.created_at).toLocaleString()}</time>
                  <p>{c.body}</p>
                </li>
              ))}
            </ul>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                addComment.mutate();
              }}
            >
              <textarea
                placeholder="Write a comment"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={3}
                required
              />
              <button type="submit" disabled={addComment.isPending}>
                Comment
              </button>
            </form>

            <h3>Activity</h3>
            <ol className="activity">
              {activity.data?.map((a) => (
                <li key={a.id}>
                  <strong>{a.actor.name}</strong> {describe(a)}{" "}
                  <time className="muted small">{new Date(a.created_at).toLocaleString()}</time>
                </li>
              ))}
            </ol>
          </>
        )}
      </aside>
    </div>
  );
}

function label(value: unknown): string {
  return STATUSES.find((s) => s.value === value)?.label ?? String(value);
}

function describe(a: Activity): string {
  if (a.kind === "issue_created") return "created this issue";
  if (a.kind === "comment_added") return "commented";
  if (a.kind === "issue_updated") {
    const changes = (a.data.changes ?? {}) as Record<string, { from: unknown; to: unknown }>;
    const parts = Object.entries(changes)
      .filter(([field]) => field !== "position")
      .map(([field, c]) => {
        if (field === "description") return "edited the description";
        if (field === "assignee_id") return c.to === null ? "unassigned it" : "changed the assignee";
        return `changed ${field} from ${label(c.from)} to ${label(c.to)}`;
      });
    return parts.length ? parts.join(", ") : "reordered it";
  }
  return a.kind.replace(/_/g, " ");
}
