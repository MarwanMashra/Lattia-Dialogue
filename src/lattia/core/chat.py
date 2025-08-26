import os

from .agent import IntakeInterviewState, LattiaAgent
from .vector_db.embeddings import OpenAIEmbeddings
from .vector_db.qdrant_store import QdrantStore
from .vector_db.retriever import SemanticRetriever


def run():
    retriever = SemanticRetriever(
        provider=OpenAIEmbeddings(),
        collection=os.getenv("QDRANT_COLLECTION", "health_questions"),
        store=QdrantStore(
            url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            api_key=os.getenv("QDRANT_API_KEY"),
        ),
    )

    agent = LattiaAgent(retriever)
    agent_reply = agent.generate_opening_question(user_name="Marwan")
    state = IntakeInterviewState()
    history = [{"role": "assistant", "content": agent_reply}]
    while True:
        print(f"Agent: {agent_reply}")
        user_input = input("User: ")
        agent_reply, state = agent.generate_reply(
            user_input, history, state, versbose=True
        )
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": agent_reply})


def main():
    run()


if __name__ == "__main__":
    main()
