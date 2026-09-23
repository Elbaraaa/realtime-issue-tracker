import { STATUSES } from "./types";
import type { Issue, Status } from "./types";

export const POSITION_GAP = 1024;

export function groupByStatus(issues: Issue[]): Record<Status, Issue[]> {
  const groups: Record<Status, Issue[]> = { todo: [], in_progress: [], in_review: [], done: [] };
  for (const issue of issues) groups[issue.status].push(issue);
  for (const column of Object.values(groups)) {
    column.sort((a, b) => a.position - b.position || a.number - b.number);
  }
  return groups;
}

/**
 * Position for a card dropped at `index` in `column` (the column as it looks without the
 * moving card). Uses the midpoint of its neighbours so only the moved card is rewritten.
 */
export function positionAt(column: Issue[], index: number, movingId: number): number {
  const others = column.filter((i) => i.id !== movingId);
  const before = others[index - 1]?.position;
  const after = others[index]?.position;
  if (before === undefined && after === undefined) return POSITION_GAP;
  if (before === undefined) return after! / 2;
  if (after === undefined) return before + POSITION_GAP;
  return (before + after) / 2;
}

export function matchesQuery(issue: Issue, projectKey: string, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return (
    issue.title.toLowerCase().includes(q) ||
    `${projectKey}-${issue.number}`.toLowerCase() === q ||
    (issue.assignee?.name.toLowerCase().includes(q) ?? false)
  );
}

export type MoveKey = "ArrowLeft" | "ArrowRight" | "ArrowUp" | "ArrowDown";

/**
 * Where a keyboard move sends a card: left/right to the end of the neighbouring column,
 * up/down one slot within its column. Returns null when the card is already at the edge.
 */
export function keyboardMove(
  columns: Record<Status, Issue[]>,
  issue: Issue,
  key: MoveKey,
): { status: Status; position: number } | null {
  const order = STATUSES.map((s) => s.value);
  const col = order.indexOf(issue.status);
  if (key === "ArrowLeft" || key === "ArrowRight") {
    const target = order[col + (key === "ArrowLeft" ? -1 : 1)];
    if (!target) return null;
    return { status: target, position: positionAt(columns[target], columns[target].length, issue.id) };
  }
  const column = columns[issue.status];
  const index = column.findIndex((i) => i.id === issue.id);
  // Index among the other cards: one earlier for up, one later for down.
  const target = key === "ArrowUp" ? index - 1 : index + 1;
  if (target < 0 || target > column.length - 1) return null;
  return { status: issue.status, position: positionAt(column, target, issue.id) };
}
