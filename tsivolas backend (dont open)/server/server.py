import socket
import threading
import json
import time

HOST = '127.0.0.1'
PORT = 5000

clients = {}
questions = []
current_q_idx = 0
lock = threading.Lock()
QUESTION_TIME = 15
MAX_SCORE = 1000
answer_times = {}
waiting_for_start = True

with open('questions.json', 'r', encoding='utf-8') as f:
    questions = json.load(f)

def broadcast(message):
    with lock:
        for info in clients.values():
            try:
                info['conn'].sendall(message.encode('utf-8'))
            except:
                pass

def send_to(conn, msg_obj):
    conn.sendall(json.dumps(msg_obj).encode('utf-8'))

def handle_client(conn, addr):
    data = conn.recv(1024)
    reg = json.loads(data.decode('utf-8'))
    if reg.get('type') != 'register':
        conn.close()
        return
    name = reg.get('name', str(addr))
    with lock:
        clients[addr] = {'conn': conn, 'name': name, 'score': 0}
        player_list = [info['name'] for info in clients.values()]
        print(f"🔹 Players Joined: {', '.join(player_list)}")
    send_to(conn, {'type': 'welcome', 'message': f'Welcome, {name}!'})
    while waiting_for_start:
        time.sleep(1)
    while True:
        try:
            data = conn.recv(1024)
            if not data:
                break
            answer = json.loads(data.decode('utf-8'))
            if answer.get('type') == 'answer':
                handle_answer(addr, answer)
        except:
            break
    with lock:
        clients.pop(addr, None)
    conn.close()

def handle_answer(addr, answer):
    global current_q_idx
    q_idx = answer.get('index')
    ans_idx = answer.get('answer')
    key = (addr, q_idx)
    if key in answer_times:
        return
    answer_times[key] = time.time()
    q = questions[q_idx]
    correct_idx = q['correct']
    if ans_idx == correct_idx:
        elapsed = answer_times[key] - question_start_time
        pts = max(int(MAX_SCORE * (1 - elapsed / QUESTION_TIME)), 100)
        with lock:
            clients[addr]['score'] += pts

def quiz_master():
    global current_q_idx, question_start_time, waiting_for_start
    print("🟢 Waiting for players to join... Press ENTER to start the quiz.")
    input("Press ENTER to start the quiz.\n")
    waiting_for_start = False
    broadcast(json.dumps({'type': 'start', 'num_questions': len(questions), 'time_per_question': QUESTION_TIME}))
    while current_q_idx < len(questions):
        q = questions[current_q_idx]
        msg = {'type': 'question', 'index': current_q_idx, 'question': q['question'], 'options': q['options']}
        broadcast(json.dumps(msg))
        question_start_time = time.time()
        time.sleep(QUESTION_TIME)
        with lock:
            leaderboard = sorted(
                [(info['name'], info['score']) for info in clients.values()],
                key=lambda x: x[1], reverse=True
            )
        broadcast(json.dumps({'type': 'leaderboard', 'data': leaderboard}))
        current_q_idx += 1
    broadcast(json.dumps({'type': 'end'}))

if __name__ == '__main__':
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        threading.Thread(target=quiz_master, daemon=True).start()
        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
