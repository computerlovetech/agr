#!/usr/bin/env python3
import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Iterable


SCHEMA = """
CREATE TABLE IF NOT EXISTS workspaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    data TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
);

CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id INTEGER NOT NULL,
    to_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (from_id) REFERENCES nodes(id),
    FOREIGN KEY (to_id) REFERENCES nodes(id)
);

CREATE INDEX IF NOT EXISTS idx_nodes_workspace_type ON nodes(workspace_id, type);
CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_id);
CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_id);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path) -> None:
    ensure_parent_dir(db_path)
    conn = connect(db_path)
    with conn:
        conn.executescript(SCHEMA)
    conn.close()


def load_json_arg(value: str | None) -> str:
    if value is None:
        return "{}"
    try:
        json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON for --data: {exc}")
    return value


def get_workspace_id(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute("SELECT id FROM workspaces WHERE name = ?", (name,)).fetchone()
    if row is None:
        raise ValueError(f"Workspace not found: {name}")
    return int(row["id"])


def create_workspace(conn: sqlite3.Connection, name: str) -> int:
    created_at = now_iso()
    cur = conn.execute(
        "INSERT INTO workspaces (name, created_at) VALUES (?, ?)",
        (name, created_at),
    )
    return _require_lastrowid(cur)


def add_node(
    conn: sqlite3.Connection,
    workspace_id: int,
    node_type: str,
    title: str,
    data: str,
) -> int:
    created_at = now_iso()
    cur = conn.execute(
        "INSERT INTO nodes (workspace_id, type, title, data, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (workspace_id, node_type, title, data, created_at, created_at),
    )
    return _require_lastrowid(cur)


def _require_lastrowid(cur: sqlite3.Cursor) -> int:
    lastrowid = cur.lastrowid
    if lastrowid is None:
        raise ValueError("Insert failed: no lastrowid returned")
    return int(lastrowid)


def update_node_data(conn: sqlite3.Connection, node_id: int, data: str) -> None:
    updated_at = now_iso()
    cur = conn.execute(
        "UPDATE nodes SET data = ?, updated_at = ? WHERE id = ?",
        (data, updated_at, node_id),
    )
    if cur.rowcount == 0:
        raise ValueError(f"Node not found: {node_id}")


def add_edge(
    conn: sqlite3.Connection, from_id: int, to_id: int, edge_type: str
) -> None:
    created_at = now_iso()
    conn.execute(
        "INSERT INTO edges (from_id, to_id, type, created_at) VALUES (?, ?, ?, ?)",
        (from_id, to_id, edge_type, created_at),
    )


def list_nodes(
    conn: sqlite3.Connection,
    workspace_id: int,
    node_type: str,
) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, title, data FROM nodes WHERE workspace_id = ? AND type = ? ORDER BY id",
        (workspace_id, node_type),
    ).fetchall()


def list_children(
    conn: sqlite3.Connection,
    parent_id: int,
    child_type: str,
    edge_type: str,
) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT n.id, n.title, n.data FROM nodes n "
        "JOIN edges e ON e.to_id = n.id "
        "WHERE e.from_id = ? AND e.type = ? AND n.type = ? "
        "ORDER BY n.id",
        (parent_id, edge_type, child_type),
    ).fetchall()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="ost", description="OST graph CLI")
    parser.add_argument("--path", default=".agr/ost.db", help="Path to OST SQLite DB")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Initialize database")

    ws = subparsers.add_parser("workspace", help="Workspace operations")
    ws_sub = ws.add_subparsers(dest="ws_cmd", required=True)
    ws_sub.add_parser("list", help="List workspaces")
    ws_create = ws_sub.add_parser("create", help="Create workspace")
    ws_create.add_argument("name")

    outcome = subparsers.add_parser("outcome", help="Outcome operations")
    outcome_sub = outcome.add_subparsers(dest="outcome_cmd", required=True)
    outcome_list = outcome_sub.add_parser("list", help="List outcomes")
    outcome_list.add_argument("--workspace", required=True)
    outcome_add = outcome_sub.add_parser("add", help="Add outcome")
    outcome_add.add_argument("--workspace", required=True)
    outcome_add.add_argument("title")
    outcome_add.add_argument("--data")
    outcome_update = outcome_sub.add_parser("update", help="Update outcome data")
    outcome_update.add_argument("--id", required=True, type=int)
    outcome_update.add_argument("--data", required=True)

    opportunity = subparsers.add_parser("opportunity", help="Opportunity operations")
    opp_sub = opportunity.add_subparsers(dest="opp_cmd", required=True)
    opp_list = opp_sub.add_parser("list", help="List opportunities")
    opp_list.add_argument("--outcome", required=True, type=int)
    opp_add = opp_sub.add_parser("add", help="Add opportunity")
    opp_add.add_argument("--outcome", required=True, type=int)
    opp_add.add_argument("title")
    opp_add.add_argument("--data")

    solution = subparsers.add_parser("solution", help="Solution operations")
    sol_sub = solution.add_subparsers(dest="sol_cmd", required=True)
    sol_list = sol_sub.add_parser("list", help="List solutions")
    sol_list.add_argument("--opportunity", required=True, type=int)
    sol_add = sol_sub.add_parser("add", help="Add solution")
    sol_add.add_argument("--opportunity", required=True, type=int)
    sol_add.add_argument("title")
    sol_add.add_argument("--data")

    assumption = subparsers.add_parser("assumption", help="Assumption operations")
    as_sub = assumption.add_subparsers(dest="ass_cmd", required=True)
    as_list = as_sub.add_parser("list", help="List assumptions")
    as_list.add_argument("--solution", required=True, type=int)
    as_add = as_sub.add_parser("add", help="Add assumption")
    as_add.add_argument("--solution", required=True, type=int)
    as_add.add_argument("title")
    as_add.add_argument("--data")

    show = subparsers.add_parser("show", help="Show OST subtree")
    show.add_argument("--outcome", required=True, type=int)

    return parser.parse_args()


def require_db(path: Path) -> None:
    if not path.exists():
        raise ValueError(f"Database not found at {path}. Run 'init' first.")


def print_rows(rows: Iterable[sqlite3.Row]) -> None:
    for row in rows:
        data = row["data"]
        print(f"{row['id']}: {row['title']} {data}")


def show_tree(conn: sqlite3.Connection, outcome_id: int) -> None:
    outcome = conn.execute(
        "SELECT id, title, data FROM nodes WHERE id = ? AND type = 'outcome'",
        (outcome_id,),
    ).fetchone()
    if outcome is None:
        raise ValueError(f"Outcome not found: {outcome_id}")

    print(f"Outcome {outcome['id']}: {outcome['title']} {outcome['data']}")
    opportunities = list_children(
        conn, outcome_id, "opportunity", "outcome_opportunity"
    )
    for opp in opportunities:
        print(f"  Opportunity {opp['id']}: {opp['title']} {opp['data']}")
        solutions = list_children(conn, opp["id"], "solution", "opportunity_solution")
        for sol in solutions:
            print(f"    Solution {sol['id']}: {sol['title']} {sol['data']}")
            assumptions = list_children(
                conn, sol["id"], "assumption", "solution_assumption"
            )
            for ass in assumptions:
                print(f"      Assumption {ass['id']}: {ass['title']} {ass['data']}")


def main() -> int:
    args = parse_args()
    db_path = Path(args.path)

    try:
        if args.command == "init":
            init_db(db_path)
            print(f"Initialized OST DB at {db_path}")
            return 0

        require_db(db_path)
        conn = connect(db_path)
        with conn:
            if args.command == "workspace":
                if args.ws_cmd == "list":
                    rows = conn.execute(
                        "SELECT id, name, created_at FROM workspaces ORDER BY name"
                    ).fetchall()
                    for row in rows:
                        print(f"{row['id']}: {row['name']} ({row['created_at']})")
                    return 0
                if args.ws_cmd == "create":
                    ws_id = create_workspace(conn, args.name)
                    print(f"Created workspace {args.name} (id {ws_id})")
                    return 0

            if args.command == "outcome":
                if args.outcome_cmd == "list":
                    ws_id = get_workspace_id(conn, args.workspace)
                    rows = list_nodes(conn, ws_id, "outcome")
                    print_rows(rows)
                    return 0
                if args.outcome_cmd == "add":
                    ws_id = get_workspace_id(conn, args.workspace)
                    data = load_json_arg(args.data)
                    node_id = add_node(conn, ws_id, "outcome", args.title, data)
                    print(f"Created outcome {node_id}")
                    return 0
                if args.outcome_cmd == "update":
                    data = load_json_arg(args.data)
                    update_node_data(conn, args.id, data)
                    print(f"Updated outcome {args.id}")
                    return 0

            if args.command == "opportunity":
                if args.opp_cmd == "list":
                    rows = list_children(
                        conn, args.outcome, "opportunity", "outcome_opportunity"
                    )
                    print_rows(rows)
                    return 0
                if args.opp_cmd == "add":
                    data = load_json_arg(args.data)
                    outcome = conn.execute(
                        "SELECT workspace_id FROM nodes WHERE id = ? AND type = 'outcome'",
                        (args.outcome,),
                    ).fetchone()
                    if outcome is None:
                        raise ValueError(f"Outcome not found: {args.outcome}")
                    node_id = add_node(
                        conn,
                        int(outcome["workspace_id"]),
                        "opportunity",
                        args.title,
                        data,
                    )
                    add_edge(conn, args.outcome, node_id, "outcome_opportunity")
                    print(f"Created opportunity {node_id}")
                    return 0

            if args.command == "solution":
                if args.sol_cmd == "list":
                    rows = list_children(
                        conn, args.opportunity, "solution", "opportunity_solution"
                    )
                    print_rows(rows)
                    return 0
                if args.sol_cmd == "add":
                    data = load_json_arg(args.data)
                    opp = conn.execute(
                        "SELECT workspace_id FROM nodes WHERE id = ? AND type = 'opportunity'",
                        (args.opportunity,),
                    ).fetchone()
                    if opp is None:
                        raise ValueError(f"Opportunity not found: {args.opportunity}")
                    node_id = add_node(
                        conn, int(opp["workspace_id"]), "solution", args.title, data
                    )
                    add_edge(conn, args.opportunity, node_id, "opportunity_solution")
                    print(f"Created solution {node_id}")
                    return 0

            if args.command == "assumption":
                if args.ass_cmd == "list":
                    rows = list_children(
                        conn, args.solution, "assumption", "solution_assumption"
                    )
                    print_rows(rows)
                    return 0
                if args.ass_cmd == "add":
                    data = load_json_arg(args.data)
                    sol = conn.execute(
                        "SELECT workspace_id FROM nodes WHERE id = ? AND type = 'solution'",
                        (args.solution,),
                    ).fetchone()
                    if sol is None:
                        raise ValueError(f"Solution not found: {args.solution}")
                    node_id = add_node(
                        conn, int(sol["workspace_id"]), "assumption", args.title, data
                    )
                    add_edge(conn, args.solution, node_id, "solution_assumption")
                    print(f"Created assumption {node_id}")
                    return 0

            if args.command == "show":
                show_tree(conn, args.outcome)
                return 0

        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
