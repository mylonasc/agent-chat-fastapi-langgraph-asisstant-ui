from langchain_core.tools import tool


@tool
def get_weather(city: str):
    """Use this to look up the weather for a specific city."""
    if "london" in city.lower():
        return "It's 15°C and cloudy in London."
    return f"The weather in {city} is sunny and 25°C."
