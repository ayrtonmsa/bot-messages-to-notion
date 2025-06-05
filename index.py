import discord
import requests
import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
NOTION_TOKEN = os.getenv('NOTION_TOKEN')
DATABASE_ID = os.getenv('DATABASE_ID')

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')

@client.event
async def on_raw_reaction_add(payload):
    # Define emoji that triggers saving to Notion
    target_emoji = "📌"
    
    if str(payload.emoji) == target_emoji:
        channel = client.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        
        save_to_notion(message)

def save_to_notion(message):
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    data = {
        "parent": {"database_id": DATABASE_ID},
        "properties": {
            "Message content": {
                "rich_text": [
                    {"text": {"content": message.content}}
                ]
            },
            "User": {
                "rich_text": [
                    {"text": {"content": message.author.name}}
                ]
            },
            "Date & Time": {
                "date": {"start": message.created_at.isoformat()}
            },
            "Link to message": {
                "url": message.jump_url
            }
        }
    }

    response = requests.post("https://api.notion.com/v1/pages", headers=headers, json=data)
    
    if response.status_code == 200:
        print("Successfully saved to Notion!")
    else:
        print(f"Failed to save note: {response.status_code}, {response.text}")

client.run(DISCORD_TOKEN)

