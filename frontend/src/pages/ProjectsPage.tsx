import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import type { Project } from "../lib/types";

export default function ProjectsPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => api<Project[]>("/projects") });
  const [key, setKey] = useState("");
  const [name, setName] = useState("");

  const create = useMutation({
    mutationFn: () => api<Project>("/projects", { method: "POST", json: { key, name } }),
    onSuccess: (project) => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      navigate(`/projects/${project.id}`);
    },
  });

  function submit(e: FormEvent) {
    e.preventDefault();
    create.mutate();
  }

  return (
    <div className="page">
      <h1>Projects</h1>
      {projects.isPending && <p className="muted">Loading…</p>}
      {projects.error && <p className="error">{projects.error.message}</p>}
      {projects.data?.length === 0 && <p className="muted">No projects yet. Create one below.</p>}
      <ul className="project-list">
        {projects.data?.map((p) => (
          <li key={p.id}>
            <Link to={`/projects/${p.id}`} className="card project-card">
              <span className="key">{p.key}</span>
              <span>{p.name}</span>
            </Link>
          </li>
        ))}
      </ul>

      <form className="card inline-form" onSubmit={submit}>
        <h2>New project</h2>
        <input
          placeholder="KEY"
          value={key}
          onChange={(e) => setKey(e.target.value.toUpperCase())}
          pattern="[A-Z][A-Z0-9]{1,9}"
          title="2–10 letters or digits, starting with a letter"
          required
          className="key-input"
        />
        <input placeholder="Project name" value={name} onChange={(e) => setName(e.target.value)} required />
        <button type="submit" disabled={create.isPending}>
          Create
        </button>
        {create.error && <p className="error">{create.error.message}</p>}
      </form>
    </div>
  );
}
