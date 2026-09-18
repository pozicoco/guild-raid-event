import requests
import time
from collections import defaultdict
from supabase import create_client
import os

URL = "https://api.wynncraft.com/v3/guild/prefix/TNSR"
DISCORD_WEBHOOK_URL = os.getenv("webhook")
INTERVAL = 60

SUPABASE_URL = os.getenv("url")
SUPABASE_KEY = os.getenv("key")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_guild_data():
    response = requests.get(URL, timeout=30)
    response.raise_for_status()
    return response.json()

def increment_player_raid(player, amount=1):
    response = supabase.rpc("increment_raid_count", {
        "p_player_name": player,
        "p_amount": amount
    }).execute()
    if response is None:
        print(f"RPCのレスポンスがNone: {player}")
        return None
    return response

def get_player_raid_count(player):
    response = (
        supabase.table("player_raids")
        .select("total_count")
        .eq("player_name", player)
        .limit(1)
        .execute()
    )
    if response is None:
        print(f"DBのレスポンスがNone: {player}")
        return 0
    if response.data:
        print(response.data)
        return response.data[0]["total_count"]
    return 0

def send_discord_webhook(raid_name, players):
    colors = {
        "The Canyon Colossus": 0x0697A0,
        "Orphion's Nexus of Light": 0xFFC83C,
        "The Nameless Anomaly": 0x2100C4,
        "Nest of the Grootslang": 0x0C9400,
        "The Wartorn Palace": 0xFF8200
    }
    description = ""
    for player in players:
        current = get_player_raid_count(player)
        description += f"**{player}: **{current} → {current + 1}\n"
    payload = {
        "embeds": [{
            "title": raid_name,
            "description": description,
            "color": colors.get(raid_name, 0x00FF00)
        }]
    }
    response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=30)
    response.raise_for_status()

def get_members_data(data):
    result = {}
    for role in ["owner", "chief", "strategist", "captain", "recruiter", "recruit"]:
        for name, value in data["members"][role].items():
            result[name] = value.copy()
    return result

def find_changes(data, previous):
    for raid, count in data.items():
        diff = count - previous.get(raid, 0)
        if 1 <= diff <= 3:
            return raid

    return None

def main():
    print("Wynncraft Guild Raid Monitor")
    print("監視開始...\n")
    data = get_guild_data()
    previous = get_members_data(data)
    print("初期データを取得しました。")
    print("60秒ごとにチェックします。\n")

    while True:
        try:
            results = {}
            time.sleep(INTERVAL)
            data = get_guild_data()
            current = get_members_data(data)

            for name, value in current.items():
                if value["restrictions"]["main_access"] == True:
                    continue

                raids_data = value["globalData"]["guildRaids"]["list"]
                previous_member = previous.get(name)

                if previous_member is None:
                    continue

                previous_raids = previous_member["globalData"]["guildRaids"]["list"]
                change = find_changes(raids_data, previous_raids)

                if change:
                    server = value["server"]
                    print(previous_raids)
                    print(raids_data)
                    results.setdefault((server, change), set()).add(name)

            print(results)

            for key, players in results.items():
                send_discord_webhook(key[1], players)
                for player in players:
                    try:
                        increment_player_raid(player)
                    except Exception as e:
                        print(f"{player} のレイド回数更新に失敗しました: {e}")

            previous = current

        except requests.RequestException as e:
            print(f"APIへの接続に失敗しました: {e}")
        except Exception as e:
            print(f"エラーが発生しました: {e}")

if __name__ == "__main__":
    main()
