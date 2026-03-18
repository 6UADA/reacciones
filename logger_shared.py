import time

server_logs = []

def log_to_web(message, type='info'):
    timestamp = time.strftime("%H:%M:%S")
    log_entry = {"time": timestamp, "msg": str(message), "type": type}
    server_logs.append(log_entry)
    if len(server_logs) > 100:
        server_logs.pop(0)
    print(f"[{timestamp}] {message}")

def get_logs():
    return server_logs
