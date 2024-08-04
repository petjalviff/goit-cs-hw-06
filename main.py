import mimetypes
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import socket
from datetime import datetime
from pymongo import MongoClient
from multiprocessing import Process
import logging

# Налаштування логування
logging.basicConfig(level=logging.INFO, format="{asctime} - {levelname} - {message}", style='{')

class HttpHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Обробка POST-запитів
        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length)
        data_dict = urllib.parse.parse_qs(post_data.decode())
        logging.info(f"Data from Form: {data_dict}")
        
        if self.path == "/message.html":
            try:
                self.send_data_to_socket(data_dict)
                self.send_response(302)
                self.send_header("Location", "/message.html")
                self.end_headers()
            except Exception as e:
                logging.error(f"Failed to send data to socket: {e}")
                self.send_error(500, "Server error: Failed to process data")

    def do_GET(self):
        # Обробка GET-запитів
        file_path = self.path.lstrip("/")
        if file_path == "":
            file_path = "index.html"

        file_path = os.path.join("front-init", file_path)
        self.serve_file(file_path)

    def serve_file(self, path):
    # Визначення MIME типу
        if "style.css" in path:
            content_type = "text/css"
        elif "logo.png" in path:
            content_type = "image/png"
        else:
            content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"

        try:
            with open(path, "rb") as file:
                self.send_response(200)
                self.send_header("Content-type", content_type)
                self.end_headers()
                self.wfile.write(file.read())
        except FileNotFoundError:
            self.handle_error(404)
        except Exception as e:
            logging.error(f"Error serving file {path}: {e}")
            self.send_error(500, "Server error: Failed to read file")

    def handle_error(self, status_code):
        # Обробка помилок
        error_file = os.path.join("front-init", "error.html")
        try:
            with open(error_file, "rb") as file:
                self.send_response(status_code)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(file.read())
        except Exception as e:
            logging.error(f"Error serving error page: {e}")
            self.send_error(status_code, "Error serving error page")

    def send_data_to_socket(self, data):
        # Відправлення даних до сокету
        data_str = "&".join(f"{k}={v[0]}" for k, v in data.items())
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(("localhost", 5000))
                s.sendall(data_str.encode())
        except Exception as e:
            logging.error(f"Failed to send data over socket: {e}")
            raise

def run_socket_server(port=5000):
    # Запуск сервера сокетів
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(("", port))
        server_socket.listen(5)
        logging.info(f"Socket server listening on port {port}...")

        while True:
            client_socket, addr = server_socket.accept()
            logging.info(f"Connected by {addr}")
            with client_socket:
                while True:
                    data = client_socket.recv(1024)
                    if not data:
                        break
                    data_str = data.decode()
                    data_parts = data_str.split("&")
                    username = data_parts[0].split("=")[1]
                    message = data_parts[1].split("=")[1]
                    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                    data_dict = {
                        "date": date,
                        "username": username,
                        "message": message,
                    }
                    save_to_mongo(data_dict)
    except Exception as e:
        logging.error(f"Socket server error: {e}")

def save_to_mongo(data):
    # Збереження даних в MongoDB
    try:
        client = MongoClient("mongo", 27017)
        db = client["message_db"]
        collection = db.messages
        collection.insert_one(data)
        logging.info(f"Data saved to MongoDB: {data}")
    except Exception as e:
        logging.error(f"Failed to save data to MongoDB: {e}")

def run_http_server(port=3000, handler_class=HttpHandler):
    # Запуск HTTP сервера
    try:
        server_address = ("", port)
        httpd = HTTPServer(server_address, handler_class)
        logging.info(f"HTTP server running on port {port}...")
        httpd.serve_forever()
    except Exception as e:
        logging.error(f"HTTP server failed to start: {e}")

def run_servers():
    # Запуск серверів у різних процесах
    http_process = Process(target=run_http_server, args=(3000,))
    socket_process = Process(target=run_socket_server, args=(5000,))

    http_process.start()
    socket_process.start()

    http_process.join()
    socket_process.join()

if __name__ == "__main__":
    run_servers()