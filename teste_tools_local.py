from app.services.llm.tools import create_calendar_event

print(
    create_calendar_event.func(
        nome="Teste Tina",
        data_hora_iso="2026-03-11 15:00"
    )
)