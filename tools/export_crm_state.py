from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = ROOT / "data" / "discador.db"
DEFAULT_OUTPUT = ROOT / "handoff" / "crm-state.json"
EXPORTED_TABLES = ("contacts", "call_logs", "contact_events")


def rows(connection: sqlite3.Connection, query: str) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(query).fetchall()]


def export_state(database: Path, output: Path) -> dict[str, Any]:
    if not database.is_file():
        raise FileNotFoundError(f"Banco não encontrado: {database}")

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        schema = rows(
            connection,
            """
            SELECT type, name, tbl_name, sql
            FROM sqlite_master
            WHERE sql IS NOT NULL
              AND name NOT LIKE 'sqlite_%'
              AND (
                (type = 'table' AND name IN ('contacts', 'call_logs', 'contact_events', 'settings'))
                OR (type = 'index' AND tbl_name IN ('contacts', 'call_logs', 'contact_events'))
              )
            ORDER BY CASE type WHEN 'table' THEN 0 ELSE 1 END, name
            """,
        )
        data = {
            table: rows(connection, f"SELECT * FROM {table} ORDER BY id")
            for table in EXPORTED_TABLES
        }
    finally:
        connection.close()

    payload: dict[str, Any] = {
        "format": "callcentercesar-crm-state",
        "version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_database": str(database),
        "notice": (
            "Exportação solicitada para migração. Contém contatos comerciais, andamento do funil, "
            "histórico e registros de chamadas; não contém config.json nem credenciais."
        ),
        "counts": {table: len(items) for table, items in data.items()},
        "schema": schema,
        "data": data,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Exporta o estado portátil do CRM.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    payload = export_state(args.database.resolve(), args.output.resolve())
    print(f"Exportado para {args.output.resolve()}")
    print(json.dumps(payload["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
