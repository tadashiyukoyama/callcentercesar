from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import app  # noqa: E402


DEFAULT_SOURCE = "https://crm-restaurantes-jundiai.cesaryukoyama28.chatgpt.site/crm.html"
SOURCE_PREFIX = "crm-restaurantes-jundiai"
STATUS_MAP = {
    "Novo": "novo",
    "Tentativa de contato": "tentativa",
    "Conversando": "conversando",
    "Retorno": "retorno",
    "Reunião": "reuniao",
    "Proposta enviada": "proposta",
    "Fechado": "ganho",
    "Perdido": "perdido",
}


def fetch_leads(url: str) -> list[dict[str, Any]]:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DiscadorLocal/1.0",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=45) as response:
        html = response.read().decode("utf-8")
    match = re.search(r"const\s+LEADS\s*=\s*(\[.*?\]);\s*const\s+STATUSES", html, re.DOTALL)
    if not match:
        raise RuntimeError("Não encontrei a lista LEADS na página pública.")
    leads = json.loads(match.group(1))
    if not isinstance(leads, list) or not leads:
        raise RuntimeError("A página pública não retornou uma lista de leads válida.")
    return leads


def text(value: Any) -> str:
    return str(value or "").strip()


def event_key(lead_id: int, index: int, item: dict[str, Any]) -> str:
    payload = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    return f"{SOURCE_PREFIX}:{lead_id}:history:{index}:{digest}"


def import_data(export_path: Path, source_url: str) -> dict[str, Any]:
    export = json.loads(export_path.read_text(encoding="utf-8-sig"))
    crm = export.get("crm")
    if not isinstance(crm, dict):
        raise ValueError("O arquivo não contém o objeto crm esperado.")

    leads = fetch_leads(source_url)
    if len(leads) != len(crm):
        raise ValueError(
            f"A fonte pública tem {len(leads)} leads, mas o arquivo de andamento contém {len(crm)} registros."
        )

    app.setup_database()
    timestamp = app.now_iso()
    inserted = 0
    updated = 0
    imported_events = 0
    status_counts: Counter[str] = Counter()
    missing_phones: list[dict[str, Any]] = []

    upsert_columns = (
        "source_key",
        "lead_order",
        "name",
        "company",
        "phone",
        "instagram",
        "stage",
        "return_date",
        "last_contact_at",
        "notes",
        "whatsapp",
        "city",
        "category",
        "address",
        "responsible_role",
        "confidence",
        "email",
        "website",
        "cnpj",
        "priority",
        "score",
        "source_url",
        "facebook",
        "public_note",
        "legal_company",
        "created_at",
        "updated_at",
    )
    update_columns = tuple(column for column in upsert_columns if column not in {"source_key", "created_at"})
    insert_sql = f"""
        INSERT INTO contacts ({', '.join(upsert_columns)})
        VALUES ({', '.join('?' for _ in upsert_columns)})
        ON CONFLICT(source_key) DO UPDATE SET
          {', '.join(f'{column}=excluded.{column}' for column in update_columns)}
    """

    with app.get_db() as connection:
        for lead in leads:
            lead_id = int(lead["id"])
            progress = crm.get(str(lead_id), {})
            if not isinstance(progress, dict):
                progress = {}
            status_label = text(progress.get("status")) or "Novo"
            stage = STATUS_MAP.get(status_label)
            if not stage:
                raise ValueError(f"Status desconhecido no lead {lead_id}: {status_label}")
            status_counts[status_label] += 1

            responsible = text(progress.get("responsibleOverride")) or text(lead.get("responsible"))
            role = text(progress.get("roleOverride")) or text(lead.get("role"))
            restaurant = text(lead.get("restaurant")) or f"Lead {lead_id}"
            phone = app.normalize_phone(lead.get("phone") or lead.get("whatsapp"))
            whatsapp = app.normalize_phone(lead.get("whatsapp"))
            public_source = text(lead.get("source"))
            facebook = public_source if "facebook.com" in public_source.casefold() else ""
            source_key = f"{SOURCE_PREFIX}:{lead_id}"
            exists = connection.execute(
                "SELECT id FROM contacts WHERE source_key = ?", (source_key,)
            ).fetchone()
            values = (
                source_key,
                lead_id,
                responsible or "Decisor ainda não identificado",
                restaurant,
                phone,
                text(lead.get("instagram")),
                stage,
                text(progress.get("nextFollowUp")),
                text(progress.get("lastContact")),
                text(progress.get("notes")),
                whatsapp,
                text(lead.get("city")),
                text(lead.get("category")),
                text(lead.get("address")),
                role,
                text(lead.get("confidence")),
                text(lead.get("email")),
                text(lead.get("site")),
                text(lead.get("cnpj")),
                text(lead.get("priority")),
                app.safe_int(lead.get("score")),
                public_source,
                facebook,
                text(lead.get("public_note")),
                text(lead.get("company")),
                timestamp,
                timestamp,
            )
            connection.execute(insert_sql, values)
            contact_id = connection.execute(
                "SELECT id FROM contacts WHERE source_key = ?", (source_key,)
            ).fetchone()["id"]
            if exists:
                updated += 1
            else:
                inserted += 1

            if not phone:
                missing_phones.append({"id": lead_id, "restaurant": restaurant})

            history = progress.get("history") if isinstance(progress.get("history"), list) else []
            for index, item in enumerate(history):
                if not isinstance(item, dict) or not text(item.get("text")):
                    continue
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO contact_events(
                      contact_id, occurred_at, text, event_type, external_key, created_at
                    ) VALUES (?, ?, ?, 'imported_history', ?, ?)
                    """,
                    (
                        contact_id,
                        text(item.get("at")),
                        text(item.get("text")),
                        event_key(lead_id, index, item),
                        timestamp,
                    ),
                )
                imported_events += max(cursor.rowcount, 0)

    return {
        "source": source_url,
        "export": str(export_path),
        "source_leads": len(leads),
        "progress_records": len(crm),
        "inserted": inserted,
        "updated": updated,
        "events_inserted": imported_events,
        "status_counts": dict(status_counts),
        "missing_phone": missing_phones,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa o CRM público e seu arquivo de andamento.")
    parser.add_argument("export", type=Path, help="Arquivo crm-restaurantes-andamento.json")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="URL pública crm.html")
    args = parser.parse_args()
    if not args.export.is_file():
        raise SystemExit(f"Arquivo não encontrado: {args.export}")
    result = import_data(args.export.resolve(), args.source)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
