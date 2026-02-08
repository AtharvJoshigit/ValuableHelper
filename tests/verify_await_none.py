import asyncio

class Bus:
    def publish(self):
        return None

async def main():
    b = Bus()
    try:
        await b.publish()
    except TypeError as e:
        print(f"Caught expected error: {e}")
    except Exception as e:
        print(f"Caught unexpected error: {type(e)} {e}")

if __name__ == "__main__":
    asyncio.run(main())