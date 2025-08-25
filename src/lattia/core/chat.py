import os

from .agent import IntakeInterviewState, LattiaAgent
from .vector_db.embeddings import OpenAIEmbeddings
from .vector_db.qdrant_store import QdrantStore
from .vector_db.retriever import SemanticRetriever


def test():
    """for testing purposes only"""


d = {
    "fields": {
        "sleep_hours": {
            "spec": {
                "key": "sleep_hours",
                "name": "Typical nightly sleep duration",
                "description": "The average number of hours of sleep the user gets per night.",
                "domain": "sleep",
                "value_type": "bucketed_choice",
                "options": {
                    "lt4h": "<4h",
                    "4to6h": "4\u20136h",
                    "6to8h": "6\u20138h",
                    "gt8h": ">8h",
                },
                "additional_value_format_specification": None,
            },
            "rationale": "User provided this information unprompted when asked about sleep habits.",
            "value": "4to6h",
        },
        "sleep_quality": {
            "spec": {
                "key": "sleep_quality",
                "name": "Sleep quality rating",
                "description": "The user's overall rating of their sleep quality over the past month.",
                "domain": "sleep",
                "value_type": "scale_1_10",
                "options": None,
                "additional_value_format_specification": None,
            },
            "rationale": "Given the user reports short sleep duration, it's important to understand their perceived sleep quality to assess functional impact and potential underlying issues.",
            "value": "6",
        },
        "daytime_sleepiness": {
            "spec": {
                "key": "daytime_sleepiness",
                "name": "Daytime sleepiness frequency",
                "description": "How often the user feels excessively sleepy or struggles to stay awake during the day.",
                "domain": "sleep",
                "value_type": "bucketed_choice",
                "options": {
                    "never": "Never",
                    "rarely": "Rarely",
                    "sometimes": "Sometimes",
                    "often": "Often",
                    "always": "Always",
                },
                "additional_value_format_specification": None,
            },
            "rationale": "Short sleep duration with moderate quality makes it important to assess for functional impairment or excessive daytime sleepiness.",
            "value": "prefer_not_to_say",
        },
        "sleep_routine_consistency": {
            "spec": {
                "key": "sleep_routine_consistency",
                "name": "Sleep routine consistency",
                "description": "How consistent the user's bedtime and wake time are throughout the week.",
                "domain": "sleep",
                "value_type": "single_choice",
                "options": {
                    "very_consistent": "Very consistent (within 30 minutes)",
                    "somewhat_consistent": "Somewhat consistent (within 1 hour)",
                    "variable": "Variable (more than 1 hour difference)",
                },
                "additional_value_format_specification": None,
            },
            "rationale": "Understanding routine consistency helps identify behavioral contributors to sleep duration and quality.",
            "value": "not_sure",
        },
        "caffeine_evening": {
            "spec": {
                "key": "caffeine_evening",
                "name": "Evening caffeine consumption",
                "description": "Whether the user consumes caffeine in the late afternoon or evening (after 3pm).",
                "domain": "sleep",
                "value_type": "yes_no",
                "options": None,
                "additional_value_format_specification": None,
            },
            "rationale": "Caffeine use in the evening is a common behavioral factor that can affect sleep onset and quality, especially when sleep is short and quality is moderate.",
            "value": "yes",
        },
        "basic_demographics_age": {
            "spec": {
                "key": "basic_demographics_age",
                "name": "Age",
                "description": "The user's current age in years.",
                "domain": "basic_info",
                "value_type": "bucketed_choice",
                "options": {
                    "under18": "Under 18",
                    "18to24": "18\u201324",
                    "25to34": "25\u201334",
                    "35to44": "35\u201344",
                    "45to54": "45\u201354",
                    "55to64": "55\u201364",
                    "65plus": "65 or older",
                },
                "additional_value_format_specification": None,
            },
            "rationale": "Shifting away from sleep, collecting age is a standard and non-sensitive starting point for building the user's overall health profile.",
            "value": "25to34",
        },
        "basic_demographics_sex": {
            "spec": {
                "key": "basic_demographics_sex",
                "name": "Sex assigned at birth",
                "description": "The user's sex assigned at birth (male, female, or other).",
                "domain": "basic_info",
                "value_type": "single_choice",
                "options": {
                    "male": "Male",
                    "female": "Female",
                    "other": "Other / prefer to self-describe",
                    "prefer_not_to_say": "Prefer not to say",
                },
                "additional_value_format_specification": None,
            },
            "rationale": "Collecting sex assigned at birth is a standard and necessary demographic variable for risk stratification and tailoring future intake domains.",
            "value": "prefer_not_to_say",
        },
        "physical_activity_frequency": {
            "spec": {
                "key": "physical_activity_frequency",
                "name": "Physical activity frequency",
                "description": "How often the user engages in moderate or vigorous physical activity per week.",
                "domain": "physical_activity",
                "value_type": "bucketed_choice",
                "options": {
                    "never": "Never",
                    "1to2x": "1\u20132 times/week",
                    "3to5x": "3\u20135 times/week",
                    "6plus": "6 or more times/week",
                },
                "additional_value_format_specification": None,
            },
            "rationale": "Transitioning to physical activity frequency is a standard next step after demographics, and is less sensitive than recent topics.",
            "value": "6plus",
        },
        "physical_activity_duration": {
            "spec": {
                "key": "physical_activity_duration",
                "name": "Average duration of physical activity sessions",
                "description": "The average length of time the user spends per physical activity session (including swimming and gym).",
                "domain": "physical_activity",
                "value_type": "bucketed_choice",
                "options": {
                    "lt30m": "Less than 30 minutes",
                    "30to60m": "30\u201360 minutes",
                    "60to90m": "60\u201390 minutes",
                    "gt90m": "More than 90 minutes",
                },
                "additional_value_format_specification": None,
            },
            "rationale": "The user\u2019s activity frequency is high, so session duration will help clarify their total weekly activity load.",
            "value": "60to90m",
        },
        "physical_activity_objectives": {
            "spec": {
                "key": "physical_activity_objectives",
                "name": "Primary objectives of physical activity",
                "description": "The user's main goals or motivations for engaging in physical activity.",
                "domain": "physical_activity",
                "value_type": "multi_choice",
                "options": {
                    "improveHealth": "Improve health",
                    "reduceStress": "Reduce stress",
                    "buildStrength": "Build strength/muscle",
                    "weightManagement": "Weight management",
                    "social": "Social connection",
                    "enjoyment": "Enjoyment/fun",
                    "performance": "Athletic performance",
                },
                "additional_value_format_specification": None,
            },
            "rationale": "Understanding the user\u2019s reasons for being physically active provides insight into their health priorities and sustainability of current behaviors.",
            "value": "improveHealth,buildStrength",
        },
        "nutrition_diet_pattern": {
            "spec": {
                "key": "nutrition_diet_pattern",
                "name": "Usual dietary pattern",
                "description": "The overall dietary pattern that best describes the user's typical eating habits.",
                "domain": "nutrition",
                "value_type": "single_choice",
                "options": {
                    "standard": "Standard (mixed diet)",
                    "mediterranean": "Mediterranean",
                    "vegetarian": "Vegetarian",
                    "vegan": "Vegan",
                    "pescatarian": "Pescatarian",
                    "lowcarb": "Low-carbohydrate",
                    "highprotein": "High-protein",
                    "other": "Other / prefer to self-describe",
                },
                "additional_value_format_specification": None,
            },
            "rationale": "Physical activity goals include muscle building and health improvement, making dietary pattern particularly relevant to assess now.",
            "value": "to_collect",
        },
    },
    "is_done": False,
}


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
    # test()


if __name__ == "__main__":
    main()
