from .agent import IntakeInterviewState, LattiaAgent


def test():
    agent = LattiaAgent()
    for _ in range(5):
        state = IntakeInterviewState()
        agent_reply = agent.generate_opening_question()
        history = [{"role": "assistant", "content": agent_reply}]
        print("Interview State:", state.model_dump())
        print(f"Agent: {agent_reply}")
        user_input = "I only sleep for 5 hours a day"
        agent_reply, state = agent.generate_reply(user_input, history, state)
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": agent_reply})


def run():
    agent = LattiaAgent()
    state = IntakeInterviewState()
    agent_reply = agent.generate_opening_question()
    history = [{"role": "assistant", "content": agent_reply}]
    for _ in range(3):
        print("Interview State:", state.model_dump())
        print(f"Agent: {agent_reply}")
        user_input = input("User: ")
        agent_reply, state = agent.generate_reply(user_input, history, state)
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": agent_reply})


def main():
    run()
    # test()


if __name__ == "__main__":
    main()
