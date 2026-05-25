"""Italian user-facing strings for the LegalAI dashboard.

To switch language, replace the string values in this module only.
"""

# ── Login page ────────────────────────────────────────────────────────────────

LOGIN_SUBTITLE = "Portale di Gestione Casi"
LOGIN_EMAIL_LABEL = "Indirizzo email"
LOGIN_EMAIL_PLACEHOLDER = "avvocato@studio.it"
LOGIN_PASSWORD_LABEL = "Password"
LOGIN_BUTTON = "Accedi"
LOGIN_ERROR_EMPTY = "Compila tutti i campi."
LOGIN_ERROR_INVALID = "Email o password non validi."
LOGIN_COPYRIGHT = "LegalAI © 2024"

# ── Header ────────────────────────────────────────────────────────────────────

LOGOUT_TOOLTIP = "Esci"

# ── Stats bar ─────────────────────────────────────────────────────────────────

STATS_TOTAL_PLACEHOLDER = "Totale: —"
STATS_PENDING_PLACEHOLDER = "In attesa: —"
STATS_HIGH_PLACEHOLDER = "Alta priorità: —"
STATS_TOTAL = "Totale: {n}"
STATS_PENDING = "In attesa: {n}"
STATS_HIGH = "Alta priorità: {n}"

# ── Status filter tabs ────────────────────────────────────────────────────────

TAB_ALL_VALUE = "All"
TAB_ALL_LABEL = "Tutti"
TAB_PENDING_LABEL = "In attesa"
TAB_ACCEPTED_LABEL = "Accettati"
TAB_REJECTED_LABEL = "Rifiutati"
TAB_MORE_INFO_LABEL = "Info richiesta"

# ── Table columns ─────────────────────────────────────────────────────────────

COL_ID = "ID"
COL_CLIENT = "Cliente"
COL_DATE = "Data"
COL_DESCRIPTION = "Descrizione"
COL_PRIORITY = "Priorità"
COL_STATUS = "Stato"
COL_DOCUMENT = "Documento"
COL_ACTIONS = "Azioni"

# ── Priority / status display labels ─────────────────────────────────────────

PRIORITY_LABELS: dict[str, str] = {
    "HIGH": "ALTA",
    "MEDIUM": "MEDIA",
    "LOW": "BASSA",
}

STATUS_LABELS: dict[str, str] = {
    "PENDING": "IN ATTESA",
    "ACCEPTED": "ACCETTATO",
    "REJECTED": "RIFIUTATO",
    "MORE_INFO_REQUESTED": "INFO RICHIESTA",
}

# ── Table empty state ─────────────────────────────────────────────────────────

NO_CASES = "Nessun caso trovato con questi filtri"

# ── Shared dialog buttons ─────────────────────────────────────────────────────

CANCEL_BTN = "Annulla"
CLOSE_BTN = "Chiudi"

# ── Accept dialog ─────────────────────────────────────────────────────────────

ACCEPT_TITLE = "Accetta Caso #{id}"
ACCEPT_CLIENT_INFO = "Cliente: {username}  •  Priorità: {priority}"
ACCEPT_NOTE_LABEL = "Nota opzionale per il cliente"
ACCEPT_NOTE_PLACEHOLDER = "es. Il nostro team ti contatterà entro 48 ore."
ACCEPT_CONFIRM_BTN = "Conferma Accettazione"
ACCEPT_SUCCESS = "Caso #{id} accettato."
ACCEPT_ERROR = "Impossibile accettare il caso."

# ── Reject dialog ─────────────────────────────────────────────────────────────

REJECT_TITLE = "Rifiuta Caso #{id}"
REJECT_CLIENT_INFO = "Cliente: {username}  •  Priorità: {priority}"
REJECT_REASON_LABEL = "Motivo del rifiuto (obbligatorio)"
REJECT_REASON_PLACEHOLDER = "es. La questione non rientra nell'area di pratica dello studio."
REJECT_REASON_REQUIRED = "Devi inserire un motivo."
REJECT_CONFIRM_BTN = "Conferma Rifiuto"
REJECT_SUCCESS = "Caso #{id} rifiutato."
REJECT_ERROR = "Impossibile rifiutare il caso."

# ── Request-info dialog ───────────────────────────────────────────────────────

INFO_TITLE = "Richiedi Info — Caso #{id}"
INFO_CLIENT_INFO = "Cliente: {username}  •  Priorità: {priority}"
INFO_MSG_LABEL = "Messaggio per il cliente (obbligatorio)"
INFO_MSG_PLACEHOLDER = "es. Fornisci ulteriori dettagli su X."
INFO_MSG_REQUIRED = "Inserisci un messaggio."
INFO_CONFIRM_BTN = "Invia Richiesta"
INFO_SUCCESS = "Richiesta inviata per il caso #{id}."
INFO_ERROR = "Impossibile inviare la richiesta."

# ── Description dialog ────────────────────────────────────────────────────────

DESC_TITLE = "Caso #{id} — Descrizione"
DESC_STATUS = "Stato: {status}"
DESC_BTN_ACCEPT = "ACCETTA"
DESC_BTN_REJECT = "RIFIUTA"
DESC_BTN_INFO = "CHIEDI INFO"

# ── Edit dialog ───────────────────────────────────────────────────────────────

EDIT_TITLE = "Modifica Caso #{id}"
EDIT_CASE_TITLE_LABEL = "Titolo"
EDIT_DESCRIPTION_LABEL = "Descrizione"
EDIT_PRIORITY_LABEL = "Priorità"
EDIT_CONFIRM_BTN = "Salva modifiche"
EDIT_SUCCESS = "Caso #{id} aggiornato."
EDIT_ERROR = "Impossibile aggiornare il caso."

# ── Delete dialog ─────────────────────────────────────────────────────────────

DELETE_TITLE = "Elimina Caso #{id}"
DELETE_CONFIRM_TEXT = (
    "Sei sicuro di voler eliminare il caso <b>#{id}</b> di <b>{username}</b>?\n"
    "L'operazione non è reversibile."
)
DELETE_CONFIRM_BTN = "Elimina definitivamente"
DELETE_SUCCESS = "Caso #{id} eliminato."
DELETE_ERROR = "Impossibile eliminare il caso."
