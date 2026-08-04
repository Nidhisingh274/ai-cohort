import requests

def fetch_url(url):
    response = requests.get(url)
    return response.json()

print(fetch_url("https://api.github.com"))