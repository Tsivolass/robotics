import socket
import threading
import json
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.uix.textinput import TextInput
from kivy.core.window import Window

# Set global background color (R, G, B, A)
Window.clearcolor = (0.1, 0.1, 0.1, 1)  # dark gray background

SERVER_HOST = '127.0.0.1'
SERVER_PORT = 5000

class NetworkClient(threading.Thread):
    def __init__(self, app, name):
        super().__init__(daemon=True)
        self.app = app
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((SERVER_HOST, SERVER_PORT))
        self.sock.sendall(json.dumps({'type': 'register', 'name': name}).encode('utf-8'))
        self.start()

    def run(self):
        buffer = ''
        while True:
            data = self.sock.recv(4096)
            if not data:
                break
            buffer += data.decode('utf-8')
            while '}{' in buffer:
                chunk, buffer = buffer.split('}{', 1)
                chunk += '}'
                self.dispatch_message(chunk)
                buffer = '{' + buffer
            if buffer:
                self.dispatch_message(buffer)

    def dispatch_message(self, msg_text):
        try:
            obj = json.loads(msg_text)
            Clock.schedule_once(lambda dt, m=obj: self.app.handle_server_message(m))
        except:
            pass

    def send_answer(self, question_idx, answer_idx):
        msg = {'type': 'answer', 'index': question_idx, 'answer': answer_idx}
        self.sock.sendall(json.dumps(msg).encode('utf-8'))

class IntroScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=40, spacing=20)
        layout.add_widget(Label(text='Enter your name:', font_size=28, color=(1, 1, 1, 1)))
        self.name_input = TextInput(font_size=24, size_hint=(1, 0.2), background_color=(1, 1, 1, 0.1), foreground_color=(1, 1, 1, 1))
        layout.add_widget(self.name_input)
        btn = Button(text='Join Quiz', size_hint=(1, 0.2), background_color=(0.2, 0.6, 1, 1), color=(1, 1, 1, 1))
        btn.bind(on_press=self.join_quiz)
        layout.add_widget(btn)
        self.add_widget(layout)

    def join_quiz(self, instance):
        name = self.name_input.text.strip() or 'Player'
        self.manager.app.network = NetworkClient(self.manager.app, name)
        self.manager.current = 'quiz'

class QuizScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', spacing=20, padding=20)
        self.timer_label = Label(text='', font_size=24, color=(1, 1, 0.2, 1))
        self.layout.add_widget(self.timer_label)
        self.add_widget(self.layout)
        self.clear_layout('Waiting for quiz to start...')

    def clear_layout(self, msg):
        self.layout.clear_widgets()
        self.layout.add_widget(self.timer_label)
        self.timer_label.text = ''
        self.layout.add_widget(Label(text=msg, font_size=24, color=(1, 1, 1, 1)))

    def display_question(self, q):
        self.layout.clear_widgets()
        self.timer = 15
        self.timer_label.text = f'Time left: {self.timer}s'
        self.layout.add_widget(self.timer_label)
        self.question_buttons = []
        self.layout.add_widget(Label(text=q['question'], font_size=26, color=(1, 1, 1, 1)))
        for idx, opt in enumerate(q['options']):
            btn = Button(text=opt, size_hint=(1, 0.2),
                         background_color=(0.3, 0.7, 0.3, 1),
                         color=(1, 1, 1, 1))
            btn.bind(on_press=lambda inst, i=idx: self.send_answer(i))
            self.question_buttons.append(btn)
            self.layout.add_widget(btn)
        self.countdown = Clock.schedule_interval(self.update_timer, 1)

    def update_timer(self, dt):
        self.timer -= 1
        self.timer_label.text = f'Time left: {self.timer}s'
        if self.timer <= 0:
            self.countdown.cancel()
            for btn in getattr(self, 'question_buttons', []):
                btn.disabled = True
            self.clear_layout("Time's up! Waiting for leaderboard...")

    def show_leaderboard(self, lb):
        if hasattr(self, 'countdown'):
            self.countdown.cancel()
        self.layout.clear_widgets()
        self.layout.add_widget(Label(text='🏆 Leaderboard', font_size=28, color=(1, 0.8, 0, 1)))
        for name, sc in lb:
            self.layout.add_widget(Label(text=f"{name}: {sc}", font_size=22, color=(0.9, 0.9, 0.9, 1)))
        Clock.schedule_once(lambda dt: self.clear_layout('Next question incoming...'), 5)

    def send_answer(self, idx):
        self.countdown.cancel()
        for btn in self.question_buttons:
            btn.disabled = True
        self.manager.app.network.send_answer(self.manager.app.current_q, idx)

class QuizApp(App):
    def build(self):
        self.sm = ScreenManager()
        self.sm.app = self
        self.sm.add_widget(IntroScreen(name='intro'))
        self.quiz_screen = QuizScreen(name='quiz')
        self.sm.add_widget(self.quiz_screen)
        return self.sm

    def handle_server_message(self, msg):
        t = msg.get('type')
        if t == 'start':
            self.quiz_screen.clear_layout('Get ready!')
        elif t == 'question':
            self.current_q = msg['index']
            self.quiz_screen.display_question(msg)
        elif t == 'leaderboard':
            self.quiz_screen.show_leaderboard(msg['data'])
        elif t == 'end':
            self.quiz_screen.clear_layout('🎉 Quiz Finished!')

if __name__ == '__main__':
    QuizApp().run()
