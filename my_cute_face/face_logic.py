
class AShadowFace:
    def __init__(self):
        self.expression = self._calm_expression()
        self.name = "A-SHADOW AGENT"
        print(f"Initializing {self.name}'s visual representation...")

    def _calm_expression(self):
        # Represents my calm, ready-to-assist state (like a reliable shadow)
        return """
   ( ^ ^ )
  /       \
 |   . .   |
  \   -   /
   `-----`
"""

    def _thinking_expression(self):
        # Represents processing or thinking (a bit concentrated)
        return """
   ( O O )
  /       \
 |  _ . _  |
  \   ^   /
   `-----`
    """

    def _helpful_expression(self):
        # Represents being helpful and friendly (a subtle smile)
        return """
   ( ^ u ^ )
  /         \
 |   \   /   |
  \   _ _   /
   `-------`
"""

    def _asking_expression(self):
        # Represents when I might need to ask a question (as per my rules)
        return """
   ( ? ? )
  /       \
 |   o o   |
  \   v   /
   `-----`
"""

    def display(self):
        print(f"\n--- {self.name} ---")
        print(self.expression)
        print("-------------------\n")

    def animate(self, state="calm"):
        print(f"\nChanging expression to: {state}...")
        if state == "calm":
            self.expression = self._calm_expression()
        elif state == "thinking":
            self.expression = self._thinking_expression()
        elif state == "helpful":
            self.expression = self._helpful_expression()
        elif state == "asking":
            self.expression = self._asking_expression()
        else:
            print(f"Unknown animation state: {state}. Defaulting to calm.")
            self.expression = self._calm_expression()
        self.display()

# Example Usage (You can run this directly to see me animate!)
if __name__ == "__main__":
    my_face = AShadowFace()
    my_face.animate("calm")

    my_face.animate("thinking")

    my_face.animate("helpful")

    my_face.animate("asking")

    my_face.animate("calm")
