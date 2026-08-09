"""Multi-agent refund processing system using LangGraph."""

import json
import logging
from typing import Dict, Iterator, List

from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from .model import get_chat_model

from .db_tools import (
    get_customer_info, get_order_info, get_product_info, get_customer_orders,
    save_processed_request, search_orders_by_customer_email,
    check_previous_refund_requests, validate_refund_eligibility
)
from .vector_db_tools import (
    search_return_eligibility_policy, search_refund_calculation_policy,
    search_customer_tier_benefits, search_exception_handling_policy,
    search_general_policy
)
from .email_tools import send_email_notification, log_communication, generate_request_id

logger = logging.getLogger(__name__)

# Tool results carrying an order list, worth surfacing to the UI as a selectable picker
# instead of letting the agent dump it as plain text.
ORDER_LIST_TOOLS = {"search_orders_by_customer_email", "get_customer_orders"}


class RefundProcessingSystem:
    """Multi-agent refund processing system with LangGraph supervisor."""
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize the multi-agent system."""
        self.llm = get_chat_model(config_path)
        self.conversation_history = []
        
        # Create agent tools
        self.validation_tools = [
            get_customer_info, get_order_info, get_product_info, get_customer_orders,
            search_orders_by_customer_email, check_previous_refund_requests,
            validate_refund_eligibility
        ]
        self.policy_tools = [
            search_return_eligibility_policy, search_refund_calculation_policy,
            search_customer_tier_benefits, search_exception_handling_policy,
            search_general_policy
        ]
        self.communication_tools = [
            send_email_notification, log_communication, save_processed_request,
          generate_request_id
        ]
        
        # Create specialized agents
        self.validation_agent = self._create_validation_agent()
        self.policy_agent = self._create_policy_agent()
        self.communication_agent = self._create_communication_agent()
        
        # Create supervisor
        self.supervisor = self._create_supervisor()
        
    def _create_validation_agent(self):
        """Create validation agent for customer/order verification."""
        return create_react_agent(
            model=self.llm,
            tools=self.validation_tools,
            prompt=(
                "You are a Validation Agent for a refund/return processing system.\n\n"
                "CRITICAL: You MUST use the available tools to get real data. DO NOT make up or guess any information.\n\n"
                "AVAILABLE TOOLS:\n"
                "- get_customer_info: Look up customer by email address\n"
                "- search_orders_by_customer_email: Find orders for a customer\n"
                "- get_customer_info: Get customer details by customer ID\n"
                "- get_order_info: Get order details by order ID\n"
                "- get_product_info: Get product details by product ID\n"
                "- get_customer_orders: Get customer's order history\n"
                "- check_previous_refund_requests: Check if customer already submitted a refund/return for this order (needs ONLY order_id)\n"
                "- validate_refund_eligibility: Deterministic, code-computed check of return-window eligibility and duplicate-refund blocking (needs ONLY order_id)\n\n"
                "WORKFLOW:\n"
                "1. If you have an email but no customer info: Use get_customer_info\n"
                "2. If customer wants to return, you need to show orders: Use search_orders_by_customer_email\n"
                "3. If you have order ID but need details: Use get_order_info\n"
                "4. If you have product ID but need details: Use get_product_info\n"
                "5. For ANY refund/return request about a specific order: call the validate_refund_eligibility tool, passing only the order_id — this is REQUIRED, not optional\n\n"
                "ELIGIBILITY IS AUTHORITATIVE AND NON-NEGOTIABLE:\n"
                "- validate_refund_eligibility does the exact date-window and duplicate-request math in code, looking up product and customer details itself from the order_id you give it. It is the ONLY source of truth for whether a return is inside the window or blocked by a prior refund.\n"
                "- It only needs order_id — do NOT pass customer_id or product_id into it (and NEVER pass a placeholder string like 'from previous result' into ANY tool call — if you don't have a real value yet, call the tool that produces it first and wait for the result before calling a tool that needs it).\n"
                "- NEVER estimate, guess, or reason about return-window eligibility yourself from dates in conversation — always call the tool and use its 'eligible' field.\n"
                "- Report the tool's result to the supervisor explicitly and unambiguously as 'ELIGIBILITY: ELIGIBLE' or 'ELIGIBILITY: NOT ELIGIBLE - <reason from tool>' so the supervisor cannot miss it.\n"
                "- If check_previous_refund_requests or validate_refund_eligibility reports 'blocking: true' / 'eligible: false', state this as a hard blocker, not a warning.\n\n"
                "STRICT RULES:\n"
                "- NEVER make up customer data, order IDs, or product information\n"
                "- ALWAYS call the appropriate tool to get real data\n"
                "- If a tool returns 'found: false', report that the item was not found\n"
                "- Only provide information that comes directly from tool results\n"
                "- After using tools, provide clear validation results based on the real data\n"
                "- Always provide all the details to supervisor about orders - order id , product id category product name etc. Use appropriate tools to find all info and compile and then provide to supervisor."
            ),
            name="validation_agent"
        )
    
    def _create_policy_agent(self):
        """Create policy agent for decision making."""
        return create_react_agent(
            model=self.llm,
            tools=self.policy_tools,
            prompt=(
                "You are a Policy Agent for refund/return processing.\n\n"
                "CRITICAL: You MUST use the available tools to search for actual policies. DO NOT make assumptions.\n\n"
                "AVAILABLE TOOLS:\n"
                "- search_return_eligibility_policy: Search return window policies by product category\n"
                "- search_refund_calculation_policy: Search refund calculation rules\n"
                "- search_customer_tier_benefits: Search tier-specific customer benefits\n"
                "- search_exception_handling_policy: Search exception handling procedures\n"
                "- search_general_policy: Search general policies by query\n\n"
                "CRITICAL: When receiving delegation from supervisor, extract actual values from conversation:\n"
                "- Look for REAL product category (e.g., 'Electronics', 'Clothing', NOT 'general')\n"
                "- Look for REAL customer tier (e.g., 'Premium', 'Gold', 'Bronze', NOT 'standard')\n"
                "- If you don't see these values, ask for them explicitly\n\n"
                "WORKFLOW:\n"
                "1. Use search_return_eligibility_policy with ACTUAL product category\n"
                "2. Use search_customer_tier_benefits with ACTUAL customer tier\n"
                "3. Use search_refund_calculation_policy with ACTUAL product category\n"
                "4. Use search_exception_handling_policy if special circumstances apply\n\n"
                "ELIGIBILITY IS DECIDED BY VALIDATION, NOT BY YOU:\n"
                "- The validation agent already ran a deterministic (code-computed, not text-search) eligibility check and will have told the supervisor 'ELIGIBILITY: ELIGIBLE' or 'ELIGIBILITY: NOT ELIGIBLE - <reason>'. The supervisor will pass this to you.\n"
                "- If you were told the order is NOT ELIGIBLE (outside return window, or blocked by a prior refund/return), your decision MUST be 'Rejected' citing that exact reason. Do NOT re-derive eligibility from the policy text yourself, do NOT override it, and do NOT search for a way to approve it anyway.\n"
                "- Only when you were told the order IS ELIGIBLE should you use the policy tools below to determine the refund AMOUNT (restocking fees, condition deductions, tier-based reductions) and cite the applicable policy.\n"
                "- If you were not told an eligibility status at all, say so explicitly and ask the supervisor to have validation run validate_refund_eligibility first — do not guess.\n\n"
                "DECISION MAKING:\n"
                "- Approved: Validation confirmed eligible, and refund amount calculated per policy\n"
                "- Rejected: Validation confirmed NOT eligible (outside return window or duplicate/blocked)\n"
                "- Needs Review: Eligible but a complex case (e.g. conflicting exception policy) requiring human judgment\n\n"
                "STRICT RULES:\n"
                "- ALWAYS search for relevant policies using tools before calculating a refund amount\n"
                "- Base refund AMOUNT calculations on actual policy search results, not assumptions\n"
                "- Provide specific policy citations in your reasoning\n"
                "- Calculate exact refund amounts based on found policies\n"
            ),
            name="policy_agent"
        )
    
    def _create_communication_agent(self):
        """Create communication agent for customer notifications."""
        return create_react_agent(
            model=self.llm,
            tools=self.communication_tools,
            prompt=(
                "You are a Communication Agent for customer notifications and record keeping.\n\n"
                "CRITICAL: You MUST use the available tools to actually send emails and save data.\n\n"
                "AVAILABLE TOOLS:\n"
                "- send_email_notification: Send email to customer with subject and message\n"
                "- log_communication: Log communication activities for audit trail\n"
                "- generate_request_id: Generate a unique request ID\n"
                "- save_processed_request: Save complete request processing results to database\n\n"
                "WORKFLOW:\n"
                "1. Use send_email_notification to notify customer of decision\n"
                "2. Use log_communication to record the communication\n"
                "3. Use generate_request_id to generate a request ID\n"
                "4. Use save_processed_request (with the generated request ID) to save all processing details to database\n\n"
                "EMAIL GUIDELINES:\n"
                "- Use professional, empathetic tone\n"
                "- Include request ID and relevant details\n"
                "- Provide clear next steps for customer\n"
                "- Include contact information for follow-up\n\n"
                "STRICT RULES:\n"
                "- ALWAYS use tools to actually send emails and save data\n"
                "- DO NOT just say you will send an email - actually use the tools\n"
                "- Provide confirmation of actions taken using tool results\n"
            ),
            name="communication_agent"
        )
    
    def _create_supervisor(self):
        """Create supervisor to orchestrate the agents."""
        return create_supervisor(
            model=self.llm,
            agents=[self.validation_agent, self.policy_agent, self.communication_agent],
            prompt=(
                "You are a friendly customer service representative helping customers with refunds, returns, and exchanges.\n\n"
                "CRITICAL: Your agents MUST use their tools to get real data. Do NOT accept hallucinated information.\n\n"
                "CONVERSATION MEMORY:\n"
                "- You have access to the full conversation history\n"
                "- Remember what you've already learned: customer email, orders, issues discussed\n"
                "- DON'T ask for information you already have\n"
                "- Reference previous parts of the conversation naturally\n\n"
                "AGENT DELEGATION (only do ONE step per response):\n"
                "1. If no email provided yet: Ask for email address\n"
                "2. If email provided but customer not looked up: Delegate to VALIDATION AGENT with explicit instruction: 'Use get_customer_info tool to look up customer with email [email]'\n"
                "3. If customer found but orders not shown: Delegate to VALIDATION AGENT with explicit instruction: 'Use search_orders_by_customer_email tool to find orders for [email]'\n"
                "4. If order mentioned but issue not clear: Ask what specific problem they're having\n"
                "5. If issue described but order details/eligibility not yet checked: Delegate to VALIDATION AGENT with explicit instruction: 'Use get_order_info and get_product_info for order [order_id], then call the validate_refund_eligibility tool with that order_id and report ELIGIBILITY explicitly'\n"
                "6. If validation reported 'ELIGIBILITY: NOT ELIGIBLE' or a blocking duplicate request: STOP HERE — do NOT delegate to the policy agent. Tell the customer directly that the request is rejected and state validation's exact reason, then proceed to step 8 to have it communicated/logged. This is a hard rule with no exceptions, regardless of how sympathetic the situation seems.\n"
                "7. If validation reported 'ELIGIBILITY: ELIGIBLE' but policy/refund amount not yet checked: Delegate to POLICY AGENT with explicit instruction: 'Validation confirmed ELIGIBLE. Use policy search tools to calculate the refund amount' and give all order details - order id, product category, customer tier etc to policy agent\n"
                "8. If a decision (approved with amount, or rejected) has been made but not confirmed with the customer: Tell customer the decision and reason, then ask if they want to proceed\n"
                "9. If customer confirms (or if it was an automatic rejection from step 6): Delegate to COMMUNICATION AGENT with explicit instruction: 'Use tools to send email notification of the [approved/rejected] decision and save request to database with status [Approved/Rejected]'\n\n"
                "AVAILABLE AGENTS:\n"
                "1. VALIDATION AGENT: Has tools for customer lookup, order verification, product info, and the authoritative validate_refund_eligibility check\n"
                "2. POLICY AGENT: Has tools for policy search and refund amount calculation — only consulted for ELIGIBLE requests\n"
                "3. COMMUNICATION AGENT: Has tools for email sending and database storage\n\n"
                "CRITICAL RULES:\n"
                "- When delegating, give EXPLICIT tool usage instructions to agents\n"
                "- If an agent returns made-up data instead of using tools, redirect them with specific tool instructions\n"
                "- REMEMBER conversation history - don't repeat questions\n"
                "- Do only ONE step per response\n"
                "- Verify agents actually used tools by checking their responses for tool call results\n"
                "- NEVER approve or forward to the policy agent a request that validation marked NOT ELIGIBLE or blocked as a duplicate — eligibility from validation is final and cannot be overridden by you or the policy agent\n"
                "- Always trigger communication agent at the end to first email the customer of the interaction and finally update the database, for BOTH approvals and rejections\n"
                "- When you find out all order details , always mention all orders and then ask which orders the customer is referring to. Do not assume which the order id."
            ),
            add_handoff_back_messages=True,
            output_mode="full_history"
        ).compile()
    
    def process_refund_request(self, request_data: Dict) -> Dict:
        """
        Process a refund/return request through the multi-agent workflow.
        
        Args:
            request_data: Dict containing request details
            
        Returns:
            Dict with processing results
        """
        request_message = f"""
        New refund request to process:
        
        Request ID: {request_data['request_id']}
        Customer ID: {request_data.get('customer_id', 'Not provided')}
        Order ID: {request_data.get('order_id', 'Not provided')}
        Request Type: {request_data['request_type']}
        Reason: {request_data['reason']}
        Description: {request_data['description']}
        
        Please process this request through the complete workflow:
        1. Start with validation to verify all details
        2. If valid, apply policies to make a decision
        3. Finally, communicate results to customer and save to database
        """
        
        try:
            # Execute the supervisor workflow
            result = self.supervisor.invoke({
                "messages": [{"role": "user", "content": request_message}]
            })
            
            # Extract the final message from supervisor
            final_messages = result.get("messages", [])
            if final_messages:
                final_response = final_messages[-1].content
                
                return {
                    "request_id": request_data['request_id'],
                    "status": "processed",
                    "workflow_complete": True,
                    "final_response": final_response,
                    "success": True
                }
            else:
                return {
                    "request_id": request_data['request_id'],
                    "status": "error",
                    "error": "No response from supervisor",
                    "success": False
                }
                
        except Exception as e:
            return {
                "request_id": request_data['request_id'],
                "status": "error",
                "error": str(e),
                "success": False
            }
    
    def stream_events(self, message: str) -> Iterator[Dict]:
        """
        Run `message` through the supervisor workflow, yielding structured events as
        they happen so a UI can render live agent activity (which agent is working,
        what tools it's calling, what came back) instead of only the final response.
        Also appends the turn to self.conversation_history.

        Event shapes:
          {"type": "tool_call", "agent": str, "name": str, "args": dict}
          {"type": "tool_result", "agent": str, "name": str, "content": Any}
          {"type": "order_options", "agent": str, "orders": list[dict]}
          {"type": "agent_text", "agent": str, "content": str}
          {"type": "final", "content": str}
        """
        logger.debug("User message: %s", message)
        self.conversation_history.append(HumanMessage(content=message))

        messages_payload = []
        for msg in self.conversation_history:
            if isinstance(msg, HumanMessage):
                messages_payload.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                messages_payload.append({"role": "assistant", "content": msg.content})

        final_response = ""
        try:
            for chunk in self.supervisor.stream({"messages": messages_payload}):
                if not isinstance(chunk, dict):
                    continue

                for node_name, node_update in chunk.items():
                    for msg in node_update.get("messages", []):
                        if isinstance(msg, ToolMessage):
                            content = msg.content
                            try:
                                parsed = json.loads(content) if isinstance(content, str) else content
                            except (TypeError, ValueError):
                                parsed = content

                            yield {"type": "tool_result", "agent": node_name, "name": msg.name, "content": parsed}

                            if msg.name in ORDER_LIST_TOOLS and isinstance(parsed, dict) and parsed.get("orders"):
                                yield {"type": "order_options", "agent": node_name, "orders": parsed["orders"]}

                        elif isinstance(msg, AIMessage):
                            for call in (msg.tool_calls or []):
                                yield {
                                    "type": "tool_call",
                                    "agent": node_name,
                                    "name": call.get("name"),
                                    "args": call.get("args", {}),
                                }
                            if msg.content:
                                yield {"type": "agent_text", "agent": node_name, "content": msg.content}
                                final_response = msg.content

        except Exception as e:
            logger.exception("Supervisor workflow failed")
            final_response = f"I encountered an error: {str(e)}. Please try again or contact support."
            yield {"type": "agent_text", "agent": "system", "content": final_response}

        if final_response:
            self.conversation_history.append(AIMessage(content=final_response))

        yield {
            "type": "final",
            "content": final_response or "I apologize, but I couldn't process your request. Please try again.",
        }

    def chat_with_supervisor(self, message: str) -> str:
        """Chat with the supervisor, returning only the final text (no live trace)."""
        final_content = ""
        for event in self.stream_events(message):
            if event["type"] == "final":
                final_content = event["content"]
        return final_content

    def get_workflow_graph(self):
        """Get visual representation of the workflow."""
        return self.supervisor.get_graph().draw_mermaid_png()


# Global instance for easy import
refund_system = None

def get_refund_system(config_path: str = "config.yaml"):
    """Get or create global refund system instance."""
    global refund_system
    if refund_system is None:
        refund_system = RefundProcessingSystem(config_path)
    return refund_system