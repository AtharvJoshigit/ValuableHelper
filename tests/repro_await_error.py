
import asyncio

class Bus:
    def publish(self):
        print("Publishing...")
        return None

async def main():
    b = Bus()
    try:
        print("Attempting to await a sync function returning None...")
        await b.publish()
    except TypeError as e:
        print(f"✅ CAUGHT EXPECTED ERROR: {e}")
    except Exception as e:
        print(f"❌ CAUGHT UNEXPECTED ERROR: {type(e)} {e}")

if __name__ == "__main__ ":
    asyncio.run(main())
