from database.retrieval import bm25_rank, reciprocal_rank_fusion


def test_bm25_prefers_exact_policy_identifier():
    documents = {
        "password": "Policy: Password and Account Security\nDocument ID: PWD-100",
        "onboarding": "Policy: Employee Onboarding\nDocument ID: ONB-101",
    }

    assert bm25_rank("What does PWD-100 require?", documents, limit=2)[0] == "password"


def test_reciprocal_rank_fusion_rewards_agreement_between_searches():
    results = reciprocal_rank_fusion(
        ["semantic-only", "shared", "other"],
        ["keyword-only", "shared", "other"],
        limit=3,
    )

    assert results[0] == "shared"
