from langgraph.graph import END, START, StateGraph

from app.graph.nodes import enrich_facts, extract, fan_out_extract, ground_merge, judge, note_node, plan_and_fetch, score_node
from app.graph.state import ScanState


def build_graph():
    g = StateGraph(ScanState)
    g.add_node("plan_and_fetch", plan_and_fetch)
    g.add_node("extract", extract)
    g.add_node("ground_merge", ground_merge)
    g.add_node("enrich_facts", enrich_facts)
    g.add_node("judge", judge)
    g.add_node("score", score_node)
    g.add_node("note", note_node)

    g.add_edge(START, "plan_and_fetch")
    g.add_conditional_edges("plan_and_fetch", fan_out_extract, ["extract", "ground_merge"])
    g.add_edge("extract", "ground_merge")
    g.add_edge("ground_merge", "enrich_facts")
    g.add_edge("enrich_facts", "judge")
    g.add_edge("judge", "score")
    g.add_edge("score", "note")
    g.add_edge("note", END)
    return g.compile()


scan_graph = build_graph()
