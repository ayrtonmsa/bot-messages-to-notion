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

intents = discord.Intents.all()

client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print(f'✅ Bot iniciado como {client.user}')


@client.event
async def on_raw_reaction_add(payload):
    print(f"📩 [raw] Reação detectada: {payload.emoji} na mensagem {payload.message_id} por {payload.user_id}")

    if str(payload.emoji.name) != "📌":
        print("⚠️ [raw] Emoji ignorado (não é 📌)")
        return

    print("✅ [raw] Emoji 📌 detectado, tentando buscar a mensagem...")

    try:
        channel = client.get_channel(payload.channel_id)
        if not channel:
            print(f"❌ [raw] Canal {payload.channel_id} não encontrado.")
            return

        message = await channel.fetch_message(payload.message_id)
        print(f"✅ [raw] Mensagem encontrada: {message.content[:100]}")
        await handle_jira_card_creation(message)

    except Exception as e:
        print("❌ [raw] Erro ao buscar mensagem:", e)


@client.event
async def on_reaction_add(reaction, user):
    print(f"📩 [normal] Reação detectada: {reaction.emoji} por {user.name}")
    if str(reaction.emoji) != "📌":
        print("⚠️ [normal] Emoji ignorado (não é 📌)")
        return

    print(f"✅ [normal] Processando mensagem: {reaction.message.content[:100]}")
    await handle_jira_card_creation(reaction.message)


def extract_project_and_clean_message(content):
    match = re.match(r"\[(\w+)\]\s*(.+)", content)
    if match:
        project_key = match.group(1)
        message_text = match.group(2)
        return project_key, message_text
    return None, content


async def handle_jira_card_creation(message):
    print("🔍 Iniciando geração do card...")

    project_key, clean_content = extract_project_and_clean_message(message.content)
    if not project_key:
        print("ℹ️ Nenhum projeto detectado, usando DEFAULT_PROJECT_KEY.")
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
        print("❌ Erro ao usar OpenAI:", e)


def create_jira_issue(summary, description, project_key):
    print(f"🚀 Enviando card para Jira ({project_key})...")
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
