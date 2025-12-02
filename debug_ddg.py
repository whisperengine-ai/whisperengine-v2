from ddgs import DDGS

def test():
    print("Testing with ddgs...")
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text("python programming", max_results=3))
            print(f"Results: {results}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()
