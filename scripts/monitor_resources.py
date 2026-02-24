#!/usr/bin/env python3
"""
Resource Monitoring Script for Raspberry Pi Trading Bot
Monitors CPU, RAM, disk, and temperature
Sends alerts when thresholds are exceeded
"""
import psutil
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

THRESHOLDS = {
    "cpu_percent": 80,      # Alert if CPU > 80%
    "memory_percent": 85,   # Alert if RAM > 85%
    "disk_percent": 90,     # Alert if disk > 90%
    "temperature": 70,      # Alert if temp > 70°C (Raspberry Pi specific)
}


def check_cpu():
    """Check CPU usage"""
    cpu = psutil.cpu_percent(interval=1)
    if cpu > THRESHOLDS["cpu_percent"]:
        return f"⚠️ High CPU: {cpu:.1f}%"
    return None


def check_memory():
    """Check RAM usage"""
    memory = psutil.virtual_memory()
    if memory.percent > THRESHOLDS["memory_percent"]:
        return f"⚠️ High memory: {memory.percent:.1f}% ({memory.used / 1024**3:.1f}GB / {memory.total / 1024**3:.1f}GB)"
    return None


def check_disk():
    """Check disk usage"""
    disk = psutil.disk_usage('/')
    if disk.percent > THRESHOLDS["disk_percent"]:
        return f"⚠️ High disk usage: {disk.percent:.1f}% ({disk.used / 1024**3:.1f}GB / {disk.total / 1024**3:.1f}GB)"
    return None


def check_temperature():
    """Check CPU temperature (Raspberry Pi specific)"""
    try:
        # Raspberry Pi thermal zone
        temp_file = Path('/sys/class/thermal/thermal_zone0/temp')
        if temp_file.exists():
            temp = float(temp_file.read_text()) / 1000
            if temp > THRESHOLDS["temperature"]:
                return f"🔥 High temperature: {temp:.1f}°C"
    except Exception as e:
        return f"⚠️ Cannot read temperature: {e}"
    return None


def check_processes():
    """Check for suspicious processes or resource hogs"""
    try:
        alerts = []

        # Get top 3 CPU-consuming processes
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
            try:
                processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Sort by CPU usage
        top_cpu = sorted(processes, key=lambda x: x['cpu_percent'] or 0, reverse=True)[:3]

        # Alert if any single process uses > 50% CPU
        for proc in top_cpu:
            if proc['cpu_percent'] and proc['cpu_percent'] > 50:
                alerts.append(f"⚠️ High CPU process: {proc['name']} ({proc['cpu_percent']:.1f}%)")

        return alerts

    except Exception as e:
        return [f"⚠️ Cannot check processes: {e}"]


def check_network():
    """Check network connections (basic monitoring)"""
    try:
        connections = psutil.net_connections()
        established = [c for c in connections if c.status == 'ESTABLISHED']

        # Alert if > 100 established connections (possible DDoS)
        if len(established) > 100:
            return f"⚠️ High connection count: {len(established)} established connections"

    except (psutil.AccessDenied, Exception) as e:
        # Access denied on Windows or other systems - skip
        pass

    return None


def send_telegram_alert(message):
    """Send alert via Telegram (optional - requires bot setup)"""
    try:
        from config.settings import get_settings
        import requests

        settings = get_settings()
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"

        payload = {
            "chat_id": settings.telegram_chat_id,
            "text": f"🚨 *Resource Alert*\n\n{message}",
            "parse_mode": "Markdown"
        }

        response = requests.post(url, json=payload, timeout=5)
        return response.status_code == 200

    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")
        return False


def main():
    """Main monitoring function"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    alerts = []

    # Run all checks
    cpu_alert = check_cpu()
    if cpu_alert:
        alerts.append(cpu_alert)

    mem_alert = check_memory()
    if mem_alert:
        alerts.append(mem_alert)

    disk_alert = check_disk()
    if disk_alert:
        alerts.append(disk_alert)

    temp_alert = check_temperature()
    if temp_alert:
        alerts.append(temp_alert)

    proc_alerts = check_processes()
    if proc_alerts:
        alerts.extend(proc_alerts)

    net_alert = check_network()
    if net_alert:
        alerts.append(net_alert)

    # Report alerts
    if alerts:
        message = f"[{timestamp}] RESOURCE ALERTS:\n" + "\n".join(alerts)
        print(message)
        print()

        # Try to send Telegram notification
        telegram_message = "\n".join(alerts)
        send_telegram_alert(telegram_message)

        return 1  # Exit code 1 indicates alerts found

    else:
        # All good - optional: log status
        cpu = psutil.cpu_percent(interval=0)
        mem = psutil.virtual_memory().percent
        print(f"[{timestamp}] OK - CPU: {cpu:.1f}%, RAM: {mem:.1f}%")
        return 0  # Exit code 0 indicates no issues


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
