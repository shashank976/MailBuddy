
from langgraph.graph import StateGraph, START, END

from workflows.states import EmailState

from agents.priority_agent import classify_email
from agents.action_agent import analyze_action
from agents.summary_agent import summarize_email
from agents.supervisor import supervisor_node


def priority_node(state: EmailState) -> dict:
    result = classify_email(
        sender=state["sender"],
        subject=state["subject"],
        body=state["body"],
        user_priorities=state["user_priorities"]
    )

    return {
        "priority_result": result
    }


def action_node(state: EmailState) -> dict:
    result = analyze_action(
        state["priority_result"]
    )

    return {
        "action_result": result
    }


def summary_node(state: EmailState) -> dict:
    result = summarize_email(
        state["priority_result"]
    )

    return {
        "summary_result": result
    }


builder = StateGraph(EmailState)

builder.add_node("priority_agent", priority_node)
builder.add_node("action_agent", action_node)
builder.add_node("summary_agent", summary_node)
builder.add_node("supervisor", supervisor_node)

builder.add_edge(START, "priority_agent")
builder.add_edge("priority_agent", "action_agent")
builder.add_edge("action_agent", "summary_agent")
builder.add_edge("summary_agent", "supervisor")
builder.add_edge("supervisor", END)

email_workflow = builder.compile()
