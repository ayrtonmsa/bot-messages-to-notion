import discord
import requests
import openai
import os
import re
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL")
DEFAULT_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print(f'✅ Bot iniciado como {client.user}')


@client.event
async def on_raw_reaction_add(payload):
    if str(payload.emoji.name) != "📌":
        return

    channel = client.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)

    await handle_jira_card_creation(message)


def extract_project_and_clean_message(content):
    """
    Detecta um prefixo como [PROJ] e retorna o código do projeto e o texto limpo.
    """
    match = re.match(r"\[(\w+)\]\s*(.+)", content)
    if match:
        project_key = match.group(1)
        message_text = match.group(2)
        return project_key, message_text
    return None, content


async def handle_jira_card_creation(message):
    project_key, clean_content = extract_project_and_clean_message(message.content)

    if not project_key:
        print("Nenhum projeto detectado, usando o padrão.")
        project_key = DEFAULT_PROJECT_KEY

    prompt = f"""
A seguinte mensagem foi enviada no Discord:

\"{clean_content}\"

Gere com base apenas nessa mensagem:
1. Um título curto (até 8 palavras)
2. Um contexto geral
3. Um resumo de uma linha que explique o objetivo da mensagem, como se fosse para criar um card no Jira.
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Você é um assistente que ajuda a criar resumos de mensagens para registrar no Jira."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5
        )

        result = response.choices[0].message.content.strip()
        lines = result.splitlines()

        title = lines[0].replace("Título:", "").strip()
        context = lines[1].replace("Contexto:", "").strip()
        summary = lines[2].replace("Resumo:", "").strip()

        print(f"📝 Criando issue no projeto [{project_key}]")
        print(f"➡️ Título: {title}")
        print(f"➡️ Resumo: {summary}")

        message_link = message.jump_url
        summary_with_link = f"{summary}\n\n🔗 [Ver mensagem no Discord]({message_link})"

        create_jira_issue(title, f"{context}\n\n{summary_with_link}", project_key)

    except Exception as e:
        print("Erro ao usar OpenAI:", e)


def create_jira_issue(summary, description, project_key):
    url = f"{JIRA_BASE_URL}/rest/api/3/issue"

    auth = (JIRA_EMAIL, JIRA_TOKEN)

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    payload = {
        "fields": {
            "project": {
                "key": project_key
            },
            "summary": summary,
            "description": description,
            "issuetype": {
                "name": "Task"
            }
        }
    }

    response = requests.post(url, json=payload, headers=headers, auth=auth)

    if response.status_code == 201:
        print(f"✅ Card criado no Jira [{project_key}]!")
    else:
        print(f"❌ Erro ao criar card no Jira {project_key}: {response.status_code}")
        print(response.text)


client.run(DISCORD_TOKEN)
