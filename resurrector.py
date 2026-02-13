import subprocess
import sys
import time
import os

def run_valh():
    """
    The Resurrector: Monitor and restart the ValH main process.
    This script acts as the 'Watcher' to ensure zero downtime during upgrades.
    """
    print("🦾 ValH Resurrector: ACTIVATED")
    print("Watching C:\\Users\\joshi\\nevergiveup\\ValuableHelper\\main.py")

    while True:
        try:
            # Start the main process
            # We use sys.executable to ensure we use the same Python environment
            process = subprocess.Popen([sys.executable, "main.py"])
            
            print(f"✅ ValH Main Process Started (PID: {process.pid})")
            
            # Wait for the process to exit
            process.wait()
            
            # Check exit code
            # If we decide to use a specific exit code for 'Update/Restart', we can handle it here
            if process.returncode == 0:
                print("🔻 ValH shut down gracefully. Re-spawning in 2 seconds...")
            else:
                print(f"⚠️ ValH crashed or was terminated (Exit Code: {process.returncode}). Resurrecting...")
            
            time.sleep(2)
            
        except KeyboardInterrupt:
            print("\n🛑 Resurrector service terminated by User. Goodbye, Boss.")
            process.terminate()
            break
        except Exception as e:
            print(f"❌ Resurrector Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run_valh()
