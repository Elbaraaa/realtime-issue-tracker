import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import type { DragEvent, FormEvent } from "react";
import { useParams } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import { groupByStatus, matchesQuery, positionAt } from "../lib/board";
import { PRIORITIES, STATUSES } from "../lib/types";
import { useProjectEvents } from "../lib/useProjectEvents";
import type { Issue, IssuePage, Member, Priority, Project, Status } from "../lib/types";
import IssuePanel from "./IssuePanel";

export default function BoardPage() {
  const projectId = Number(useParams().projectId);
  const qc = useQueryClient();
  const issuesKey = ["project", projectId, "issues"];

  const project = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api<Project>(`/projects/${projectId}`),
  });
  const issues = useQuery({
    queryKey: issuesKey,
    queryFn: () => api<IssuePage>(`/projects/${projectId}/issues?limit=500`),
  });
  const members = useQuery({
    queryKey: ["project", projectId, "members"],
    queryFn: () => api<Member[]>(`/projects/${projectId}/members`),
  });

  const [query, setQuery] = useState("");
  const [openId, setOpenId] = useState<number | null>(null);
  const [dragging, setDragging] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const live = useProjectEvents(projectId, {
    onReady: () => qc.invalidateQueries({ queryKey: ["project", projectId] }),
    onEvent: (event) => {
      qc.invalidateQueries({ queryKey: issuesKey });
      if (event.kind.startsWith("member_")) {
        qc.invalidateQueries({ queryKey: ["project", projectId, "members"] });
      }
      if (event.issue_id !== null) qc.invalidateQueries({ queryKey: ["issue", event.issue_id] });
    },
  });

  const columns = useMemo(() => {
    const key = project.data?.key ?? "";
    return groupByStatus((issues.data?.items ?? []).filter((i) => matchesQuery(i, key, query)));
  }, [issues.data, project.data, query]);

  const move = useMutation({
    mutationFn: ({ issue, status, position }: { issue: Issue; status: Status; position: number }) =>
      api<Issue>(`/issues/${issue.id}`, {
        method: "PATCH",
        json: { version: issue.version, status, position },
      }),
    onMutate: async ({ issue, status, position }) => {
      // Move the card immediately; roll back if the server disagrees.
      await qc.cancelQueries({ queryKey: issuesKey });
      const previous = qc.getQueryData<IssuePage>(issuesKey);
      qc.setQueryData<IssuePage>(issuesKey, (page) =>
        page && {
          ...page,
          items: page.items.map((i) => (i.id === issue.id ? { ...i, status, position } : i)),
        },
      );
      return { previous };
    },
    onError: (err, _vars, ctx) => {
      if (ctx?.previous) qc.setQueryData(issuesKey, ctx.previous);
      setNotice(
        err instanceof ApiError && err.status === 409
          ? "Someone else just changed that issue — the board has been refreshed."
          : err.message,
      );
    },
    onSettled: () => qc.invalidateQueries({ queryKey: issuesKey }),
  });

  function onDrop(e: DragEvent, status: Status, index: number) {
    e.preventDefault();
    e.stopPropagation();
    const issue = issues.data?.items.find((i) => i.id === dragging);
    setDragging(null);
    if (!issue) return;
    const position = positionAt(columns[status], index, issue.id);
    if (issue.status === status && issue.position === position) return;
    move.mutate({ issue, status, position });
  }

  if (project.error) return <p className="error page">{project.error.message}</p>;
  if (!project.data) return <p className="muted page">Loading…</p>;

  return (
    <div className="board-page">
      <div className="board-header">
        <div>
          <h1>
            <span className="key">{project.data.key}</span> {project.data.name}
          </h1>
          <p className="muted">
            {issues.data?.total ?? 0} issues ·{" "}
            <span className={live ? "live on" : "live"}>{live ? "Live" : "Reconnecting…"}</span>
          </p>
        </div>
        <input
          className="search"
          placeholder="Filter by title, key, or assignee"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {notice && (
        <p className="notice" role="status">
          {notice}{" "}
          <button className="link" onClick={() => setNotice(null)}>
            Dismiss
          </button>
        </p>
      )}

      <NewIssueForm projectId={projectId} members={members.data ?? []} />

      <div className="board">
        {STATUSES.map(({ value, label }) => (
          <section
            key={value}
            className="column"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => onDrop(e, value, columns[value].length)}
          >
            <h2>
              {label} <span className="count">{columns[value].length}</span>
            </h2>
            {columns[value].map((issue, index) => (
              <article
                key={issue.id}
                className={`card issue-card${dragging === issue.id ? " dragging" : ""}`}
                draggable
                onDragStart={() => setDragging(issue.id)}
                onDragEnd={() => setDragging(null)}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => onDrop(e, value, index)}
                onClick={() => setOpenId(issue.id)}
              >
                <span className="muted small">
                  {project.data.key}-{issue.number}
                </span>
                <p>{issue.title}</p>
                <div className="issue-meta">
                  <span className={`priority ${issue.priority}`}>{issue.priority}</span>
                  {issue.assignee && (
                    <span className="avatar" title={issue.assignee.name}>
                      {initials(issue.assignee.name)}
                    </span>
                  )}
                </div>
              </article>
            ))}
          </section>
        ))}
      </div>

      <MembersPanel projectId={projectId} members={members.data ?? []} />

      {openId !== null && (
        <IssuePanel
          issueId={openId}
          projectKey={project.data.key}
          members={members.data ?? []}
          onClose={() => setOpenId(null)}
        />
      )}
    </div>
  );
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function NewIssueForm({ projectId, members }: { projectId: number; members: Member[] }) {
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [priority, setPriority] = useState<Priority>("medium");
  const [assignee, setAssignee] = useState("");

  const create = useMutation({
    mutationFn: () =>
      api<Issue>(`/projects/${projectId}/issues`, {
        method: "POST",
        json: { title, priority, assignee_id: assignee ? Number(assignee) : null },
      }),
    onSuccess: () => {
      setTitle("");
      qc.invalidateQueries({ queryKey: ["project", projectId, "issues"] });
    },
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    create.mutate();
  }

  return (
    <form className="card inline-form" onSubmit={submit}>
      <input
        placeholder="What needs doing?"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        maxLength={200}
        required
        className="grow"
      />
      <select value={priority} onChange={(e) => setPriority(e.target.value as Priority)}>
        {PRIORITIES.map((p) => (
          <option key={p} value={p}>
            {p}
          </option>
        ))}
      </select>
      <select value={assignee} onChange={(e) => setAssignee(e.target.value)}>
        <option value="">Unassigned</option>
        {members.map((m) => (
          <option key={m.user.id} value={m.user.id}>
            {m.user.name}
          </option>
        ))}
      </select>
      <button type="submit" disabled={create.isPending}>
        Add issue
      </button>
      {create.error && <p className="error">{create.error.message}</p>}
    </form>
  );
}

function MembersPanel({ projectId, members }: { projectId: number; members: Member[] }) {
  const qc = useQueryClient();
  const [email, setEmail] = useState("");
  const invite = useMutation({
    mutationFn: () =>
      api<Member>(`/projects/${projectId}/members`, { method: "POST", json: { email } }),
    onSuccess: () => {
      setEmail("");
      qc.invalidateQueries({ queryKey: ["project", projectId, "members"] });
    },
  });

  return (
    <details className="card members">
      <summary>Members ({members.length})</summary>
      <ul>
        {members.map((m) => (
          <li key={m.user.id}>
            {m.user.name} <span className="muted small">{m.user.email}</span>
            {m.role === "owner" && <span className="tag">owner</span>}
          </li>
        ))}
      </ul>
      <form
        className="inline-form"
        onSubmit={(e) => {
          e.preventDefault();
          invite.mutate();
        }}
      >
        <input
          type="email"
          placeholder="Invite by email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <button type="submit" disabled={invite.isPending}>
          Add
        </button>
        {invite.error && <p className="error">{invite.error.message}</p>}
      </form>
    </details>
  );
}
