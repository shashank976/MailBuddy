from agents.cleanup_agent import recommend_cleanup


def check_case(
    name: str,
    expected_action: str,
    **kwargs,
):
    result = recommend_cleanup(**kwargs)

    print(f"\n--- {name} ---")
    print(result.model_dump_json(indent=2))

    assert result.action == expected_action, (
        f"Expected {expected_action}, got {result.action}"
    )

    assert result.approval_required is True

    return result


# TEST 1: Basic promotional email
check_case(
    name="Clothing promotion",
    expected_action="archive",
    priority="low",
    category="promotion",
    action_status="none",
    requires_action=False,
    needs_review=False,
)

# TEST 2: Promotional mailing list
check_case(
    name="Newsletter with unsubscribe header",
    expected_action="unsubscribe",
    priority="low",
    category="promotion",
    action_status="none",
    requires_action=False,
    needs_review=False,
    has_list_unsubscribe=True,
)

# TEST 3: Important recruiting email
check_case(
    name="Recruiting email",
    expected_action="keep",
    priority="high",
    category="career",
    action_status="pending",
    requires_action=True,
    needs_review=False,
)

# TEST 4: Important academic update
check_case(
    name="Academic announcement",
    expected_action="keep",
    priority="high",
    category="academics",
    action_status="none",
    requires_action=False,
    needs_review=False,
)

# TEST 5: Low-priority but uncertain
check_case(
    name="Uncertain promotion",
    expected_action="keep",
    priority="low",
    category="promotion",
    action_status="uncertain",
    requires_action=False,
    needs_review=True,
    has_list_unsubscribe=True,
)

# TEST 6: Promotional subject but important content
check_case(
    name="High-priority promotional category",
    expected_action="keep",
    priority="high",
    category="promotion",
    action_status="none",
    requires_action=False,
    needs_review=False,
    has_list_unsubscribe=True,
)

# TEST 7: Low-priority account security
check_case(
    name="Security email",
    expected_action="keep",
    priority="low",
    category="security",
    action_status="none",
    requires_action=False,
    needs_review=False,
)

print("\nAll 7 Cleanup Agent tests passed!")
