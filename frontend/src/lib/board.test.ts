import { describe, expect, it } from "vitest";
import { groupByStatus, keyboardMove, matchesQuery, POSITION_GAP, positionAt } from "./board";
import type { Issue } from "./types";

const user = { id: 1, email: "a@example.com", name: "Ada" };

function issue(id: number, position: number, extra: Partial<Issue> = {}): Issue {
  return {
    id,
    project_id: 1,
    number: id,
    title: `Issue ${id}`,
    description: "",
    status: "todo",
    priority: "medium",
    assignee: null,
    reporter: user,
    position,
    version: 1,
    created_at: "",
    updated_at: "",
    ...extra,
  };
}

describe("groupByStatus", () => {
  it("buckets by status and sorts by position", () => {
    const groups = groupByStatus([issue(1, 3000), issue(2, 1000), issue(3, 5, { status: "done" })]);
    expect(groups.todo.map((i) => i.id)).toEqual([2, 1]);
    expect(groups.done.map((i) => i.id)).toEqual([3]);
    expect(groups.in_progress).toEqual([]);
  });
});

describe("positionAt", () => {
  const column = [issue(1, 1000), issue(2, 2000), issue(3, 3000)];

  it("drops into an empty column", () => {
    expect(positionAt([], 0, 9)).toBe(POSITION_GAP);
  });

  it("drops at the top, middle, and end", () => {
    expect(positionAt(column, 0, 9)).toBe(500);
    expect(positionAt(column, 1, 9)).toBe(1500);
    expect(positionAt(column, 3, 9)).toBe(3000 + POSITION_GAP);
  });

  it("ignores the moving card when reordering within a column", () => {
    // Moving card 1 to sit between 2 and 3.
    expect(positionAt(column, 1, 1)).toBe(2500);
  });
});

describe("matchesQuery", () => {
  const i = issue(12, 0, { title: "Fix login", assignee: { ...user, name: "Grace" } });

  it("matches title, exact key, and assignee", () => {
    expect(matchesQuery(i, "WEB", "")).toBe(true);
    expect(matchesQuery(i, "WEB", "LOGIN")).toBe(true);
    expect(matchesQuery(i, "WEB", "web-12")).toBe(true);
    expect(matchesQuery(i, "WEB", "web-1")).toBe(false);
    expect(matchesQuery(i, "WEB", "grace")).toBe(true);
  });
});

describe("keyboardMove", () => {
  const todo = [issue(1, 1000), issue(2, 2000), issue(3, 3000)];
  const inProgress = [issue(4, 1000, { status: "in_progress" })];
  const columns = groupByStatus([...todo, ...inProgress]);

  it("moves right to the end of the next column", () => {
    expect(keyboardMove(columns, todo[0], "ArrowRight")).toEqual({
      status: "in_progress",
      position: 1000 + POSITION_GAP,
    });
  });

  it("stops at the first and last columns", () => {
    expect(keyboardMove(columns, todo[0], "ArrowLeft")).toBeNull();
    const done = issue(5, 1000, { status: "done" });
    expect(keyboardMove(groupByStatus([done]), done, "ArrowRight")).toBeNull();
  });

  it("moves up and down one slot", () => {
    // Card 2 up: lands before card 1.
    expect(keyboardMove(columns, todo[1], "ArrowUp")).toEqual({ status: "todo", position: 500 });
    // Card 2 down: lands between cards 3 and the end.
    expect(keyboardMove(columns, todo[1], "ArrowDown")).toEqual({
      status: "todo",
      position: 3000 + POSITION_GAP,
    });
    // Card 1 down: lands between cards 2 and 3.
    expect(keyboardMove(columns, todo[0], "ArrowDown")).toEqual({ status: "todo", position: 2500 });
  });

  it("stops at the top and bottom of a column", () => {
    expect(keyboardMove(columns, todo[0], "ArrowUp")).toBeNull();
    expect(keyboardMove(columns, todo[2], "ArrowDown")).toBeNull();
  });
});
