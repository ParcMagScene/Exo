"""local_info.py - Informations locales en temps réel pour EXO.

Fournit au BrainEngine :
- Date et heure locale (fuseau horaire configuré)
- Météo actuelle (Open-Meteo API, gratuit, sans clé)
- Éphémérides (lever/coucher du soleil)
- Infos de localisation

Configuration via .env :
  EXO_CITY, EXO_COUNTRY, EXO_TIMEZONE, EXO_LATITUDE, EXO_LONGITUDE
"""

import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

import aiohttp

logger = logging.getLogger(__name__)

# ─── Mapping WMO weather codes → description FR ──────────
WMO_CODES: Dict[int, str] = {
    0: "ciel dégagé",
    1: "principalement dégagé",
    2: "partiellement nuageux",
    3: "couvert",
    45: "brouillard",
    48: "brouillard givrant",
    51: "bruine légère",
    53: "bruine modérée",
    55: "bruine forte",
    56: "bruine verglaçante légère",
    57: "bruine verglaçante forte",
    61: "pluie légère",
    63: "pluie modérée",
    65: "pluie forte",
    66: "pluie verglaçante légère",
    67: "pluie verglaçante forte",
    71: "neige légère",
    73: "neige modérée",
    75: "neige forte",
    77: "grains de neige",
    80: "averses légères",
    81: "averses modérées",
    82: "averses violentes",
    85: "averses de neige légères",
    86: "averses de neige fortes",
    95: "orage",
    96: "orage avec grêle légère",
    99: "orage avec grêle forte",
}


class LocalInfo:
    """Fournit les informations locales (heure, météo, localisation)."""

    def __init__(self):
        self.city = os.getenv("EXO_CITY", "Saint-Étienne")
        self.country = os.getenv("EXO_COUNTRY", "France")
        self.timezone_name = os.getenv("EXO_TIMEZONE", "Europe/Paris")
        self.latitude = float(os.getenv("EXO_LATITUDE", "45.4397"))
        self.longitude = float(os.getenv("EXO_LONGITUDE", "4.3872"))

        # Cache météo (éviter trop d'appels API)
        self._weather_cache: Optional[Dict[str, Any]] = None
        self._weather_cache_time: Optional[datetime] = None
        self._cache_ttl = 600  # 10 minutes

        logger.info("✅ LocalInfo : %s, %s (%.4f, %.4f)",
                     self.city, self.country, self.latitude, self.longitude)

    # ─── Heure locale ─────────────────────────────────────

    def get_local_datetime(self) -> datetime:
        """Retourne la date/heure locale avec le bon fuseau."""
        try:
            from zoneinfo import ZoneInfo  # Python 3.9+
            tz = ZoneInfo(self.timezone_name)
        except (ImportError, KeyError, Exception):
            # Fallback si zoneinfo/tzdata absent : UTC+1 pour FR
            tz = timezone(timedelta(hours=1))

        return datetime.now(tz)

    def get_time_info(self) -> Dict[str, str]:
        """Retourne les informations temporelles locales formatées."""
        now = self.get_local_datetime()

        # Jour de la semaine en français
        jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
        mois = ["janvier", "février", "mars", "avril", "mai", "juin",
                "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

        jour_semaine = jours[now.weekday()]
        mois_nom = mois[now.month - 1]

        # Moment de la journée
        h = now.hour
        if 5 <= h < 12:
            moment = "matin"
        elif 12 <= h < 14:
            moment = "midi"
        elif 14 <= h < 18:
            moment = "après-midi"
        elif 18 <= h < 22:
            moment = "soirée"
        else:
            moment = "nuit"

        return {
            "heure": now.strftime("%H:%M"),
            "date": f"{jour_semaine} {now.day} {mois_nom} {now.year}",
            "moment": moment,
            "timestamp_iso": now.isoformat(),
            "fuseau": self.timezone_name,
        }

    # ─── Météo (Open-Meteo, gratuit, sans clé API) ───────

    async def get_weather(self) -> Dict[str, Any]:
        """Récupère la météo actuelle via Open-Meteo (gratuit)."""

        # Check cache
        if self._weather_cache and self._weather_cache_time:
            elapsed = (datetime.now() - self._weather_cache_time).total_seconds()
            if elapsed < self._cache_ttl:
                return self._weather_cache

        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                       "weather_code,wind_speed_10m,wind_direction_10m,"
                       "precipitation,cloud_cover",
            "daily": "sunrise,sunset,temperature_2m_max,temperature_2m_min,"
                     "precipitation_sum,uv_index_max",
            "timezone": self.timezone_name,
            "forecast_days": 2,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        logger.warning("Open-Meteo HTTP %d", resp.status)
                        return self._fallback_weather()

                    data = await resp.json()

            current = data.get("current", {})
            daily = data.get("daily", {})

            weather_code = current.get("weather_code", 0)
            description = WMO_CODES.get(weather_code, f"code {weather_code}")

            result = {
                "temperature": current.get("temperature_2m"),
                "ressenti": current.get("apparent_temperature"),
                "humidite": current.get("relative_humidity_2m"),
                "description": description,
                "vent_kmh": current.get("wind_speed_10m"),
                "precipitation_mm": current.get("precipitation"),
                "couverture_nuageuse": current.get("cloud_cover"),
                "lever_soleil": daily.get("sunrise", [None])[0],
                "coucher_soleil": daily.get("sunset", [None])[0],
                "temp_max_jour": daily.get("temperature_2m_max", [None])[0],
                "temp_min_jour": daily.get("temperature_2m_min", [None])[0],
                "precipitation_jour": daily.get("precipitation_sum", [None])[0],
                "uv_max": daily.get("uv_index_max", [None])[0],
            }

            # Prévision demain
            if len(daily.get("temperature_2m_max", [])) > 1:
                result["demain_max"] = daily["temperature_2m_max"][1]
                result["demain_min"] = daily["temperature_2m_min"][1]
                result["demain_precipitation"] = daily["precipitation_sum"][1]

            # Cache
            self._weather_cache = result
            self._weather_cache_time = datetime.now()

            logger.info("🌤 Météo : %s, %.1f°C ressentie %.1f°C",
                        description, result["temperature"], result["ressenti"])

            return result

        except Exception as e:
            logger.error("Erreur météo Open-Meteo : %s", e)
            return self._fallback_weather()

    def _fallback_weather(self) -> Dict[str, Any]:
        """Météo fallback quand l'API est indisponible."""
        return {
            "temperature": None,
            "description": "données météo indisponibles",
            "erreur": True,
        }

    # ─── Résumé complet pour le prompt système ────────────

    async def get_context_summary(self) -> str:
        """Génère un résumé textuel de toutes les infos locales pour le prompt."""
        time_info = self.get_time_info()
        weather = await self.get_weather()

        lines = [
            f"📍 Localisation : {self.city}, {self.country}",
            f"🕐 Date/heure : {time_info['date']}, {time_info['heure']} ({time_info['moment']})",
            f"🌡 Fuseau horaire : {time_info['fuseau']}",
        ]

        if weather.get("temperature") is not None:
            lines.append(
                f"🌤 Météo actuelle : {weather['description']}, "
                f"{weather['temperature']}°C (ressenti {weather['ressenti']}°C)"
            )
            lines.append(
                f"   Humidité {weather['humidite']}%, "
                f"vent {weather['vent_kmh']} km/h, "
                f"nuages {weather['couverture_nuageuse']}%"
            )
            if weather.get("lever_soleil"):
                lever = weather["lever_soleil"].split("T")[1][:5] if "T" in str(weather["lever_soleil"]) else weather["lever_soleil"]
                coucher = weather["coucher_soleil"].split("T")[1][:5] if "T" in str(weather["coucher_soleil"]) else weather["coucher_soleil"]
                lines.append(f"   Soleil : lever {lever}, coucher {coucher}")
            if weather.get("temp_max_jour") is not None:
                lines.append(
                    f"   Aujourd'hui : {weather['temp_min_jour']}°C → {weather['temp_max_jour']}°C, "
                    f"précipitations {weather['precipitation_jour']}mm, UV {weather['uv_max']}"
                )
            if weather.get("demain_max") is not None:
                lines.append(
                    f"   Demain : {weather['demain_min']}°C → {weather['demain_max']}°C, "
                    f"précipitations {weather['demain_precipitation']}mm"
                )
        else:
            lines.append("🌤 Météo : données indisponibles")

        return "\n".join(lines)
