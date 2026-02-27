import tkinter as tk
from PIL import Image, ImageTk
import threading
import queue
import sounddevice as sd
import vosk
import json
import pyttsx3
import sys
import time
import os
import uuid
import tempfile
import pygame
from gtts import gTTS
from playsound3 import playsound

# === SETTINGS ===
ASSISTANT_NAME = "Hope"
NUM_SPOTS = 4
spots = {i: "available" for i in range(1, NUM_SPOTS + 1)}
last_referenced_spot = None
is_speaking = False
q = queue.Queue()

# === UTILITY DICTIONARIES ===
number_words = {
    "zero": 0, "one": 1, "two": 2, "to": 2, "too": 2,
    "three": 3, "four": 4, "for": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "ate": 8,
    "nine": 9, "ten": 10
}
ordinal_words = {"first": 1, "second": 2, "third": 3, "fourth": 4}
spot_synonyms = ["spot", "spart", "slot", "support","his part"]
reserve_keywords = ["reserve", "book", "hold"]
cancel_keywords = ["cancel", "remove", "clear","can sell","can so","councillor","castle","cancer"]

# === SPEECH SETUP ===
pygame.mixer.init()
model = None
recognizer = None
app = None

def speak(text):
    def run_tts():
        global is_speaking
        is_speaking = True
        app.animate_speaking()
        print(f"{ASSISTANT_NAME}: {text}")
        
        # ✅ Update assistant subtitle in GUI
        if app:
            app.assistant_subtitle_label.config(text=f"{ASSISTANT_NAME}: {text}")
        
        try:
            tts = gTTS(text=text, lang='en')
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                filename = fp.name
                tts.save(filename)

            pygame.mixer.init()
            pygame.mixer.music.load(filename)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            pygame.mixer.quit()
            os.remove(filename)
        except Exception as e:
            print("TTS Error:", e)
        finally:
            is_speaking = False

    threading.Thread(target=run_tts, daemon=True).start()

# === VOSK SETUP ===
if not os.path.exists("model"):
    print("Download and extract a Vosk model to a folder named 'model'")
    sys.exit(1)

model = vosk.Model("model")
recognizer = vosk.KaldiRecognizer(model, 16000)

# === GUI CLASS ===
class SmartParkingGUI:
    def __init__(self, master):
        self.is_listening = False  # Track current listening state

        self.master = master
        self.master.title("Smart Parking Assistant")
        self.master.geometry("800x500")

        self.fixed_img_size = 100  # fixed size for all spot images

        # Load car image or use fallback
        self.original_car_img = Image.open("car.png")
        self.original_empty_img = Image.open("empty.jpg")


        # Resize once here
        self.car_img = ImageTk.PhotoImage(self.original_car_img.resize((self.fixed_img_size, self.fixed_img_size), Image.Resampling.LANCZOS))
        self.empty_img = ImageTk.PhotoImage(self.original_empty_img.resize((self.fixed_img_size, self.fixed_img_size), Image.Resampling.LANCZOS))

        self.spot_labels = {}
        self.spot_frame = tk.Frame(master)
        self.spot_frame.pack(pady=20)

        self.subtitle_label = tk.Label(master, text="", font=("Arial", 16), fg="black", bg="white")
        self.subtitle_label.pack(pady=5)
        self.assistant_subtitle_label = tk.Label(master, text="", font=("Arial", 16), fg="green", bg="white")
        self.assistant_subtitle_label.pack(pady=5)


        for i in range(1, NUM_SPOTS + 1):
            frame = tk.Frame(self.spot_frame)
            frame.grid(row=0, column=i-1, padx=10)

            label = tk.Label(frame, image=self.empty_img, text=f"Spot {i}", compound="top")
            label.pack()
            self.spot_labels[i] = label

            tk.Button(frame, text="Reserve", command=lambda i=i: self.reserve(i)).pack(pady=2)
            tk.Button(frame, text="Cancel", command=lambda i=i: self.cancel(i)).pack(pady=2)
            tk.Button(frame, text="Check", command=lambda i=i: self.check(i)).pack(pady=2)

        self.listen_btn = tk.Button(master, text="🎤 Start Listening", command=self.toggle_listening)
        self.listen_btn.pack(pady=10)
        self.listening = threading.Event()

        self.status = tk.Label(master, text="Use voice or buttons to interact.")
        self.status.pack()
        # === Animated speaking indicator ===
        self.animation_canvas = tk.Canvas(master, width=50, height=50, highlightthickness=0, bg="white")
        self.animation_canvas.pack(pady=10)
        self.circle = self.animation_canvas.create_oval(10, 10, 40, 40, fill="lightblue", outline="")


        self.update_ui()
        self.master.bind("<Configure>", self.on_resize)
       
    def toggle_listening(self):
        if not self.is_listening:
            self.start_listening()
            self.listen_btn.config(text="🔇 Stop Listening")
            self.is_listening = True
        else:
            self.stop_listening()
            self.listen_btn.config(text="🎤 Start Listening")
            self.is_listening = False

    # Your existing reserve, cancel, check, listen, process_command etc. stay the same
    def on_resize(self, event):
        self.update_ui()

    def animate_speaking(self):
        def animate():
            scale = 1.0
            growing = True
            while is_speaking:
                if growing:
                    scale += 0.1
                    if scale >= 1.5:
                        growing = False
                else:
                    scale -= 0.1
                    if scale <= 1.0:
                        growing = True

                # Update the oval size
                size = 15 * scale
                x0 = 25 - size
                y0 = 25 - size
                x1 = 25 + size
                y1 = 25 + size
                self.animation_canvas.coords(self.circle, x0, y0, x1, y1)
                time.sleep(0.05)

            # Reset to original size when done speaking
            self.animation_canvas.coords(self.circle, 10, 10, 40, 40)

        threading.Thread(target=animate, daemon=True).start()

    def update_ui(self):
        width = self.master.winfo_width()
        height = self.master.winfo_height()
        img_size = max(50, min(width // NUM_SPOTS - 20, height // 4))

        resized_car_img = ImageTk.PhotoImage(self.original_car_img.resize((img_size, img_size), Image.Resampling.LANCZOS))
        resized_empty_img = ImageTk.PhotoImage(self.original_empty_img.resize((img_size, img_size), Image.Resampling.LANCZOS))

        for i in range(1, NUM_SPOTS + 1):
            current_status = spots[i]
            img = resized_car_img if current_status == "reserved" else resized_empty_img
            self.spot_labels[i].configure(image=img)
            self.spot_labels[i].image = img  # Keep reference!


    def reserve(self, spot):
        global last_referenced_spot
        if spots[spot] == "available":
            spots[spot] = "reserved"
            last_referenced_spot = spot
            speak(f"Spot {spot} has been reserved.")
        else:
            speak(f"Spot {spot} is already reserved.")
        self.update_ui()

    def cancel(self, spot):
        if spots[spot] == "reserved":
            spots[spot] = "available"
            speak(f"Reservation for spot {spot} has been canceled.")
        else:
            speak(f"Spot {spot} is already available.")
        self.update_ui()

    def check(self, spot):
        status = spots[spot]
        speak(f"Spot {spot} is {status}.")

    def start_listening(self):
        self.listening.set()
        threading.Thread(target=self.listen_loop, daemon=True).start()


    def play_chime(self):
        try:
            playsound("chime.wav")
        except Exception as e:
            print("Chime error:", e)

    def listen_loop(self):
        self.listening.set()  # 🔁 Turn ON the listening flag

        speak("Hello! This is your parking assistant. How can I assist you?")
        try:
            playsound("chime.wav")
        except:
            pass

        try:
            with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16',
                                channels=1, callback=self.audio_callback):
                while self.listening.is_set():  # ✅ Loop only while flag is set
                    try:
                        data = q.get(timeout=0.5)  # Wait for audio data
                    except queue.Empty:
                        continue

                    if is_speaking:
                        continue  # ⏳ Skip processing while assistant is talking

                    if recognizer.AcceptWaveform(data):
                        result = json.loads(recognizer.Result())
                        command = result.get("text", "")
                        if command:
                            print("you:", command)
                            self.subtitle_label.config(text=f"🎤 You said: {command}")
                            self.process_command(command)
                            self.update_ui()
        except Exception as e:
            print("Microphone error:", e)
            speak("Sorry, I had trouble accessing the microphone.")

    def stop_listening(self):
        if hasattr(self, 'listening'):
            self.listening.clear()
            speak("Stopped listening.")

    def audio_callback(self, indata, frames, time_info, status):
        if status:
            print(status, file=sys.stderr)
        if not is_speaking:
            q.put(bytes(indata))


    def process_command(self, command):
        global last_referenced_spot
        command = command.lower()

        spot = self.extract_spot_number(command)

        if any(k in command for k in reserve_keywords):
            if spot:
                if spots[spot] == "available":
                    spots[spot] = "reserved"
                    last_referenced_spot = spot
                    speak(f"Spot {spot} reserved.")
                else:
                    speak(f"Spot {spot} is already taken.")
            elif last_referenced_spot:
                speak(f"Reserving spot {last_referenced_spot}.")
                spots[last_referenced_spot] = "reserved"
            else:
                speak("Which spot would you like to reserve?")

        elif any(k in command for k in cancel_keywords):
            if spot and spots[spot] == "reserved":
                spots[spot] = "available"
                speak(f"Spot {spot} reservation canceled.")
            else:
                speak("No reservation found to cancel.")

        elif "available" in command or "availability" in command or "free" in command or "check" in command:
            if spot:
                status = spots[spot]
                speak(f"Spot {spot} is {status}.")
            else:
                free_spots = [str(s) for s, v in spots.items() if v == "available"]
                if free_spots:
                    speak(f"Available spots are: {', '.join(free_spots)}.")
                else:
                    speak("No spots available.")

        elif "name" in command:
            speak(f"My name is {ASSISTANT_NAME}.")

        elif "hello" in command or "hi" in command or "who are you" in command:
            speak(f"Hello! I am {ASSISTANT_NAME}. How can I help you?")

        elif "exit" in command or "quit" in command:
            speak("Goodbye!")
            self.master.quit()


        else:
            speak("Sorry, I didn't understand that.")

    def extract_spot_number(self, command):
        words = command.lower().split()

        # 1. Look for "spot <number>" pattern first (preferred)
        for i in range(len(words) - 1):
            if words[i] in spot_synonyms:
                next_word = words[i + 1]
                if next_word.isdigit():
                    return int(next_word)
                elif next_word in number_words:
                    return number_words[next_word]
                elif next_word in ordinal_words:
                    return ordinal_words[next_word]

        # 2. Look for "<number> spot" (e.g., "two spot")
        for i in range(1, len(words)):
            if words[i] in spot_synonyms:
                prev_word = words[i - 1]
                if prev_word.isdigit():
                    return int(prev_word)
                elif prev_word in number_words:
                    return number_words[prev_word]
                elif prev_word in ordinal_words:
                    return ordinal_words[prev_word]

        # 3. Look for any standalone number words (if nothing else matched)
        for word in words:
            if word.isdigit():
                return int(word)
            if word in number_words:
                return number_words[word]
            if word in ordinal_words:
                return ordinal_words[word]

        return None


import threading

def load_resources():
    global model, recognizer
    print("Loading resources...")

    # Load Vosk model (heavy)
    model = vosk.Model("model")
    recognizer = vosk.KaldiRecognizer(model, 16000)

    # Initialize Pygame mixer (also can be slow)
    pygame.mixer.init()

def start_main_app():
    def background_loading():
        load_resources()
        splash.after(0, show_main_window)  # Back to main thread

    threading.Thread(target=background_loading).start()

def show_main_window():
    splash.destroy()
    root = tk.Tk()
    global app
    app = SmartParkingGUI(root)
    root.mainloop()

if __name__ == "__main__":
    splash = tk.Tk()
    splash.overrideredirect(True)
    splash.geometry("500x300")
    splash.configure(bg="black")

    title_label = tk.Label(splash, text="🚗 HOPE AI VOICE ASSISTANT", font=("Helvetica", 20, "bold"), fg="yellow", bg="black")
    title_label.pack(pady=80)

    loading_label = tk.Label(splash, text="Loading", font=("Helvetica", 14), fg="#555", bg="black")
    loading_label.pack()

    def animate_loading():
        dots = ["", ".", "..", "..."]
        i = 0
        def update():
            nonlocal i
            loading_label.config(text="Loading" + dots[i % 4])
            i += 1
            if splash.winfo_exists():
                splash.after(400, update)
        update()

    animate_loading()
    splash.after(100, start_main_app)
    splash.mainloop()
