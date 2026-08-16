from __future__ import annotations

import csv
import io
import json
import mimetypes
import os
import re
import sqlite3
import subprocess
import threading
import time
import traceback
import xml.etree.ElementTree as ET
from datetime import datetime
from email import policy
from email.parser import BytesParser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "discador.db"
CONFIG_PATH = ROOT / "config.json"
HOST = "127.0.0.1"
PORT = int(os.environ.get("DISCADOR_PORT", "8765"))
DEFAULT_ADB = Path(r"D:\AndroidTools\platform-tools\adb.exe")

STAGES = {
    "novo": "Novo",
    "tentativa": "Tentativa de contato",
    "conversando": "Conversando",
    "retorno": "Retorno",
    "reuniao": "Reunião",
    "proposta": "Proposta enviada",
    "ganho": "Fechado",
    "perdido": "Perdido",
}

OUTCOMES = {
    "answered": "Atendeu",
    "interested": "Interessado",
    "refused": "Recusou",
    "meeting": "Reunião agendada",
    "voicemail": "Caixa postal",
    "wrong_number": "Número inválido",
    "busy": "Ocupado",
    "dropped": "Caiu",
    "no_answer": "Não atendeu",
    "callback": "Retorno agendado",
}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def today_iso() -> str:
    return datetime.now().astimezone().date().isoformat()


def normalize_phone(value: Any) -> str:
    raw = str(value or "").strip()
    if raw.startswith("+"):
        return "+" + re.sub(r"\D", "", raw[1:])
    return re.sub(r"\D", "", raw)


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def contact_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    result = dict(row)
    result["stage_label"] = STAGES.get(result.get("stage"), result.get("stage") or "Novo")
    return result


def get_db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")
    return connection


def setup_database() -> None:
    with get_db() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                company TEXT DEFAULT '',
                phone TEXT NOT NULL,
                instagram TEXT DEFAULT '',
                stage TEXT NOT NULL DEFAULT 'novo',
                return_date TEXT DEFAULT '',
                last_contact_at TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS call_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT NOT NULL,
                outcome TEXT NOT NULL,
                duration_seconds INTEGER DEFAULT 0,
                notes TEXT DEFAULT '',
                FOREIGN KEY(contact_id) REFERENCES contacts(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        existing_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(contacts)").fetchall()
        }
        extra_columns = {
            "source_key": "TEXT",
            "lead_order": "INTEGER DEFAULT 0",
            "whatsapp": "TEXT DEFAULT ''",
            "city": "TEXT DEFAULT ''",
            "category": "TEXT DEFAULT ''",
            "address": "TEXT DEFAULT ''",
            "responsible_role": "TEXT DEFAULT ''",
            "confidence": "TEXT DEFAULT ''",
            "email": "TEXT DEFAULT ''",
            "website": "TEXT DEFAULT ''",
            "cnpj": "TEXT DEFAULT ''",
            "priority": "TEXT DEFAULT ''",
            "score": "INTEGER DEFAULT 0",
            "source_url": "TEXT DEFAULT ''",
            "facebook": "TEXT DEFAULT ''",
            "public_note": "TEXT DEFAULT ''",
            "legal_company": "TEXT DEFAULT ''",
        }
        for column, definition in extra_columns.items():
            if column not in existing_columns:
                connection.execute(f"ALTER TABLE contacts ADD COLUMN {column} {definition}")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS contact_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id INTEGER NOT NULL,
                occurred_at TEXT DEFAULT '',
                text TEXT NOT NULL,
                event_type TEXT NOT NULL DEFAULT 'note',
                external_key TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(contact_id) REFERENCES contacts(id) ON DELETE CASCADE
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_contact_events_external_key
              ON contact_events(external_key)
              WHERE external_key IS NOT NULL AND external_key != '';
            CREATE INDEX IF NOT EXISTS idx_contacts_stage ON contacts(stage);
            CREATE INDEX IF NOT EXISTS idx_contacts_queue ON contacts(stage, return_date, last_contact_at);
            """
        )
        connection.execute("DROP INDEX IF EXISTS idx_contacts_source_key")
        connection.execute("CREATE UNIQUE INDEX idx_contacts_source_key ON contacts(source_key)")
        connection.execute("UPDATE contacts SET stage = 'conversando' WHERE stage = 'contato'")
        connection.execute("UPDATE contacts SET stage = 'reuniao' WHERE stage = 'qualificado'")


def load_config() -> dict[str, str]:
    defaults = {"adb_path": str(DEFAULT_ADB), "device_serial": ""}
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            defaults.update({key: str(value) for key, value in data.items() if value is not None})
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return defaults


def save_config(data: dict[str, str]) -> None:
    CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class ADBError(RuntimeError):
    pass


class ADBBridge:
    def __init__(self) -> None:
        config = load_config()
        self.adb_path = Path(config.get("adb_path") or DEFAULT_ADB)
        self.serial = config.get("device_serial", "")
        self.last_error = ""
        self.last_check = 0.0
        self.connected = False
        self.lock = threading.RLock()

    def _run(self, args: list[str], timeout: float = 8.0, with_serial: bool = False) -> tuple[int, str, str]:
        if not self.adb_path.exists():
            self.last_error = f"ADB não encontrado em {self.adb_path}"
            return 1, "", self.last_error
        command = [str(self.adb_path)]
        if with_serial and self.serial:
            command.extend(["-s", self.serial])
        command.extend(args)
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if completed.returncode != 0:
                self.last_error = (completed.stderr or completed.stdout or "Falha no ADB").strip()
            return completed.returncode, completed.stdout.strip(), completed.stderr.strip()
        except subprocess.TimeoutExpired:
            self.last_error = "O ADB demorou demais para responder."
            return 124, "", self.last_error
        except OSError as exc:
            self.last_error = str(exc)
            return 1, "", self.last_error

    def _shell(self, args: list[str], timeout: float = 8.0) -> str:
        code, stdout, stderr = self._run(["shell", *args], timeout=timeout, with_serial=True)
        if code != 0:
            raise ADBError(stderr or stdout or self.last_error or "Falha no ADB")
        return stdout

    def _device_list(self) -> list[tuple[str, str]]:
        code, stdout, _ = self._run(["devices"], timeout=5.0)
        if code != 0:
            return []
        devices: list[tuple[str, str]] = []
        for line in stdout.splitlines():
            if "\t" in line:
                serial, state = line.split("\t", 1)
                if serial.strip() and serial.strip() != "List of devices attached":
                    devices.append((serial.strip(), state.strip()))
        return devices

    def ensure_device(self, force: bool = False) -> bool:
        with self.lock:
            if not force and time.monotonic() - self.last_check < 2.5:
                return self.connected
            self.last_check = time.monotonic()
            devices = self._device_list()
            ready = [serial for serial, state in devices if state == "device"]
            if self.serial in ready:
                self.connected = True
                return True
            if ready:
                self.serial = ready[0]
                self.connected = True
                save_config({"adb_path": str(self.adb_path), "device_serial": self.serial})
                return True

            code, services, _ = self._run(["mdns", "services"], timeout=5.0)
            if code == 0:
                candidates = re.findall(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}:\d{3,6}", services)
                seen: set[str] = set()
                for candidate in candidates:
                    if candidate in seen:
                        continue
                    seen.add(candidate)
                    self._run(["connect", candidate], timeout=8.0)
                    devices = self._device_list()
                    if any(serial == candidate and state == "device" for serial, state in devices):
                        self.serial = candidate
                        self.connected = True
                        save_config({"adb_path": str(self.adb_path), "device_serial": self.serial})
                        return True

            self.connected = False
            return False

    def connect(self) -> dict[str, Any]:
        ok = self.ensure_device(force=True)
        return self.status() | {"ok": ok}

    def status(self) -> dict[str, Any]:
        connected = self.ensure_device()
        result: dict[str, Any] = {
            "connected": connected,
            "serial": self.serial if connected else "",
            "adb_path": str(self.adb_path),
            "error": "" if connected else self.last_error,
        }
        if connected:
            try:
                props = self._shell(["getprop"], timeout=5.0)
                result["model"] = self._prop(props, "ro.product.model") or "Android"
                result["android"] = self._prop(props, "ro.build.version.release") or "?"
            except ADBError as exc:
                result["error"] = str(exc)
        return result

    @staticmethod
    def _prop(output: str, name: str) -> str:
        match = re.search(rf"\[{re.escape(name)}\]: \[(.*?)\]", output)
        return match.group(1) if match else ""

    def call_state(self) -> tuple[str, str]:
        if not self.ensure_device():
            return "offline", self.last_error
        try:
            registry = self._shell(["dumpsys", "telephony.registry"], timeout=6.0)
            state_values = [int(value) for value in re.findall(r"mCallState\s*=\s*(\d+)", registry)]
            telecom = self._shell(["dumpsys", "telecom"], timeout=6.0)
            cause = self._disconnect_cause(telecom, registry)

            # Precise telephony states distinguish DIALING/ALERTING from ACTIVE.
            # The coarse state 2 only means OFFHOOK and is therefore not enough
            # for the assisted automatic sequence to know that someone answered.
            precise_values = [
                int(value)
                for value in re.findall(
                    r"(?:mForegroundCallState|foregroundCallState)\s*[=:]\s*(\d+)",
                    registry,
                    flags=re.IGNORECASE,
                )
            ]
            calls_match = re.search(
                r"\bmCalls:\s*(.*?)(?:\n\s*mCallAudioManager:|\n\s*mInCallController:|\Z)",
                telecom,
                flags=re.IGNORECASE | re.DOTALL,
            )
            current_calls = calls_match.group(1) if calls_match else ""
            telecom_states = {
                value.upper()
                for value in re.findall(
                    r"\bstate\s*=\s*(ACTIVE|HOLDING|DIALING|CONNECTING|SELECT_PHONE_ACCOUNT|RINGING|NEW|DISCONNECTING)",
                    current_calls,
                    flags=re.IGNORECASE,
                )
            }

            if 1 in precise_values or "ACTIVE" in telecom_states or "HOLDING" in telecom_states:
                state = "active"
            elif any(value in {5, 6} for value in precise_values) or "RINGING" in telecom_states:
                state = "ringing"
            elif any(value in {3, 4} for value in precise_values) or telecom_states.intersection(
                {"DIALING", "CONNECTING", "SELECT_PHONE_ACCOUNT", "NEW"}
            ):
                state = "dialing"
            elif 1 in state_values:
                state = "ringing"
            elif 2 in state_values:
                state = "dialing"
            else:
                state = "idle"
            return state, cause
        except ADBError as exc:
            return "unknown", str(exc)

    @staticmethod
    def _disconnect_cause(telecom: str, registry: str) -> str:
        # Android's dumpsys format differs by build: recent versions use
        # "DisconnectCause [ Code: (...) ... Reason: (...)" rather than the
        # older "code=" representation.
        matches = re.findall(
            r"DisconnectCause\s*\[\s*Code:\s*\(([^)]+)\).*?Reason:\s*\(([^)]+)\)",
            telecom,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if matches:
            code, reason = matches[-1]
            return reason.strip() or code.strip()
        legacy = re.search(r"DisconnectCause\s*\{[^}]*code=([^,}]+)", telecom, flags=re.IGNORECASE)
        if legacy:
            return legacy.group(1).strip()
        causes = [value for value in re.findall(r"mCallDisconnectCause\s*=\s*(-?\d+)", registry) if value != "-1"]
        return f"TELEPHONY_CAUSE_{causes[-1]}" if causes else ""

    def start_call(self, phone: str) -> str:
        if not self.ensure_device(force=True):
            raise ADBError(self.last_error or "Celular não conectado ao ADB")
        normalized = normalize_phone(phone)
        if len(re.sub(r"\D", "", normalized)) < 8:
            raise ValueError("O telefone precisa ter pelo menos 8 dígitos.")
        self._shell(["am", "start", "-a", "android.intent.action.CALL", "-d", f"tel:{normalized}"], timeout=8.0)
        return normalized

    def hangup(self) -> None:
        if self.ensure_device():
            self._shell(["input", "keyevent", "6"], timeout=5.0)

    def _window_xml(self) -> str:
        self._shell(["uiautomator", "dump", "/sdcard/discador-window.xml"], timeout=8.0)
        return self._shell(["cat", "/sdcard/discador-window.xml"], timeout=5.0)

    def activate_speaker(self) -> dict[str, Any]:
        if not self.ensure_device():
            return {"ok": False, "message": self.last_error or "Celular offline"}
        try:
            xml = self._window_xml()
            root = ET.fromstring(xml)
        except (ADBError, ET.ParseError) as exc:
            return {"ok": False, "message": f"Não consegui ler a tela da chamada: {exc}"}

        terms = (
            "speaker",
            "alto-fal",
            "alto fal",
            "viva-voz",
            "viva voz",
            "hands-free",
            "handsfree",
            "altavoz",
            "altavoz",
        )
        resource_terms = ("speaker", "speakerphone", "audio_route", "audio-route", "toggle_speaker")
        for node in root.iter():
            label = " ".join((node.attrib.get("text", ""), node.attrib.get("content-desc", ""))).casefold()
            resource_id = node.attrib.get("resource-id", "").casefold()
            if not any(term in label for term in terms) and not any(term in resource_id for term in resource_terms):
                continue
            if node.attrib.get("checked") == "true" or node.attrib.get("selected") == "true":
                return {"ok": True, "changed": False, "message": "Viva-voz já estava ativo."}
            bounds = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.attrib.get("bounds", ""))
            if not bounds:
                continue
            x1, y1, x2, y2 = (int(value) for value in bounds.groups())
            self._shell(["input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2)], timeout=5.0)
            return {"ok": True, "changed": True, "message": "Viva-voz ativado."}
        return {"ok": False, "message": "Botão de viva-voz não apareceu na tela da chamada."}


class DialerController:
    def __init__(self, bridge: ADBBridge) -> None:
        self.bridge = bridge
        self.lock = threading.RLock()
        self.selected_contact_id: int | None = None
        self.active_contact_id: int | None = None
        self.call_started_at = ""
        self.call_status = "idle"
        self.last_cause = ""
        self.speaker_message = ""
        self.last_poll = 0.0

    def _contact(self, contact_id: int | None) -> sqlite3.Row | None:
        if not contact_id:
            return None
        with get_db() as connection:
            return connection.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()

    def select(self, contact_id: int) -> dict[str, Any]:
        contact = self._contact(contact_id)
        if contact is None:
            raise ValueError("Contato não encontrado.")
        with self.lock:
            self.selected_contact_id = contact_id
        return {"contact": contact_dict(contact)}

    def _poll_call(self) -> None:
        if time.monotonic() - self.last_poll < 1.0:
            return
        self.last_poll = time.monotonic()
        state, cause = self.bridge.call_state()
        with self.lock:
            self.last_cause = cause
            if self.active_contact_id:
                if state == "dialing":
                    self.call_status = "dialing"
                elif state == "ringing":
                    self.call_status = "ringing"
                elif state == "active":
                    self.call_status = "active"
                elif state == "idle" and self.call_status in {"ringing", "active", "dialing"}:
                    self.call_status = "disconnected"
                elif state in {"offline", "unknown"}:
                    self.call_status = state

    def status(self) -> dict[str, Any]:
        with self.lock:
            self._poll_call()
            selected = self._contact(self.selected_contact_id)
            active = self._contact(self.active_contact_id)
            return {
                "selected": contact_dict(selected),
                "active": contact_dict(active),
                "call_status": self.call_status,
                "call_started_at": self.call_started_at,
                "last_cause": self.last_cause,
                "speaker_message": self.speaker_message,
                "phone": self.bridge.status(),
            }

    def start(self, contact_id: int) -> dict[str, Any]:
        contact = self._contact(contact_id)
        if contact is None:
            raise ValueError("Contato não encontrado.")
        with self.lock:
            if self.active_contact_id and self.call_status not in {"idle", "disconnected"}:
                raise ValueError("Já existe uma chamada em andamento.")
            self.bridge.start_call(contact["phone"])
            self.selected_contact_id = contact_id
            self.active_contact_id = contact_id
            self.call_started_at = now_iso()
            self.call_status = "dialing"
            self.last_cause = ""
            self.speaker_message = "Aguardando tela da chamada..."
            # The in-call UI can appear after the telecom state changes. Retry
            # a few times instead of losing the only early attempt.
            for delay in (1.8, 3.6, 5.8, 8.0):
                timer = threading.Timer(delay, self._activate_speaker_later)
                timer.daemon = True
                timer.start()
        return self.status()

    def _activate_speaker_later(self) -> None:
        with self.lock:
            if not self.active_contact_id or self.call_status not in {"dialing", "ringing", "active"}:
                return
        result = self.bridge.activate_speaker()
        with self.lock:
            if result.get("ok") or not self.speaker_message or "não apareceu" in self.speaker_message.casefold():
                self.speaker_message = result.get("message", "")

    def speaker(self) -> dict[str, Any]:
        result = self.bridge.activate_speaker()
        with self.lock:
            self.speaker_message = result.get("message", "")
        return result

    def hangup(self) -> dict[str, Any]:
        self.bridge.hangup()
        with self.lock:
            if self.active_contact_id:
                self.call_status = "disconnected"
        return self.status()

    @staticmethod
    def _next_contact(exclude_id: int | None) -> sqlite3.Row | None:
        with get_db() as connection:
            return connection.execute(
                """
                SELECT * FROM contacts
                WHERE (? IS NULL OR id != ?)
                  AND stage NOT IN ('ganho', 'perdido')
                  AND phone IS NOT NULL AND TRIM(phone) != ''
                ORDER BY
                  CASE
                    WHEN return_date != '' AND substr(return_date, 1, 10) <= ? THEN 0
                    WHEN return_date != '' THEN 1
                    ELSE 2
                  END,
                  CASE WHEN return_date IS NULL OR return_date = '' THEN '9999-12-31' ELSE return_date END ASC,
                  CASE UPPER(priority)
                    WHEN 'QUENTE' THEN 0
                    WHEN 'PRIORITÁRIO' THEN 1
                    WHEN 'PRIORITARIO' THEN 1
                    WHEN 'MÉDIO' THEN 2
                    WHEN 'MEDIO' THEN 2
                    ELSE 3
                  END,
                  score DESC,
                  CASE WHEN last_contact_at IS NULL OR last_contact_at = '' THEN 0 ELSE 1 END,
                  last_contact_at ASC,
                  CASE WHEN lead_order > 0 THEN lead_order ELSE 999999 END,
                  id ASC
                LIMIT 1
                """,
                (exclude_id, exclude_id, today_iso()),
            ).fetchone()

    def _record(self, contact_id: int, outcome: str, notes: str = "", return_date: str = "") -> None:
        if outcome not in OUTCOMES:
            raise ValueError("Resultado de chamada inválido.")
        ended = now_iso()
        with get_db() as connection:
            row = connection.execute(
                "SELECT last_contact_at, return_date, notes FROM contacts WHERE id = ?", (contact_id,)
            ).fetchone()
            started = (self.call_started_at or (row["last_contact_at"] if row else "") or ended)
            duration = 0
            try:
                duration = max(0, int((datetime.fromisoformat(ended) - datetime.fromisoformat(started)).total_seconds()))
            except (TypeError, ValueError):
                pass
            connection.execute(
                "INSERT INTO call_logs(contact_id, started_at, ended_at, outcome, duration_seconds, notes) VALUES (?, ?, ?, ?, ?, ?)",
                (contact_id, started, ended, outcome, duration, notes.strip()),
            )
            stage_by_outcome = {
                "answered": "conversando",
                "interested": "conversando",
                "callback": "retorno",
                "meeting": "reuniao",
                "refused": "perdido",
                "voicemail": "tentativa",
                "wrong_number": "tentativa",
                "busy": "tentativa",
                "dropped": "tentativa",
                "no_answer": "tentativa",
            }
            next_stage = stage_by_outcome.get(outcome, "tentativa")
            saved_return = return_date.strip() or (row["return_date"] if row else "")
            saved_notes = row["notes"] if row else ""
            if notes.strip():
                label = datetime.now().astimezone().strftime("%d/%m/%Y %H:%M")
                observation = f"[{label}] {notes.strip()}"
                saved_notes = f"{saved_notes.rstrip()}\n{observation}".strip()
            connection.execute(
                """
                UPDATE contacts
                SET last_contact_at = ?, stage = ?, return_date = ?, notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (ended, next_stage, saved_return, saved_notes, ended, contact_id),
            )

    def record(self, outcome: str, notes: str = "", return_date: str = "") -> dict[str, Any]:
        with self.lock:
            contact_id = self.active_contact_id or self.selected_contact_id
            if not contact_id:
                raise ValueError("Selecione um contato primeiro.")
            self._record(contact_id, outcome, notes, return_date)
            self.active_contact_id = None
            self.call_status = "idle"
            self.call_started_at = ""
            self.selected_contact_id = contact_id
        return self.status()

    def next(self, outcome: str, notes: str = "", return_date: str = "", auto_start: bool = True) -> dict[str, Any]:
        with self.lock:
            current_id = self.active_contact_id or self.selected_contact_id
            if current_id and outcome:
                if self.active_contact_id and self.call_status not in {"idle", "disconnected"}:
                    self.bridge.hangup()
                self._record(current_id, outcome, notes, return_date)
            next_contact = self._next_contact(current_id)
            self.active_contact_id = None
            self.call_status = "idle"
            self.call_started_at = ""
            self.last_cause = ""
            self.speaker_message = ""
            self.selected_contact_id = next_contact["id"] if next_contact else None
        if next_contact and auto_start:
            return self.start(next_contact["id"])
        return self.status()


def list_contacts(search: str = "", stage: str = "") -> list[dict[str, Any]]:
    with get_db() as connection:
        clauses: list[str] = []
        params: list[Any] = []
        if search:
            clauses.append(
                """(
                  name LIKE ? OR company LIKE ? OR legal_company LIKE ? OR phone LIKE ? OR whatsapp LIKE ?
                  OR instagram LIKE ? OR city LIKE ? OR responsible_role LIKE ? OR notes LIKE ? OR cnpj LIKE ?
                )"""
            )
            value = f"%{search}%"
            params.extend([value] * 10)
        if stage and stage in STAGES:
            clauses.append("stage = ?")
            params.append(stage)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = connection.execute(
            f"""
            SELECT * FROM contacts {where}
            ORDER BY CASE WHEN lead_order > 0 THEN lead_order ELSE 999999 END, id DESC
            LIMIT 500
            """,
            params,
        ).fetchall()
        return [contact_dict(row) for row in rows]


def queue_contacts(limit: int = 500) -> list[dict[str, Any]]:
    with get_db() as connection:
        rows = connection.execute(
            """
            SELECT * FROM contacts
            WHERE stage NOT IN ('ganho', 'perdido')
              AND phone IS NOT NULL AND TRIM(phone) != ''
            ORDER BY
              CASE
                WHEN return_date != '' AND substr(return_date, 1, 10) <= ? THEN 0
                WHEN return_date != '' THEN 1
                ELSE 2
              END,
              CASE WHEN return_date IS NULL OR return_date = '' THEN '9999-12-31' ELSE return_date END ASC,
              CASE UPPER(priority)
                WHEN 'QUENTE' THEN 0
                WHEN 'PRIORITÁRIO' THEN 1
                WHEN 'PRIORITARIO' THEN 1
                WHEN 'MÉDIO' THEN 2
                WHEN 'MEDIO' THEN 2
                ELSE 3
              END,
              score DESC,
              CASE WHEN last_contact_at IS NULL OR last_contact_at = '' THEN 0 ELSE 1 END,
              last_contact_at ASC,
              CASE WHEN lead_order > 0 THEN lead_order ELSE 999999 END,
              id ASC
            LIMIT ?
            """,
            (today_iso(), max(1, min(limit, 500))),
        ).fetchall()
        return [contact_dict(row) for row in rows]


def summary() -> dict[str, Any]:
    with get_db() as connection:
        total = connection.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        active = connection.execute("SELECT COUNT(*) FROM contacts WHERE stage NOT IN ('ganho', 'perdido')").fetchone()[0]
        due = connection.execute(
            """
            SELECT COUNT(*) FROM contacts
            WHERE return_date != '' AND substr(return_date, 1, 10) <= ?
              AND stage NOT IN ('ganho', 'perdido')
            """,
            (today_iso(),),
        ).fetchone()[0]
        contacted = connection.execute("SELECT COUNT(*) FROM contacts WHERE last_contact_at != ''").fetchone()[0]
        calls = connection.execute("SELECT COUNT(*) FROM call_logs WHERE date(ended_at) = date('now', 'localtime')").fetchone()[0]
        counts = {
            row["stage"]: row["total"]
            for row in connection.execute("SELECT stage, COUNT(*) AS total FROM contacts GROUP BY stage").fetchall()
        }
        pipeline = {stage: int(counts.get(stage, 0)) for stage in STAGES}
        return {
            "total": total,
            "active": active,
            "due": due,
            "contacted": contacted,
            "calls_today": calls,
            "pipeline": pipeline,
        }


def funnel() -> dict[str, Any]:
    with get_db() as connection:
        rows = connection.execute(
            """
            SELECT * FROM contacts
            ORDER BY
              CASE stage
                WHEN 'novo' THEN 0
                WHEN 'tentativa' THEN 1
                WHEN 'conversando' THEN 2
                WHEN 'retorno' THEN 3
                WHEN 'reuniao' THEN 4
                WHEN 'proposta' THEN 5
                WHEN 'ganho' THEN 6
                WHEN 'perdido' THEN 7
                ELSE 8
              END,
              CASE UPPER(priority)
                WHEN 'QUENTE' THEN 0
                WHEN 'PRIORITÁRIO' THEN 1
                WHEN 'PRIORITARIO' THEN 1
                WHEN 'MÉDIO' THEN 2
                WHEN 'MEDIO' THEN 2
                ELSE 3
              END,
              score DESC,
              CASE WHEN lead_order > 0 THEN lead_order ELSE 999999 END,
              id ASC
            LIMIT 500
            """
        ).fetchall()
        contacts = [contact_dict(row) for row in rows]
        return {
            "contacts": contacts,
            "stages": STAGES,
            "cities": sorted({item.get("city", "") for item in contacts if item.get("city")}),
            "priorities": [
                value
                for value in ("QUENTE", "PRIORITÁRIO", "MÉDIO", "BASE")
                if any(item.get("priority") == value for item in contacts)
            ],
        }


def contact_events(contact_id: int | None = None, limit: int = 200) -> list[dict[str, Any]]:
    with get_db() as connection:
        params: list[Any] = []
        where = ""
        if contact_id:
            where = "WHERE contact_events.contact_id = ?"
            params.append(contact_id)
        params.append(max(1, min(limit, 500)))
        rows = connection.execute(
            f"""
            SELECT contact_events.*, contacts.name, contacts.company
            FROM contact_events JOIN contacts ON contacts.id = contact_events.contact_id
            {where}
            ORDER BY contact_events.occurred_at DESC, contact_events.id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]


def history(limit: int = 100) -> list[dict[str, Any]]:
    with get_db() as connection:
        rows = connection.execute(
            """
            SELECT call_logs.*, contacts.name, contacts.company, contacts.phone
            FROM call_logs JOIN contacts ON contacts.id = call_logs.contact_id
            ORDER BY call_logs.id DESC LIMIT ?
            """,
            (max(1, min(limit, 500)),),
        ).fetchall()
        return [dict(row) for row in rows]


def create_contact(data: dict[str, Any]) -> dict[str, Any]:
    name = str(data.get("name", "")).strip()
    phone = normalize_phone(data.get("phone"))
    if not name:
        raise ValueError("Nome é obrigatório.")
    if len(re.sub(r"\D", "", phone)) < 8:
        raise ValueError("Telefone inválido ou incompleto.")
    stage = data.get("stage", "novo") if data.get("stage", "novo") in STAGES else "novo"
    timestamp = now_iso()
    text_fields = (
        "company",
        "instagram",
        "return_date",
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
        "source_url",
        "facebook",
        "public_note",
        "legal_company",
    )
    columns = ["name", "phone", "stage", *text_fields, "score", "created_at", "updated_at"]
    values: list[Any] = [name, phone, stage]
    values.extend(str(data.get(field, "")).strip() for field in text_fields)
    values.extend([safe_int(data.get("score")), timestamp, timestamp])
    with get_db() as connection:
        cursor = connection.execute(
            f"INSERT INTO contacts({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
            values,
        )
        row = connection.execute("SELECT * FROM contacts WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return contact_dict(row) or {}


def update_contact(contact_id: int, data: dict[str, Any]) -> dict[str, Any]:
    with get_db() as connection:
        current = connection.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()
        if current is None:
            raise ValueError("Contato não encontrado.")
        name = str(data.get("name", current["name"])).strip()
        phone = normalize_phone(data.get("phone", current["phone"]))
        if not name:
            raise ValueError("Nome é obrigatório.")
        if phone and len(re.sub(r"\D", "", phone)) < 8:
            raise ValueError("Telefone inválido ou incompleto.")
        if not phone and not current["source_key"]:
            raise ValueError("Telefone válido é obrigatório para contatos manuais.")
        stage = data.get("stage", current["stage"])
        if stage not in STAGES:
            stage = current["stage"]
        text_fields = (
            "company",
            "instagram",
            "return_date",
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
            "source_url",
            "facebook",
            "public_note",
            "legal_company",
        )
        values: list[Any] = [name, phone, stage]
        values.extend(str(data.get(field, current[field])).strip() for field in text_fields)
        values.extend([safe_int(data.get("score", current["score"]), current["score"]), now_iso(), contact_id])
        connection.execute(
            f"""
            UPDATE contacts
            SET name=?, phone=?, stage=?, {', '.join(f'{field}=?' for field in text_fields)}, score=?, updated_at=?
            WHERE id=?
            """,
            values,
        )
        row = connection.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()
        return contact_dict(row) or {}


def parse_import(content: bytes, filename: str) -> list[dict[str, Any]]:
    text = content.decode("utf-8-sig", errors="replace")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    aliases = {
        "name": ("name", "nome", "cliente", "contato"),
        "company": ("company", "empresa", "razao social", "razão social"),
        "phone": ("phone", "telefone", "celular", "numero", "número"),
        "instagram": ("instagram", "insta", "@instagram"),
        "stage": ("stage", "etapa", "funil"),
        "return_date": ("return_date", "data retorno", "retorno", "follow up", "follow-up"),
        "notes": ("notes", "observação", "observacoes", "observações", "notas"),
    }

    def value_for(row: dict[str | None, str | None], keys: tuple[str, ...]) -> str:
        normalized = {str(key or "").strip().casefold(): str(value or "").strip() for key, value in row.items()}
        for key in keys:
            if key.casefold() in normalized:
                return normalized[key.casefold()]
        return ""

    result: list[dict[str, Any]] = []
    for row in reader:
        mapped = {field: value_for(row, keys) for field, keys in aliases.items()}
        if mapped["name"] or mapped["phone"]:
            result.append(mapped)
    return result


class AppHandler(BaseHTTPRequestHandler):
    server_version = "Discador/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {fmt % args}")

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _send_bytes(self, body: bytes, content_type: str, status: int = 200) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _error(self, message: str, status: int = 400) -> None:
        self._send_json({"ok": False, "error": message}, status)

    def _read_body(self) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        return self.rfile.read(max(0, length))

    def _json_body(self) -> dict[str, Any]:
        raw = self._read_body()
        if not raw:
            return {}
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON inválido.")
        return data

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)
        try:
            if path == "/":
                self._send_bytes((STATIC_DIR / "index.html").read_bytes(), "text/html; charset=utf-8")
                return
            if path.startswith("/static/"):
                target = (STATIC_DIR / path.removeprefix("/static/")).resolve()
                if not target.is_relative_to(STATIC_DIR.resolve()) or not target.exists():
                    self._error("Arquivo não encontrado.", 404)
                    return
                self._send_bytes(target.read_bytes(), mimetypes.guess_type(target.name)[0] or "application/octet-stream")
                return
            if path == "/api/health":
                self._send_json({"ok": True, "app": "Discador", "root": str(ROOT), "time": now_iso()})
                return
            if path == "/api/status":
                self._send_json({"ok": True, **dialer.status()})
                return
            if path == "/api/summary":
                self._send_json({"ok": True, "summary": summary()})
                return
            if path == "/api/contacts":
                self._send_json({"ok": True, "contacts": list_contacts(query.get("search", [""])[0], query.get("stage", [""])[0])})
                return
            if path == "/api/funnel":
                self._send_json({"ok": True, **funnel()})
                return
            if path == "/api/queue":
                limit = safe_int(query.get("limit", [500])[0], 500)
                self._send_json({"ok": True, "contacts": queue_contacts(limit)})
                return
            if path == "/api/history":
                self._send_json({"ok": True, "history": history()})
                return
            if path == "/api/events":
                contact_id = safe_int(query.get("contact_id", [0])[0], 0) or None
                self._send_json({"ok": True, "events": contact_events(contact_id)})
                return
            if path == "/api/config":
                self._send_json({"ok": True, "config": load_config(), "stages": STAGES, "outcomes": OUTCOMES})
                return
            self._error("Rota não encontrada.", 404)
        except Exception as exc:
            traceback.print_exc()
            self._error(str(exc), 500)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        try:
            if path == "/api/contacts":
                self._send_json({"ok": True, "contact": create_contact(self._json_body())}, 201)
                return
            if path == "/api/import":
                body = self._read_body()
                content_type = self.headers.get("Content-Type", "")
                header_bytes = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode()
                message = BytesParser(policy=policy.default).parsebytes(header_bytes + body)
                imported: list[dict[str, Any]] = []
                for part in message.iter_attachments():
                    content = part.get_payload(decode=True) or b""
                    imported.extend(parse_import(content, part.get_filename() or "import.csv"))
                if not imported:
                    raise ValueError("Não encontrei um arquivo CSV no envio.")
                created = 0
                errors: list[str] = []
                for index, item in enumerate(imported, start=2):
                    try:
                        create_contact(item)
                        created += 1
                    except ValueError as exc:
                        errors.append(f"Linha {index}: {exc}")
                self._send_json({"ok": True, "created": created, "errors": errors})
                return
            if path == "/api/adb/connect":
                self._send_json({"ok": True, "phone": dialer.bridge.connect()})
                return
            if path == "/api/dialer/select":
                data = self._json_body()
                self._send_json({"ok": True, **dialer.select(int(data["contact_id"]))})
                return
            if path == "/api/dialer/start":
                data = self._json_body()
                self._send_json({"ok": True, **dialer.start(int(data["contact_id"]))})
                return
            if path == "/api/dialer/speaker":
                self._send_json(dialer.speaker())
                return
            if path == "/api/dialer/hangup":
                self._send_json({"ok": True, **dialer.hangup()})
                return
            if path == "/api/dialer/record":
                data = self._json_body()
                self._send_json(
                    {
                        "ok": True,
                        **dialer.record(
                            str(data.get("outcome", "")),
                            str(data.get("notes", "")),
                            str(data.get("return_date", "")),
                        ),
                    }
                )
                return
            if path == "/api/dialer/next":
                data = self._json_body()
                self._send_json(
                    {
                        "ok": True,
                        **dialer.next(
                            str(data.get("outcome", "")),
                            str(data.get("notes", "")),
                            str(data.get("return_date", "")),
                            bool(data.get("auto_start", True)),
                        ),
                    }
                )
                return
            self._error("Rota não encontrada.", 404)
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self._error(str(exc), 400)
        except ADBError as exc:
            self._error(str(exc), 503)
        except Exception as exc:
            traceback.print_exc()
            self._error(str(exc), 500)

    def do_PUT(self) -> None:
        path = unquote(urlparse(self.path).path)
        match = re.fullmatch(r"/api/contacts/(\d+)", path)
        if not match:
            self._error("Rota não encontrada.", 404)
            return
        try:
            self._send_json({"ok": True, "contact": update_contact(int(match.group(1)), self._json_body())})
        except (ValueError, json.JSONDecodeError) as exc:
            self._error(str(exc), 400)
        except Exception as exc:
            traceback.print_exc()
            self._error(str(exc), 500)

    def do_DELETE(self) -> None:
        path = unquote(urlparse(self.path).path)
        match = re.fullmatch(r"/api/contacts/(\d+)", path)
        if not match:
            self._error("Rota não encontrada.", 404)
            return
        contact_id = int(match.group(1))
        with get_db() as connection:
            cursor = connection.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
        self._send_json({"ok": True, "deleted": cursor.rowcount > 0})


setup_database()
bridge = ADBBridge()
dialer = DialerController(bridge)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    print(f"Discador rodando em http://{HOST}:{PORT}")
    print(f"Dados: {DB_PATH}")
    print(f"ADB: {bridge.adb_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDiscador encerrado.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
