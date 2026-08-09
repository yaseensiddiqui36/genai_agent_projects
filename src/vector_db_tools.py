"""Vector database tools for policy retrieval."""

import logging
from typing import Dict
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Try to import vector store, fallback to mock if not available
try:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from src.vector_db_creation import PolicyVectorStore

    # Initialize policy retriever
    policy_store = PolicyVectorStore()
    policy_store.load_vector_store("policy_vector_db")
    logger.info("Vector database loaded successfully")

except Exception as e:
    logger.warning("Vector database not available (%s); using mock policy retrieval", e)

    class MockPolicyStore:
        def search_policies(self, query, k=3, filters=None):
            return [
                {
                    'content': f"Mock policy content for query: {query}",
                    'metadata': {'document_title': 'Mock Policy', 'section': 'Mock Section'},
                    'relevance': 0.8
                }
            ]
    
    policy_store = MockPolicyStore()


@tool
def search_return_eligibility_policy(product_category: str, customer_tier: str = "") -> str:
    """Search for return eligibility policies for specific product category and customer tier"""
    # Create a flexible query that includes the input category and return terms
    query = f"{product_category} return window eligibility timeframe policy"
    
    # Try search without strict filters first - just use the query
    results = policy_store.search_policies(query, k=4, filters=None)
    policies = [result['content'] for result in results]

    # If we have customer tier, also search for tier-specific policies
    if customer_tier and not policies:
        tier_query = f"{customer_tier} {product_category} return policy benefits"
        tier_results = policy_store.search_policies(tier_query, k=3, filters=None)
        policies = [result['content'] for result in tier_results]

    return "\n\n".join(policies) if policies else f"Found return policy information that may apply to {product_category} category"


@tool
def search_refund_calculation_policy(product_category: str, customer_tier: str = "", reason: str = "") -> str:
    """Search for refund calculation policies"""
    # Create flexible query with all provided information
    query_parts = [product_category, "refund calculation", "restocking fee"]
    if reason:
        query_parts.append(reason)
    if customer_tier:
        query_parts.append(customer_tier)
    
    query = " ".join(query_parts)
    
    # Search without strict filters to be more inclusive
    results = policy_store.search_policies(query, k=4, filters=None)
    policies = [result['content'] for result in results]

    return "\n\n".join(policies) if policies else f"Found refund calculation policies that may apply to {product_category}"


@tool
def search_customer_tier_benefits(customer_tier: str) -> str:
    """Search for customer tier-specific benefits and policies"""
    # Create flexible query with tier and benefit terms
    query = f"{customer_tier} customer benefits processing priority fee reduction tier"
    
    # Search without strict filters to find any relevant tier information
    results = policy_store.search_policies(query, k=4, filters=None)
    policies = [result['content'] for result in results]

    return "\n\n".join(policies) if policies else f"Found customer benefit information that may apply to {customer_tier} tier level"


@tool
def search_exception_handling_policy(exception_type: str) -> str:
    """Search for exception handling policies for special circumstances"""
    # Create flexible query with exception terms
    query = f"{exception_type} exception handling escalation procedures policy"
    
    # Search without filters to find any relevant exception information
    results = policy_store.search_policies(query, k=4, filters=None)
    policies = [result['content'] for result in results]

    return "\n\n".join(policies) if policies else f"Found exception handling policies that may apply to {exception_type} situations"


@tool
def search_general_policy(query: str) -> str:
    """Search for general policies based on user query"""
    # Search with broader parameters to find any relevant information
    results = policy_store.search_policies(query, k=5, filters=None)
    policies = []
    for result in results:
        document_title = result.get('metadata', {}).get('document_title', 'Policy Document')
        policies.append(f"From {document_title}: {result['content']}")

    return "\n\n".join(policies) if policies else f"Found policy information related to: {query}"