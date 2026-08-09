"""Database tools for refund processing system."""

from typing import Dict
from langchain_core.tools import tool
from database_creation import Customer, Product, Order, ProcessedRequest, SessionLocal
from datetime import datetime


@tool
def get_customer_info(customer_id: str) -> Dict:
    """Retrieve customer information from database"""
    session = SessionLocal()
    try:
        customer = session.query(Customer).filter(Customer.customer_id == customer_id).first()
        if customer:
            return {
                "customer_id": customer.customer_id,
                "name": f"{customer.first_name} {customer.last_name}",
                "email": customer.email,
                "tier": customer.customer_tier,
                "date_joined": customer.date_joined.isoformat() if customer.date_joined else None,
                "found": True
            }
        return {"found": False, "error": "Customer not found"}
    except Exception as e:
        return {"found": False, "error": str(e)}
    finally:
        session.close()


@tool
def get_order_info(order_id: str) -> Dict:
    """Retrieve order information from database"""
    session = SessionLocal()
    try:
        order = session.query(Order).filter(Order.order_id == order_id).first()
        if order:
            return {
                "order_id": order.order_id,
                "customer_id": order.customer_id,
                "product_id": order.product_id,
                "order_date": order.order_date.isoformat() if order.order_date else None,
                "delivery_date": order.delivery_date.isoformat() if order.delivery_date else None,
                "total_amount": order.total_amount,
                "status": order.status,
                "found": True
            }
        return {"found": False, "error": "Order not found"}
    except Exception as e:
        return {"found": False, "error": str(e)}
    finally:
        session.close()


@tool
def get_product_info(product_id: str) -> Dict:
    """Retrieve product information from database"""
    session = SessionLocal()
    try:
        product = session.query(Product).filter(Product.product_id == product_id).first()
        if product:
            return {
                "product_id": product.product_id,
                "name": product.product_name,
                "category": product.category,
                "price": product.price,
                "return_window_days": product.return_window_days,
                "fragile": product.fragile,
                "restockable": product.restockable,
                "found": True
            }
        return {"found": False, "error": "Product not found"}
    except Exception as e:
        return {"found": False, "error": str(e)}
    finally:
        session.close()


@tool
def get_customer_orders(customer_id: str, limit: int = 10) -> Dict:
    """Retrieve recent orders for a customer (useful for chatbot assistance)"""
    session = SessionLocal()
    try:
        orders = session.query(Order).filter(
            Order.customer_id == customer_id
        ).order_by(Order.order_date.desc()).limit(limit).all()
        
        if orders:
            order_list = []
            for order in orders:
                order_list.append({
                    "order_id": order.order_id,
                    "product_id": order.product_id,
                    "order_date": order.order_date.isoformat() if order.order_date else None,
                    "delivery_date": order.delivery_date.isoformat() if order.delivery_date else None,
                    "total_amount": order.total_amount,
                    "status": order.status
                })
            
            return {
                "found": True,
                "orders": order_list,
                "count": len(order_list)
            }
        return {"found": False, "orders": [], "count": 0}
    except Exception as e:
        return {"found": False, "error": str(e)}
    finally:
        session.close()


@tool
def save_processed_request(request_id: str, customer_id: str, order_id: str, product_id: str,
                          request_type: str, reason: str, description: str, status: str, 
                          decision_reason: str, refund_amount: float = 0.0, agent_notes: str = "",
                          requires_followup: bool = False, followup_reason: str = "") -> Dict:
    """Save processed request results to database"""
    session = SessionLocal()
    try:
        processed_request = ProcessedRequest(
            request_id=request_id,
            customer_id=customer_id,
            order_id=order_id,
            product_id=product_id,
            request_type=request_type,
            reason=reason,
            description=description,
            request_date=datetime.now(),
            status=status,
            decision_reason=decision_reason,
            refund_amount=refund_amount,
            processing_date=datetime.now(),
            agent_notes=agent_notes,
            requires_followup=requires_followup,
            followup_reason=followup_reason
        )
        session.add(processed_request)
        session.commit()
        return {"success": True, "message": "Request saved successfully"}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


@tool
def search_orders_by_customer_email(email: str, limit: int = 5) -> Dict:
    """Search orders by customer email (utility for chatbot)"""
    session = SessionLocal()
    try:
        # First find customer by email
        customer = session.query(Customer).filter(Customer.email == email).first()
        if not customer:
            return {"found": False, "error": "Customer not found"}
        
        # Then get their orders
        orders = session.query(Order).filter(
            Order.customer_id == customer.customer_id
        ).order_by(Order.order_date.desc()).limit(limit).all()
        
        order_list = []
        for order in orders:
            order_list.append({
                "order_id": order.order_id,
                "product_id": order.product_id,
                "order_date": order.order_date.isoformat() if order.order_date else None,
                "delivery_date": order.delivery_date.isoformat() if order.delivery_date else None,
                "total_amount": order.total_amount,
                "status": order.status
            })
        
        return {
            "customer_id": customer.customer_id,
            "customer_name": f"{customer.first_name} {customer.last_name}",
            "orders": order_list,
            "count": len(order_list),
            "found": True
        }
    except Exception as e:
        return {"found": False, "error": str(e)}
    finally:
        session.close()




@tool
def check_previous_refund_requests(order_id: str) -> Dict:
    """Check if a customer has already submitted refund/return requests for this order.

    Only needs the order_id - customer_id and product_id are looked up from the
    order record itself rather than requiring the caller to supply them (those
    values require chaining output from other tool calls, which is error-prone).
    """
    session = SessionLocal()
    try:
        order = session.query(Order).filter(Order.order_id == order_id).first()
        if not order:
            return {"has_previous_requests": False, "error": "Order not found"}

        query = session.query(ProcessedRequest).filter(
            ProcessedRequest.customer_id == order.customer_id,
            ProcessedRequest.order_id == order_id,
            ProcessedRequest.request_type.in_(['Refund', 'Return'])
        )

        previous_requests = query.all()
        
        if not previous_requests:
            return {
                "has_previous_requests": False,
                "message": "No previous refund/return requests found for this order"
            }
        
        # Check for approved/completed requests
        approved_requests = [req for req in previous_requests if req.status in ['Approved', 'Completed']]
        pending_requests = [req for req in previous_requests if req.status in ['In Progress', 'Pending']]
        
        request_details = []
        for req in previous_requests:
            request_details.append({
                "request_id": req.request_id,
                "request_type": req.request_type,
                "status": req.status,
                "request_date": req.request_date.isoformat() if req.request_date else None,
                "refund_amount": req.refund_amount,
                "decision_reason": req.decision_reason
            })
        
        return {
            "has_previous_requests": True,
            "total_requests": len(previous_requests),
            "approved_requests": len(approved_requests),
            "pending_requests": len(pending_requests),
            "request_details": request_details,
            "warning": "Customer has already submitted refund/return requests for this order" if approved_requests else None,
            "blocking": len(approved_requests) > 0  # Block if there are already approved refunds
        }
    except Exception as e:
        return {"has_previous_requests": False, "error": str(e)}
    finally:
        session.close()


@tool
def validate_refund_eligibility(order_id: str, customer_id: str = "") -> Dict:
    """Deterministic, code-computed check of whether a refund/return request is eligible.

    Only needs the order_id - product_id is looked up from the order record itself.
    Pass customer_id ONLY if you already have the real value from a prior tool result
    (never a placeholder) to additionally verify the order belongs to that customer;
    omit it to skip that check.
    """
    session = SessionLocal()
    try:
        # Get order information
        order = session.query(Order).filter(Order.order_id == order_id).first()
        if not order:
            return {"eligible": False, "reason": "Order not found"}

        # Verify customer owns this order, if a customer_id was actually supplied
        if customer_id and order.customer_id != customer_id:
            return {"eligible": False, "reason": "Order does not belong to this customer"}

        # Check if already delivered
        if not order.delivery_date:
            return {"eligible": False, "reason": "Order has not been delivered yet"}

        # Get product information
        product = session.query(Product).filter(Product.product_id == order.product_id).first()
        if not product:
            return {"eligible": False, "reason": "Product not found"}

        # Check return window
        days_since_delivery = (datetime.now() - order.delivery_date).days
        if days_since_delivery > product.return_window_days:
            return {
                "eligible": False,
                "reason": f"Return window expired ({days_since_delivery} days since delivery, {product.return_window_days} day limit)"
            }

        # Check for previous processed requests
        previous_check = check_previous_refund_requests.invoke({"order_id": order_id})
        if previous_check.get("blocking", False):
            return {
                "eligible": False,
                "reason": "Item has already been refunded or returned",
                "previous_requests": previous_check.get("request_details", [])
            }
        
        return {
            "eligible": True,
            "order_info": {
                "order_id": order.order_id,
                "delivery_date": order.delivery_date.isoformat(),
                "total_amount": order.total_amount,
                "status": order.status
            },
            "product_info": {
                "product_name": product.product_name,
                "category": product.category,
                "return_window_days": product.return_window_days,
                "days_since_delivery": days_since_delivery,
                "restockable": product.restockable
            },
            "warnings": previous_check.get("request_details", []) if previous_check.get("has_previous_requests") else []
        }
    except Exception as e:
        return {"eligible": False, "error": str(e)}
    finally:
        session.close()