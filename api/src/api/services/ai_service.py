import json
from typing import Optional

from google import genai
from google.genai import types
from pydantic import BaseModel

from api.database.models import CasePriority
from api.config import settings

_ANALYSIS_PROMPT = """Sei un assistente per la presa in carico di casi legali presso uno studio legale. Un cliente ha inviato una richiesta legale. Analizzala e rispondi SOLO con un JSON valido corrispondente allo schema seguente.

Regole per la priorità:
- HIGH: materia penale, violenza domestica, affidamento urgente di minori, sfratto imminente, detenzione per immigrazione, provvedimenti d'urgenza
- MEDIUM: controversie civili, diritto del lavoro, questioni contrattuali, recupero crediti, diritto di famiglia generico
- LOW: domande legali generali, revisione documenti, pianificazione successoria, costituzione d'impresa

Regole per il feedback:
- Non fornire mai consulenza legale specifica
- Sii empatico e professionale (massimo 2-3 frasi)
- Riconosci la situazione e spiega che un avvocato esaminerà il caso
- Non promettere risultati

Regole per le domande di chiarimento:
- Chiedi solo se mancano informazioni che cambierebbero la priorità o la descrizione
- Massimo 2 domande
- Ogni domanda DEVE avere 2-4 opzioni di risposta brevi (adatte a pulsanti)
- Se non serve alcun chiarimento, imposta "questions" come lista vuota

Schema JSON:
{{
  "title": "Titolo del caso in 5-7 parole",
  "description": "Descrizione professionale in 2-3 frasi per il dashboard dell'avvocato",
  "priority": "HIGH | MEDIUM | LOW",
  "user_feedback": "Risposta empatica da inviare al cliente",
  "questions": [
    {{
      "question": "Testo della domanda di chiarimento",
      "options": ["Opzione A", "Opzione B"]
    }}
  ]
}}

Tutti i campi di testo devono essere scritti in italiano.

Messaggio del cliente:
{message}
{context}"""

_TRANSCRIPTION_PROMPT = """Il file audio allegato è un messaggio vocale di un cliente che cerca assistenza legale.
Trascrivi l'audio in modo accurato e restituisci SOLO il testo della trascrizione, senza altro."""


class ClarifyingQuestion(BaseModel):
    """A single AI-generated clarifying question with selectable options.

    Attributes:
        question: The question text to display to the user.
        options: 2-4 short answer strings suitable for inline keyboard buttons.
    """

    question: str
    options: list[str]


class CaseAnalysisResult(BaseModel):
    """Structured output produced by the AI case-analysis step.

    Attributes:
        title: Short case title for the dashboard table.
        description: Longer description for the lawyer's review.
        priority: Urgency level assigned by the AI.
        user_feedback: Empathetic reply to send back to the client.
        questions: Optional clarifying questions (up to 2) with button options.
        raw_transcription: Voice transcription text when input was audio.
    """

    title: str
    description: str
    priority: CasePriority
    user_feedback: str
    questions: list[ClarifyingQuestion] = []
    raw_transcription: Optional[str] = None


class AIService:
    """Gemini-backed service for legal case analysis and voice transcription.

    Args:
        api_key: Google AI API key.
        model_name: Gemini model identifier (default ``gemini-1.5-pro``).
    """

    def __init__(
        self,
        api_key: str = settings.gemini_api_key,
        model_name: str = settings.gemini_model,
    ) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model_name = model_name

    async def analyse_case(
        self,
        text: str,
        file_bytes: Optional[bytes] = None,
        file_mime_type: Optional[str] = None,
        previous_answers: Optional[dict[int, str]] = None,
    ) -> CaseAnalysisResult:
        """Analyse a client's legal query and return structured AI output.

        When ``file_bytes`` are provided the file is sent inline to Gemini
        alongside the text prompt, enabling multimodal analysis of documents
        and images.

        Args:
            text: The client's message text or voice transcription.
            file_bytes: Optional raw bytes of an attached document or image.
            file_mime_type: MIME type of ``file_bytes`` when provided.
            previous_answers: Mapping of question index → chosen answer from
                a prior clarification round to include as extra context.

        Returns:
            A ``CaseAnalysisResult`` with title, description, priority,
            user feedback, and optional follow-up questions.
        """
        context_lines: list[str] = []
        if previous_answers:
            context_lines.append("\nAdditional context from client answers:")
            for idx, answer in previous_answers.items():
                context_lines.append(f"  Q{idx + 1}: {answer}")

        prompt = _ANALYSIS_PROMPT.format(
            message=text,
            context="\n".join(context_lines),
        )

        contents: list = []
        if file_bytes and file_mime_type:
            contents.append(
                types.Part.from_bytes(data=file_bytes, mime_type=file_mime_type)
            )
        contents.append(prompt)

        response = await self._client.aio.models.generate_content(
            model=self._model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )

        raw = json.loads(response.text)
        questions = [
            ClarifyingQuestion(question=q["question"], options=q["options"])
            for q in raw.get("questions", [])
        ]

        return CaseAnalysisResult(
            title=raw["title"],
            description=raw["description"],
            priority=CasePriority(raw["priority"]),
            user_feedback=raw["user_feedback"],
            questions=questions,
        )

    async def transcribe_voice(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/ogg",
    ) -> str:
        """Transcribe an audio voice message to plain text.

        Args:
            audio_bytes: Raw audio file bytes.
            mime_type: MIME type of the audio (e.g. ``"audio/ogg"``).

        Returns:
            The transcribed text string.
        """
        response = await self._client.aio.models.generate_content(
            model=self._model_name,
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                _TRANSCRIPTION_PROMPT,
            ],
        )
        return response.text.strip()
