
from workflows.email_workflow import email_workflow


test_email = {
    "email_id": "test-001",
    "thread_id": "thread-001",
    "sender": "recruiter@example.com",
    "subject": "Interview Invitation",
    "body": (
        "We would like to interview you tomorrow. "
        "Please confirm your availability."
    ),
    "user_priorities": (
        "Prioritize software engineering internships "
        "and academic deadlines."
    ),
}


result = email_workflow.invoke(test_email)

print("\n--- PRIORITY RESULT ---")
print(
    result["priority_result"].model_dump_json(indent=2)
)

print("\n--- SUPERVISOR RESULT ---")
print(result["dashboard_group"])

assert result["dashboard_group"] == "needs_attention"

print("\nWorkflow test passed!")

print("\n--- ACTION RESULT ---")
print(result["action_result"].model_dump_json(indent=2))

assert result["action_result"].requires_action is True
assert result["action_result"].action_type == "reply"
assert result["dashboard_group"] == "needs_attention"