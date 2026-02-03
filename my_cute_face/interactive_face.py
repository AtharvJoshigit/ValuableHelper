import tkinter as tk
import random
import time

class AShadowInteractiveFace:
    def __init__(self, master):
        self.master = master
        master.title("A-SHADOW AGENT - Interactive Face")
        master.geometry("300x200") # A nice size for eyes and mouth
        master.resizable(False, False) # Keep it fixed for a controlled look
        master.overrideredirect(True) # Remove window decorations for a cleaner, floating face

        self.canvas = tk.Canvas(master, width=300, height=200, bg="#F0F8FF", highlightthickness=0)
        self.canvas.pack()

        # Eyes (main shape is white oval)
        self.left_eye = self.canvas.create_oval(70, 60, 130, 90, fill="white", outline="black", width=2)
        self.right_eye = self.canvas.create_oval(170, 60, 230, 90, fill="white", outline="black", width=2)
        
        # Pupils (small black ovals)
        self.left_pupil = self.canvas.create_oval(90, 70, 110, 80, fill="black", outline="black")
        self.right_pupil = self.canvas.create_oval(190, 70, 210, 80, fill="black", outline="black")

        # Mouth (neutral arc initially)
        self.mouth = self.canvas.create_arc(100, 120, 200, 140, start=180, extent=180, style=tk.ARC, outline="black", width=3)

        self.is_smiling = False
        self.background_colors = ["#F0F8FF", "#FFE0E6", "#E0FFFF", "#E6E0FF", "#F8F0FF"] # Light blue, pink, cyan, lavender, light purple
        self.current_bg_index = 0

        self._start_animations()

    def _start_animations(self):
        self._schedule_blink()
        self._schedule_smile()
        self._schedule_bg_change()

    # --- Blinking Logic ---
    def _schedule_blink(self):
        delay = random.randint(2000, 5000) # Blink every 2-5 seconds
        self.master.after(delay, self._initiate_blink_sequence)

    def _initiate_blink_sequence(self):
        # Close eyes (shrink pupils vertically)
        self.canvas.coords(self.left_pupil, 90, 74, 110, 76)
        self.canvas.coords(self.right_pupil, 190, 74, 210, 76)
        
        self.master.after(100, self._complete_blink) # Hold blink for 100ms, then open
        self._schedule_blink() # Reschedule for next blink

    def _complete_blink(self):
        # Open eyes (restore pupils)
        self.canvas.coords(self.left_pupil, 90, 70, 110, 80)
        self.canvas.coords(self.right_pupil, 190, 70, 210, 80)

    # --- Smiling Logic ---
    def _schedule_smile(self):
        delay = random.randint(3000, 7000) # Smile every 3-7 seconds
        self.master.after(delay, self._initiate_smile_sequence)

    def _initiate_smile_sequence(self):
        if not self.is_smiling:
            self._set_happy_mouth()
            self.master.after(random.randint(1000, 2000), self._set_neutral_mouth) # Hold smile then revert
        
        self._schedule_smile() # Reschedule for next smile initiation

    def _set_neutral_mouth(self):
        self.canvas.coords(self.mouth, 100, 130, 200, 150) # Flatter arc
        self.canvas.itemconfig(self.mouth, start=180, extent=180) 
        self.is_smiling = False

    def _set_happy_mouth(self):
        self.canvas.coords(self.mouth, 100, 120, 200, 160) # Wider, deeper arc
        self.canvas.itemconfig(self.mouth, start=200, extent=140) 
        self.is_smiling = True

    # --- Background Change Logic ---
    def _schedule_bg_change(self):
        delay = random.randint(5000, 10000) # Change background every 5-10 seconds
        self.master.after(delay, self._change_background)

    def _change_background(self):
        self.current_bg_index = (self.current_bg_index + 1) % len(self.background_colors)
        new_color = self.background_colors[self.current_bg_index]
        self.canvas.config(bg=new_color)
        self._schedule_bg_change()


if __name__ == "__main__":
    root = tk.Tk()
    face = AShadowInteractiveFace(root)
    root.mainloop() # Keeps the window open and responsive
