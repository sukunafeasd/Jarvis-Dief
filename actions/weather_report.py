"""Weather data for the assistant's own screen, never browser navigation."""
import json
import requests


def condition(code):
    if code == 0:
        return "Céu limpo"
    if code in (1, 2):
        return "Parcialmente nublado"
    if code == 3:
        return "Nublado"
    if code in (45, 48):
        return "Nevoeiro"
    if code in (71, 73, 75, 77, 85, 86):
        return "Neve"
    if code in (95, 96, 99):
        return "Tempestade"
    return "Chuva" if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82) else "Condição indisponível"


def weather_action(parameters, player=None, session_memory=None):
    city = str(parameters.get("city", "")).strip()
    if not city:
        from core.profile import read_profile
        city = read_profile()["city"]
    if not city:
        return json.dumps({"ok": False, "error": "Informe a cidade."}, ensure_ascii=False)
    when = parameters.get("time", "today")
    if when not in ("today", "tomorrow", "week"):
        return json.dumps({"ok": False, "error": "Período inválido."}, ensure_ascii=False)
    try:
        response = requests.get("https://geocoding-api.open-meteo.com/v1/search", params={
            "name": city, "count": 5, "language": "pt", "format": "json"}, timeout=12)
        response.raise_for_status()
        places = response.json().get("results", [])
        if not places:
            raise ValueError("Cidade não encontrada. Informe também o estado ou país.")
        place = next((p for p in places if p.get("country_code") == "BR"), places[0])
        response = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": place["latitude"], "longitude": place["longitude"], "timezone": "auto",
            "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,is_day",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max",
            "forecast_days": 7}, timeout=15)
        response.raise_for_status()
        data = response.json()
        current, daily = data["current"], data["daily"]
        days = [{"date": day, "condition": condition(daily["weather_code"][i]),
                 "code": daily["weather_code"][i], "max": daily["temperature_2m_max"][i],
                 "min": daily["temperature_2m_min"][i], "rain": daily["precipitation_probability_max"][i],
                 "wind": daily["wind_speed_10m_max"][i]} for i, day in enumerate(daily["time"])]
        selected = days[1 if when == "tomorrow" else 0]
        model = {"kind": "weather", "title": "CLIMA", "city": place["name"],
                 "region": place.get("admin1", ""), "period": when, "observed": current["time"],
                 "temperature": current["temperature_2m"] if when != "tomorrow" else selected["max"],
                 "condition": condition(current["weather_code"]) if when != "tomorrow" else selected["condition"],
                 "code": current["weather_code"] if when != "tomorrow" else selected["code"],
                 "humidity": current["relative_humidity_2m"] if when != "tomorrow" else None,
                 "wind": current["wind_speed_10m"] if when != "tomorrow" else selected["wind"],
                 "rain": selected["rain"], "is_day": current["is_day"], "forecast": days,
                 "source": "Open-Meteo"}
        if player:
            player.show_manifestation(model)
        return json.dumps({"ok": True, "screen_shown": bool(player), "weather": model,
                           "instruction": "Explique estes dados em português enquanto estão na tela. Não abra navegador."}, ensure_ascii=False)
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as error:
        if player:
            player.show_manifestation({"kind": "weather", "title": "CLIMA", "city": city,
                                       "error": "Não foi possível consultar o clima agora."})
        return json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False)


TOOL = {"name": "weather_report", "description": "Consulta clima real e mostra a atmosfera dentro da tela do Jarvis. Nunca abre navegador. Fale sobre os dados retornados enquanto são exibidos.",
        "parameters": {"type": "OBJECT", "properties": {
            "city": {"type": "STRING", "description": "Nome da cidade"},
            "time": {"type": "STRING", "enum": ["today", "tomorrow", "week"]}}},
        "handler": weather_action}
