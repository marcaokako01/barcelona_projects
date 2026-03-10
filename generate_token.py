from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar"]

flow = InstalledAppFlow.from_client_secrets_file(
    "google_oauth_client.json",
    SCOPES
)

creds = flow.run_local_server(
    host="localhost",
    port=8080,
    open_browser=True
)

with open("token.json", "w", encoding="utf-8") as token:
    token.write(creds.to_json())

print("Token gerado com sucesso!")