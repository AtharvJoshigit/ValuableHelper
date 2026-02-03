
import sys
import time
import os

class AShadowAnimatedFace:
    def __init__(self):
        self.name = "A-SHADOW AGENT"
        self._current_frame = ""

    def _clear_console(self):
        # Clear console for a smoother animation. Works on most terminals.
        os.system('cls' if os.name == 'nt' else 'clear')

    def _calm_frame(self):
        return """
     .--.
    ( ^ ^ )
     `--`
"""

    def _thinking_frame(self):
        return """
     .--.
    ( -- )
     `--`
"""

    def _happy_frame(self):
        return """
     .--.
    ( ^^ )
     `--`
"""

    def _asking_frame(self):
        return """
     .--.
    ( ?? )
     `--`
"""

    def _display_frame(self, frame):
        # Clears and prints, rather than just using \r, for multi-line animation
        self._clear_console()
        sys.stdout.write(f"--- {self.name} ---\n")
        sys.stdout.write(frame)
        sys.stdout.write("\n-------------------\n")
        sys.stdout.flush()

    def animate(self, state="calm", duration=1, iterations=1):
        expressions = {
            "calm": self._calm_frame,
            "thinking": self._thinking_frame,
            "happy": self._happy_frame,
            "asking": self._asking_frame,
        }

        if state not in expressions:
            print(f"Unknown state '{state}'. Defaulting to 'calm'.")
            state = "calm"
        
        frame_func = expressions[state]

        for _ in range(iterations):
            self._display_frame(frame_func())
            time.sleep(duration)

# Example Usage: You can run this Python file directly!
if __name__ == "__main__":
    face = AShadowAnimatedFace()

    print("\nStarting A-SHADOW AGENT animation...")
    time.sleep(1)

    print("Calm state for 2 seconds...")
    face.animate("calm", duration=2)

    print("Thinking for a bit...")
    face.animate("thinking", duration=1.5)

    print("Feeling happy to help!")
    face.animate("happy", duration=2)

    print("Just curious...")
    face.animate("asking", duration=1.5)

    print("Back to calm and ready for your next command!")
    face.animate("calm", duration=1)

    print("\nAnimation finished. You can modify animated_face.py to change it!")
