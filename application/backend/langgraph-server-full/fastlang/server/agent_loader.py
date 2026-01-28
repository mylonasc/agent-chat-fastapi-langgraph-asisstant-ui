

def _make_demo_agent(*args, **kwargs):
    from pathlib import Path
    curr_path = Path(__file__)
    p = curr_path.parents[2].as_posix()
    import sys
    sys.path.append(p)
    from examples.demo_agent.get_graph import make_agent_with_weather_tool 
    return make_agent_with_weather_tool(*args, **kwargs)