from datetime import datetime, timezone
from typing import Any, Dict

from flask import Flask, jsonify, redirect, render_template, request

from geo import geo_lookup
from storage import load_visits, save_visits


def _parse_user_agent(ua: str | None) -> Dict[str, str]:
    """Very lightweight UA parsing to guess browser and OS.

    This is intentionally simple – just enough for dashboard display.
    """
    if not ua:
        return {"browser": "Unknown", "os": "Unknown"}

    ua_lower = ua.lower()

    # Browser detection (order matters)
    if "edg" in ua_lower:
        browser = "Edge"
    elif "opr" in ua_lower or "opera" in ua_lower:
        browser = "Opera"
    elif "chrome" in ua_lower and "safari" in ua_lower and "edge" not in ua_lower:
        browser = "Chrome"
    elif "firefox" in ua_lower:
        browser = "Firefox"
    elif "safari" in ua_lower and "chrome" not in ua_lower:
        browser = "Safari"
    else:
        browser = "Other"

    # OS detection
    if "windows" in ua_lower:
        os = "Windows"
    elif "android" in ua_lower:
        os = "Android"
    elif "iphone" in ua_lower or "ipad" in ua_lower or "ios" in ua_lower:
        os = "iOS"
    elif "mac os x" in ua_lower or "macintosh" in ua_lower:
        os = "macOS"
    elif "linux" in ua_lower:
        os = "Linux"
    else:
        os = "Other"

    return {"browser": browser, "os": os}


def create_app(config: Dict[str, Any]) -> Flask:
    app = Flask(__name__)

    visits_path = config["storage"]["visits_path"]
    ip_api = config["tracking"]["ip_info_api"]
    default_target = config["tracking"]["default_target_url"]

    @app.route("/t/<token>")
    def track_click(token: str):
        """Tracking endpoint.

        - Reads visitor IP
        - Looks up geo info
        - Appends record to visits storage
        - Redirects user to a real target URL
        """
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        if ip and "," in ip:
            ip = ip.split(",")[0].strip()

        geo = geo_lookup(ip, ip_api) or {}

        # Try to build Google Maps URL if we have lat/lon
        lat = geo.get("lat")
        lon = geo.get("lon")
        google_maps_url = None
        if isinstance(lat, (int, float)) or isinstance(lon, (int, float)):
            # Numeric types only
            try:
                lat_f = float(lat)
                lon_f = float(lon)
                google_maps_url = f"https://www.google.com/maps?q={lat_f},{lon_f}"
            except Exception:
                google_maps_url = None

        ua_raw = request.headers.get("User-Agent")
        ua_info = _parse_user_agent(ua_raw)

        record = {
            "time": datetime.now(timezone.utc).isoformat(),
            "ip": ip,
            "country": geo.get("country"),
            "region": geo.get("regionName"),
            "city": geo.get("city"),
            "lat": lat,
            "lon": lon,
            "isp": geo.get("isp"),
            "token": token,
            "user_agent": ua_raw,
            "browser": ua_info["browser"],
            "os": ua_info["os"],
            "google_maps_url": google_maps_url,
        }

        visits = load_visits(visits_path)
        visits.append(record)
        save_visits(visits_path, visits)

        target_url = request.args.get("next") or default_target
        return redirect(target_url)

    @app.route("/visits", methods=["GET"])
    def list_visits():
        """Simple API to see stored visits (for testing)."""
        return jsonify(load_visits(visits_path))

    @app.route("/dashboard", methods=["GET"])
    def dashboard():
        """HTML dashboard showing visits in a table."""
        visits = load_visits(visits_path)
        return render_template("dashboard.html", visits=visits)

    @app.route("/img/<token>")
    def image_tracker(token: str):
        """Tracking endpoint that shows an image page instead of redirect.

        Usage example:
        /img/<token>?src=https://example.com/image.jpg
        """
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        if ip and "," in ip:
            ip = ip.split(",")[0].strip()

        geo = geo_lookup(ip, ip_api) or {}

        lat = geo.get("lat")
        lon = geo.get("lon")
        google_maps_url = None
        if isinstance(lat, (int, float)) or isinstance(lon, (int, float)):
            try:
                lat_f = float(lat)
                lon_f = float(lon)
                google_maps_url = f"https://www.google.com/maps?q={lat_f},{lon_f}"
            except Exception:
                google_maps_url = None

        ua_raw = request.headers.get("User-Agent")
        ua_info = _parse_user_agent(ua_raw)

        record = {
            "time": datetime.now(timezone.utc).isoformat(),
            "ip": ip,
            "country": geo.get("country"),
            "region": geo.get("regionName"),
            "city": geo.get("city"),
            "lat": lat,
            "lon": lon,
            "isp": geo.get("isp"),
            "token": token,
            "user_agent": ua_raw,
            "browser": ua_info["browser"],
            "os": ua_info["os"],
            "google_maps_url": google_maps_url,
        }

        visits = load_visits(visits_path)
        visits.append(record)
        save_visits(visits_path, visits)

        image_url = request.args.get("src") or "https://via.placeholder.com/800x500.png?text=Image"
        return render_template("image_page.html", image_url=image_url)

    return app
