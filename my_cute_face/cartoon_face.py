import tkinter as tk
import time

class AShadowCartoonFace:
    def __init__(self, master):
        self.master = master
        master.title("A-SHADOW AGENT")
        master.geometry("250x250") # Set a fixed window size

        self.canvas = tk.Canvas(master, width=250, height=250, bg="#E0E0E0", highlightthickness=0)
        self.canvas.pack()

        # Face outline (soft rounded rectangle)
        self.face_bg = self.canvas.create_oval(50, 50, 200, 200, fill="#303030", outline="#505050")

        # Eye whites
        self.left_eye_white = self.canvas.create_oval(80, 95, 110, 125, fill="white", outline="black")
        self.right_eye_white = self.canvas.create_oval(140, 95, 170, 125, fill="white", outline="black")

        # Pupils (will change for expression)
        self.left_pupil = self.canvas.create_oval(90, 105, 100, 115, fill="black", outline="black")
        self.right_pupil = self.canvas.create_oval(150, 105, 160, 115, fill="black", outline="black")

        # Mouth (will change for expression)
        self.mouth = self.canvas.create_line(100, 145, 150, 145, fill="black", width=3)

        self._current_expression = "calm"
        self._expressions = {
            "calm": self._draw_calm,
            "thinking": self._draw_thinking,
            "happy": self._draw_happy,
            "asking": self._draw_asking
        }
        self.set_expression("calm") # Start with calm

    def _draw_calm(self):
        # Pupils centered
        self.canvas.coords(self.left_pupil, 90, 105, 100, 115)
        self.canvas.coords(self.right_pupil, 150, 105, 160, 115)
        # Flat mouth
        self.canvas.coords(self.mouth, 100, 145, 150, 145)
        self.canvas.itemconfig(self.mouth, smooth=0)

    def _draw_thinking(self):
        # Pupils slightly down and close
        self.canvas.coords(self.left_pupil, 87, 108, 97, 118)
        self.canvas.coords(self.right_pupil, 147, 108, 157, 118)
        # Slight furrowed brow (represented by a flatter, slightly lower mouth)
        self.canvas.coords(self.mouth, 100, 150, 150, 150)
        self.canvas.itemconfig(self.mouth, smooth=0)

    def _draw_happy(self):
        # Pupils slightly up
        self.canvas.coords(self.left_pupil, 90, 100, 100, 110)
        self.canvas.coords(self.right_pupil, 150, 100, 160, 110)
        # Curved happy mouth
        self.canvas.coords(self.mouth, 100, 145, 125, 155, 150, 145)
        self.canvas.itemconfig(self.mouth, smooth=1) # Smooth curve

    def _draw_asking(self):
        # Pupils slightly up and to the side (a questioning tilt)
        self.canvas.coords(self.left_pupil, 85, 103, 95, 113)
        self.canvas.coords(self.right_pupil, 145, 107, 155, 117)
        # Slightly raised eyebrow (implied by eye position) and a small, slightly open mouth
        self.canvas.coords(self.mouth, 115, 145, 135, 145)
        self.canvas.itemconfig(self.mouth, smooth=0)


    def set_expression(self, expression_name):
        if expression_name in self._expressions:
            self._current_expression = expression_name
            self._expressions[expression_name]()
        else:
            print(f"Unknown expression: {expression_name}. Defaulting to calm.")
            self._current_expression = "calm"
            self._draw_calm()
        self.master.update_idletasks() # Refresh the canvas

    def animate_sequence(self, sequence, delay=1.5):
        for expression in sequence:
            print(f"A-SHADOW AGENT: {expression.capitalize()}...")
            self.set_expression(expression)
            time.sleep(delay)


if __name__ == "__main__":
    root = tk.Tk()
    face = AShadowCartoonFace(root)

    animation_sequence = ["calm", "thinking", "happy", "asking", "calm"]
    face.animate_sequence(animation_sequence, delay=1.5)

    root.mainloop() # Keeps the window open and responsive
