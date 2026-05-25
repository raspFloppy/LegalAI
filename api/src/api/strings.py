"""Italian user-facing strings for the LegalAI bot and notifications.

To switch language, replace the string values in this module only.
"""

# ── Bot conversation ──────────────────────────────────────────────────────────

WELCOME = (
    "👋 <b>Benvenuto su LegalAI!</b>\n\n"
    "Ti mettiamo in contatto con professionisti legali qualificati.\n\n"
    "Per iniziare, comunicaci il tuo <b>nome completo</b> (nome e cognome):"
)

NAME_INVALID = (
    "⚠️ Inserisci il tuo <b>nome completo</b> (nome e cognome, solo lettere).\n\n"
    "Esempio: <i>Mario Rossi</i>"
)

ASK_PROBLEM = (
    "Grazie, <b>{name}</b>! 👍\n\n"
    "Ora descrivi la tua situazione legale nel modo più dettagliato possibile.\n"
    "Puoi inviare un <b>messaggio di testo</b>, una <b>nota vocale</b> o allegare un "
    "<b>PDF / immagine</b> di eventuali documenti pertinenti."
)

ANALYSING = "🔍 <b>Analisi del caso in corso…</b>\n\nAttendi un momento."

QUESTION_HEADER = "❓ <b>Domanda {idx} di {total}</b>\n\n"

CASE_CONFIRMATION = (
    "{user_feedback}\n\n"
    "{priority_emoji} <b>Priorità del caso:</b> {priority}\n"
    "📁 <b>ID Caso:</b> #{case_id}\n\n"
    "Un professionista legale esaminerà il tuo caso e ti contatterà a breve."
)

DISPATCH_ERROR = (
    "⚠️ Si è verificato un errore durante l'elaborazione del tuo messaggio. Riprova."
)

DOCUMENT_SUBMITTED_TEXT = "Documento/immagine inviato per la revisione."

ADDITIONAL_INFO_SUFFIX = "\n\nInformazioni aggiuntive: {text}"

USE_BUTTONS = "Per continuare, usa i pulsanti qui sopra."

# ── Update flow (returning user) ──────────────────────────────────────────────

ASK_UPDATE_OR_NEW = (
    "Bentornato, <b>{name}</b>! 👋\n\n"
    "Hai già un caso aperto (<b>#{case_id}</b>).\n\n"
    "Vuoi aggiungere nuove informazioni a questo caso o aprire un nuovo caso?"
)

UPDATE_YES_BTN = "✅ Aggiungi info al caso #{case_id}"
UPDATE_NO_BTN = "➕ Apri un nuovo caso"

UPDATE_START = (
    "Ottimo! Descrivi le nuove informazioni o allega un documento al caso <b>#{case_id}</b>.\n"
    "Puoi inviare testo, una nota vocale o un file."
)

UPDATE_CONFIRMED = (
    "✅ <b>Le informazioni sono state aggiunte al tuo caso #{case_id}.</b>\n\n"
    "Il nostro team esaminerà le nuove informazioni e ti contatterà a breve."
)

# ── Lawyer-action notifications ───────────────────────────────────────────────

CASE_ACCEPTED = (
    "✅ <b>Il tuo caso è stato accettato.</b>\n\n"
    "Il tuo caso è stato preso in carico dall'avv. <b>{lawyer_name}</b>, "
    "che ti contatterà a breve."
)

CASE_ACCEPTED_NOTE_SUFFIX = "\n\n<i>{note}</i>"

CASE_REJECTED = (
    "❌ <b>Il tuo caso è stato esaminato.</b>\n\n"
    "Purtroppo non siamo in grado di prendere in carico il tuo caso al momento.\n\n"
    "<b>Motivo:</b> {reason}"
)

MORE_INFO_REQUESTED = (
    "📋 <b>Il nostro team ha bisogno di ulteriori informazioni sul tuo caso:</b>\n\n"
    "{message}\n\n"
    "Rispondi a questo messaggio con i dettagli richiesti."
)
