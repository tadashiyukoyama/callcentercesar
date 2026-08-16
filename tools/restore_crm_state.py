from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "handoff" / "crm-state.json"
DEFAULT_DATABASE = ROOT / "data" / "discador.db"
RESTORED_TABLES = ("contacts", "call_logs", "contact_events")


def existing_tables(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def create_missing_schema(connection: sqlite3.Connection, schema: list[dict[str, Any]]) -> None:
    present = existing_tables(connection)
    for item in schema:
        if item.get("type") != "table" or item.get("name") in present:
            continue
        sql = item.get("sql")
        if sql:
            connection.execute(str(sql))
            present.add(str(item["name"]))


def insert_rows(
    connection: sqlite3.Connection,
    table: str,
    records: list[dict[str, Any]],
) -> None:
    allowed = {
        row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }
    for record in records:
        columns = [column for column in record if column in allowed]
        if not columns:
            continue
        placeholders = ", ".join("?" for _ in columns)
        names = ", ".join(columns)
        connection.execute(
            f"INSERT INTO {table} ({names}) VALUES ({placeholders})",
            [record[column] for column in columns],
        )


def create_missing_indexes(connection: sqlite3.Connection, schema: list[dict[str, Any]]) -> None:
    present = {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")
    }
    for item in schema:
        if item.get("type") != "index" or item.get("name") in present:
            continue
        sql = item.get("sql")
        if sql:
            connection.execute(str(sql))
            present.add(str(item["name"]))


def restore_state(source: Path, database: Path, replace: bool) -> dict[str, int]:
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("format") != "callcentercesar-crm-state" or payload.get("version") != 1:
        raise ValueError("Formato de exportação desconhecido.")

    data = payload.get("data")
    schema = payload.get("schema")
    if not isinstance(data, dict) or not isinstance(schema, list):
        raise ValueError("Exportação incompleta.")

    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        create_missing_schema(connection, schema)

        current_contacts = 0
        if "contacts" in existing_tables(connection):
            current_contacts = int(connection.execute("SELECT COUNT(*) FROM contacts").fetchone()[0])
        if current_contacts and not replace:
            raise RuntimeError(
                f"O banco de destino já contém {current_contacts} contatos. "
                "Use --replace somente se quiser substituí-los."
            )

        if replace:
            for table in reversed(RESTORED_TABLES):
                if table in existing_tables(connection):
                    connection.execute(f"DELETE FROM {table}")

        counts: dict[str, int] = {}
        for table in RESTORED_TABLES:
            records = data.get(table, [])
            if not isinstance(records, list):
                raise ValueError(f"Tabela inválida na exportação: {table}")
            insert_rows(connection, table, records)
            counts[table] = len(records)

        create_missing_indexes(connection, schema)
        if "sqlite_sequence" in existing_tables(connection):
            for table in RESTORED_TABLES:
                maximum = connection.execute(f"SELECT COALESCE(MAX(id), 0) FROM {table}").fetchone()[0]
                connection.execute("DELETE FROM sqlite_sequence WHERE name = ?", (table,))
                if maximum:
                    connection.execute(
                        "INSERT INTO sqlite_sequence(name, seq) VALUES (?, ?)",
                        (table, maximum),
                    )
        connection.commit()
        return counts
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Restaura o estado portátil do CRM.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Substitui contatos existentes no banco de destino.",
    )
    args = parser.parse_args()

    counts = restore_state(args.input.resolve(), args.database.resolve(), args.replace)
    print(f"Restaurado em {args.database.resolve()}")
    print(json.dumps(counts, ensure_ascii=False))


if __name__ == "__main__":
    main()
