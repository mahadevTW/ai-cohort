import httpx


if __name__ == "__main__":
    sorted_data = httpx.post("https://hemispherically-pietistical-laci.ngrok-free.dev/sort", json=[5, 2, 9, 1, 5, 6])
    print(sorted_data.json())