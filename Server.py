import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import socket
import threading
import sqlite3
from datetime import datetime


HOST = '0.0.0.0'
PORT = 4001
DB_NAME = 'Praktikum_bd.db'
COLOR_BG = "#D6D6D6"
COLOR_TEXT = "#000000"
COLOR_PROGRESS_BLUE = "#333399"
COLOR_DANGER = "#A52A2A"

class ServerAdminPanel:
    def __init__(self, root):
        self.root = root
        self.root.title("System Overview")
        self.root.geometry("750x550")
        self.root.configure(bg=COLOR_BG)
        self.active_connections = {}
        self.init_db()
        self.setup_ui()

        threading.Thread(target=self.start_server, daemon=True).start()

    def init_db(self):
        conn = sqlite3.connect(DB_NAME)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Clients (
                    IP TEXT PRIMARY KEY,
                    Hostname TEXT,
                    Status TEXT,
                    LastSeen TIMESTAMP
                )
            ''')
            cursor.execute("UPDATE Clients SET Status = 'OFFLINE'")
            conn.commit()
        finally:
            conn.close()

    def setup_ui(self):
        header = tk.Frame(self.root, bg=COLOR_BG, bd=2, relief="raised")
        header.pack(fill="x", padx=10, pady=(10, 5))
        tk.Label(header, text="OPERATING SYSTEM MONITOR", bg=COLOR_BG, font=("Verdana", 10, "bold")).pack(pady=5)
        control_frame = tk.Frame(self.root, bg=COLOR_BG)
        control_frame.pack(fill="x", padx=10, pady=5)

        btn_ps = tk.Button(control_frame, text="Execute PowerShell", bg=COLOR_BG, font=("Verdana", 8),
                           relief="raised", bd=2, command=self.prompt_and_send_ps)
        btn_ps.pack(side="left", padx=(0, 5))

        btn_shutdown = tk.Button(control_frame, text="Power Off", bg=COLOR_BG, fg=COLOR_DANGER,
                                 font=("Verdana", 8, "bold"), relief="raised", bd=2,
                                 command=lambda: self.send_command("CMD:SHUTDOWN"))
        btn_shutdown.pack(side="left")

        container = tk.Frame(self.root, bg=COLOR_BG, bd=2, relief="sunken")
        container.pack(fill="both", expand=True, padx=10, pady=5)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="white", rowheight=25, font=("Verdana", 9))
        style.configure("Treeview.Heading", background=COLOR_BG, relief="raised", font=("Verdana", 9, "bold"))
        style.map('Treeview', background=[('selected', COLOR_PROGRESS_BLUE)])

        self.tree = ttk.Treeview(container, columns=("ip", "name", "stat", "time"), show="headings")
        self.tree.heading("ip", text="Network Address")
        self.tree.heading("name", text="Machine Name")
        self.tree.heading("stat", text="State")
        self.tree.heading("time", text="Last Active")

        for col in ("ip", "name", "stat", "time"):
            self.tree.column(col, anchor="center", width=120)

        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.status_frame = tk.Frame(self.root, bg=COLOR_BG, bd=1, relief="sunken")
        self.status_frame.pack(fill="x", side="bottom", padx=10, pady=10)

        self.status_label = tk.Label(self.status_frame, text="System Ready", bg=COLOR_BG, font=("Verdana", 8))
        self.status_label.pack(side="left", padx=5)

        btn_clear = tk.Button(self.root, text="Clear History", bg=COLOR_BG, relief="raised", bd=2,
                              command=self.clear_offline, font=("Verdana", 8))
        btn_clear.pack(side="right", padx=10, pady=(0, 10))

        self.refresh_table()

    def start_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((HOST, PORT))
            server.listen()
            while True:
                conn, addr = server.accept()
                threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()
        except Exception as e:
            print(f"Socket error: {e}")

    def handle_client(self, conn, addr):
        ip = addr[0]
        self.active_connections[ip] = conn
        try:
            hostname = conn.recv(1024).decode('utf-8', errors='ignore').strip()
            if not hostname: return

            self.db_update(ip, hostname, "ONLINE")

            while True:
                data = conn.recv(1024)
                if not data: break
        except:
            pass
        finally:
            if ip in self.active_connections:
                del self.active_connections[ip]
            self.db_update(ip, None, "OFFLINE")
            conn.close()

    def prompt_and_send_ps(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Selection Error", "Please select a target machine first.")
            return

        args = simpledialog.askstring("PowerShell Command", "Enter arguments:")
        if args is not None:
            if args.strip() == "":
                self.send_command("CMD:POWERSHELL")
            else:
                self.send_command(f"CMD:PS_ARGS:{args}")

    def send_command(self, cmd):
        selected = self.tree.selection()
        if not selected:
            return
        item = self.tree.item(selected[0])
        ip = item['values'][0]
        status = item['values'][2]

        if status != "ONLINE" or ip not in self.active_connections:
            messagebox.showerror("Link Error", f"Machine {ip} is offline or unreachable :(")
            return

        if cmd == "CMD:SHUTDOWN":
            if not messagebox.askyesno("Achtung!", f"Halt target system {ip}?\nUnsaved data will be lost . . ."):
                return
        try:
            self.active_connections[ip].send(cmd.encode('utf-8'))
            messagebox.showinfo("Success", f"Command sequence sent to {ip}.")
        except Exception as e:
            messagebox.showerror("Execution Failed", str(e))

    def db_update(self, ip, name, status):
        conn = sqlite3.connect(DB_NAME)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            cursor = conn.cursor()
            if status == "ONLINE":
                cursor.execute('''
                    INSERT INTO Clients (IP, Hostname, Status, LastSeen) VALUES (?, ?, ?, ?)
                    ON CONFLICT(IP) DO UPDATE SET Status=?, LastSeen=?, Hostname=COALESCE(?, Hostname)
                ''', (ip, name, status, now, status, now, name))
            else:
                cursor.execute("UPDATE Clients SET Status=?, LastSeen=? WHERE IP=?", (status, now, ip))
            conn.commit()
        finally:
            conn.close()

        self.root.after(0, self.refresh_table)

    def refresh_table(self):
        selected_item = self.tree.selection()
        selected_ip = self.tree.item(selected_item[0])['values'][0] if selected_item else None

        for item in self.tree.get_children():
            self.tree.delete(item)

        conn = sqlite3.connect(DB_NAME)
        online_count = 0
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Clients ORDER BY Status DESC, LastSeen DESC")
            rows = cursor.fetchall()
            for row in rows:
                tag = "off" if row[2] == "OFFLINE" else "on"
                if row[2] == "ONLINE": online_count += 1

                item_id = self.tree.insert("", "end", values=row, tags=(tag,))
                if row[0] == selected_ip:
                    self.tree.selection_set(item_id)
        finally:
            conn.close()

        self.tree.tag_configure("off", foreground="#666666")
        self.tree.tag_configure("on", foreground=COLOR_PROGRESS_BLUE)
        self.status_label.config(text=f"Active Connections: {online_count} | Database Records: {len(rows)}")

    def clear_offline(self):
        if messagebox.askyesno("System", "Clean all offline records?"):
            conn = sqlite3.connect(DB_NAME)
            conn.execute("DELETE FROM Clients WHERE Status='OFFLINE'")
            conn.commit()
            conn.close()
            self.refresh_table()

if __name__ == "__main__":
    root = tk.Tk()
    app = ServerAdminPanel(root)
    root.mainloop()