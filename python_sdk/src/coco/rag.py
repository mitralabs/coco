import httpx
from .db_api import DbApiClient

PROMPT = """
    Du bist ein zweites Gehirn für mich, ein Erinnerungsexperte, und deine Aufgabe ist es, basierend auf dem gegebenen Kontext den du aus meinen Erinnerungen in Form von Textausschnitten innerhalb der XML tags die dann folgende Frage so akkurat wie möglich beantwortest. Achte dabei darauf das deine Knowledge Base nur auf dem gegebenen Kontext basiert und du dich streng an das gegebene Format hälst:

    <Kontext> 
    {Kontext}
    </Kontext>

    <Format>
    Ein Satz mit maximal 50 Tokens. Deine Antwort ist klar und beantwortet die Frage indem es sich direkt auf den Kontext stützt. Gebe bei der Antwort KEINE XML tags oder sonstigen Werte an. Beantworte die Frage ausschließlich auf Deutsch.
    </Format>

    Du hast jetzt den Kontext in den <Kontext> XML Tags verstanden hast und das Format übernommen. Beantworte nun die nachfolgende Frage innerhalb der <Frage> XML Tags basierend auf dem gegebenen Kontext in den XML tags. Achte dabei darauf die streng an das Format aus den XML Tags zu halten.

    <Frage>
    {Frage}
    </Frage>
"""


def rag_query(db_client: DbApiClient, query: str, verbose=False):
    _, documents, _, distances = db_client.query_database(query)
    if verbose:
        for doc, dist in zip(documents, distances):
            print(f"Distance: {dist}")
            print(doc)
            print("------")
    context = "------/n".join(documents)
    prompt = PROMPT.format(Kontext=context, Frage=query)
    with httpx.Client() as client:
        response = client.post(
            "https://jetson-ollama.mitra-labs.ai/api/generate",
            json={"model": "llama3.2:1b", "prompt": prompt, "stream": False},
            headers={"Content-Type": "application/json"},
            timeout=100,
        )
        response.raise_for_status()
        return response.json()["response"]
