import socket
import json

try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    s.connect(('127.0.0.1', 9876))
    s.sendall(json.dumps({'action': 'ping', 'data': {}}).encode('utf-8') + b'\n')
    data = s.recv(4096)
    print('PHAN HOI TU SKETCHUP:', data.decode('utf-8'))
    s.close()
except Exception as e:
    print('LỖI KẾT NỐI:', e)
