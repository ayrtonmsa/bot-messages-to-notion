import discord
import requests
from openai import OpenAI
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

openAIClient = OpenAI(
  api_key=os.getenv("OPENAI_API_KEY"),
)

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

Com base apenas nessa mensagem, elabore:

1. **Título curto (até 8 palavras):**
   - Deve resumir de forma clara o assunto central.

2. **Contexto detalhado:**
   - Explique o que motivou a mensagem.
   - Indique se há um problema, dúvida, sugestão ou solicitação.
   - Inclua qualquer informação implícita que ajude a entender o cenário.

3. **Resumo objetivo (formato de card no Jira):**
   - Descreva qual é o objetivo da mensagem.
   - Se houver um problema, explique-o claramente.
   - Se houver uma solução proposta, detalhe-a.
   - Escreva de forma que qualquer membro da equipe entenda o que deve ser feito ou discutido.

Seja claro, técnico e direto ao ponto, mas com contexto suficiente para compreensão completa.
Responda em Inglês.
"""

    try:
        response = openAIClient.chat.completions.create(model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Você é um assistente que transforma mensagens em resumos claros e contextualizados para serem usados como cards no Jira."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5)

        result = response.choices[0].message.content.strip()
        title, context, summary = parse_openai_response(result)

        print(f"📝 Criando issue no projeto [{project_key}]")
        print(f"➡️ Título: {title}")
        print(f"➡️ Contexto: {context}")
        print(f"➡️ Resumo: {summary}")

        message_link = message.jump_url
        summary_with_link = f"{summary}\n\n🔗 [Ver mensagem no Discord]({message_link})"

        create_jira_issue(f"[BOT] {title}", f"{context}\n\n{summary_with_link}", project_key)

    except Exception as e:
        print("❌ Erro ao usar OpenAI:", e)


def create_jira_issue(summary, description_text, project_key):
    print(f"🚀 Enviando card para Jira ({project_key})...")
    url = f"{JIRA_BASE_URL}/rest/api/3/issue"

    auth = (JIRA_EMAIL, JIRA_TOKEN)

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    description_adf = {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": description_text
                    }
                ]
            }
        ]
    }

    payload = {
        "fields": {
            "project": {
                "key": project_key
            },
            "summary": summary,
            "description": description_adf,
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


def parse_openai_response(text):
    title = ""
    context = ""
    summary = ""

    lines = text.splitlines()
    current_section = None
    buffer = {"title": [], "context": [], "summary": []}

    for line in lines:
        line_stripped = line.strip().lower()

        if "title" in line_stripped:
            current_section = "title"
            continue
        elif "context" in line_stripped:
            current_section = "context"
            continue
        elif "summary" in line_stripped:
            current_section = "summary"
            continue

        if current_section:
            buffer[current_section].append(line.strip())

    title = " ".join(buffer["title"]).strip()
    context = " ".join(buffer["context"]).strip()
    summary = " ".join(buffer["summary"]).strip()

    return title, context, summary


client.run(DISCORD_TOKEN)
