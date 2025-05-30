import graphene
from graphene import relay
from graphene_sqlalchemy import SQLAlchemyObjectType, SQLAlchemyConnectionField
from models import ProductionFeedback, ProductionHistory, QualityCheck, MarketplaceNotification, get_session
from sqlalchemy import desc, and_
import datetime
import requests
import json
import sys
import os

# Add parent directory to path to import common modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.config import GRAPHQL_ENDPOINTS

# Define GraphQL types
class ProductionFeedbackType(SQLAlchemyObjectType):
    class Meta:
        model = ProductionFeedback
        interfaces = (relay.Node, )

class ProductionHistoryType(SQLAlchemyObjectType):
    class Meta:
        model = ProductionHistory
        interfaces = (relay.Node, )

class QualityCheckType(SQLAlchemyObjectType):
    class Meta:
        model = QualityCheck
        interfaces = (relay.Node, )

class MarketplaceNotificationType(SQLAlchemyObjectType):
    class Meta:
        model = MarketplaceNotification
        interfaces = (relay.Node, )

# Input types for mutations
class ProductionFeedbackInput(graphene.InputObjectType):
    batch_id = graphene.Int(required=True)
    step_id = graphene.Int()
    status = graphene.String(required=True)
    completion_percentage = graphene.Float()
    quality_score = graphene.Float()
    quality_data = graphene.JSONString()
    issues = graphene.String()

class ProductionHistoryInput(graphene.InputObjectType):
    batch_id = graphene.Int(required=True)
    batch_number = graphene.String()
    product_id = graphene.Int(required=True)
    quantity = graphene.Int(required=True)
    start_time = graphene.DateTime()
    end_time = graphene.DateTime()
    duration_minutes = graphene.Int()
    status = graphene.String(required=True)
    marketplace_order_id = graphene.String()
    notes = graphene.String()

class QualityCheckInput(graphene.InputObjectType):
    batch_id = graphene.Int(required=True)
    step_id = graphene.Int()
    check_type = graphene.String(required=True)
    parameter_name = graphene.String(required=True)
    expected_value = graphene.String()
    actual_value = graphene.String()
    passed = graphene.Boolean(required=True)
    severity = graphene.Int()
    notes = graphene.String()
    checked_by = graphene.String()

class MarketplaceNotificationInput(graphene.InputObjectType):
    batch_id = graphene.Int(required=True)
    marketplace_order_id = graphene.String(required=True)
    notification_type = graphene.String(required=True)
    message = graphene.String(required=True)

# Helper functions for interacting with other services
def get_batch_details(batch_id):
    """Get batch details from Production Management Service"""
    try:
        query = """
        query($id: Int!) {
            productionBatch(id: $id) {
                id
                batchNumber
                orderId
                productId
                quantity
                status
                actualStart
                actualEnd
            }
        }
        """
        variables = {"id": batch_id}
        
        # Make request to Production Management Service
        response = requests.post(
            GRAPHQL_ENDPOINTS["production_management"],
            json={"query": query, "variables": variables}
        )
        
        data = response.json()
        if 'data' in data and 'productionBatch' in data['data']:
            return data['data']['productionBatch']
        return None
    except Exception as e:
        print(f"Error fetching batch details: {e}")
        return None

def notify_marketplace(order_id, status, message):
    """Send notification to marketplace (dummy implementation)"""
    try:
        # In a real implementation, this would make an API call to the marketplace
        # For now, we'll just log it
        print(f"Marketplace notification for order {order_id}: {status} - {message}")
        return {
            "success": True,
            "message": "Notification sent to marketplace"
        }
    except Exception as e:
        print(f"Error notifying marketplace: {e}")
        return {
            "success": False,
            "message": f"Error: {str(e)}"
        }

# Mutations
class CreateProductionFeedback(graphene.Mutation):
    class Arguments:
        input = ProductionFeedbackInput(required=True)
    
    production_feedback = graphene.Field(lambda: ProductionFeedbackType)
    success = graphene.Boolean()
    message = graphene.String()
    
    def mutate(self, info, input):
        session = get_session()
        
        # Create production feedback
        feedback = ProductionFeedback(
            batch_id=input.batch_id,
            step_id=input.step_id,
            status=input.status,
            completion_percentage=input.completion_percentage or 0,
            quality_score=input.quality_score,
            quality_data=input.quality_data,
            issues=input.issues
        )
        
        session.add(feedback)
        session.commit()
        session.refresh(feedback)
        
        # If status is 'completed', add to production history
        if input.status == 'completed' and not input.step_id:  # Only for batch-level completion
            batch_details = get_batch_details(input.batch_id)
            
            if batch_details:
                # Calculate duration
                duration_minutes = None
                if batch_details.get('actualStart') and batch_details.get('actualEnd'):
                    start = datetime.datetime.fromisoformat(batch_details['actualStart'].replace('Z', '+00:00'))
                    end = datetime.datetime.fromisoformat(batch_details['actualEnd'].replace('Z', '+00:00'))
                    duration_minutes = int((end - start).total_seconds() / 60)
                
                # Create production history record
                history = ProductionHistory(
                    batch_id=input.batch_id,
                    batch_number=batch_details.get('batchNumber'),
                    product_id=batch_details.get('productId'),
                    quantity=batch_details.get('quantity'),
                    start_time=batch_details.get('actualStart'),
                    end_time=batch_details.get('actualEnd'),
                    duration_minutes=duration_minutes,
                    status=input.status,
                    marketplace_order_id=batch_details.get('orderId'),
                    notes=input.issues
                )
                
                session.add(history)
                session.commit()
                
                # Create marketplace notification
                if batch_details.get('orderId'):
                    notification = MarketplaceNotification(
                        batch_id=input.batch_id,
                        marketplace_order_id=batch_details.get('orderId'),
                        notification_type='status_update',
                        message=f"Production completed for batch {batch_details.get('batchNumber')}. Quality score: {input.quality_score or 'N/A'}"
                    )
                    
                    session.add(notification)
                    session.commit()
        
        session.close()
        
        return CreateProductionFeedback(
            production_feedback=feedback,
            success=True,
            message="Production feedback recorded successfully"
        )

class CreateQualityCheck(graphene.Mutation):
    class Arguments:
        input = QualityCheckInput(required=True)
    
    quality_check = graphene.Field(lambda: QualityCheckType)
    success = graphene.Boolean()
    message = graphene.String()
    
    def mutate(self, info, input):
        session = get_session()
        
        # Create quality check
        check = QualityCheck(
            batch_id=input.batch_id,
            step_id=input.step_id,
            check_type=input.check_type,
            parameter_name=input.parameter_name,
            expected_value=input.expected_value,
            actual_value=input.actual_value,
            passed=input.passed,
            severity=input.severity,
            notes=input.notes,
            checked_by=input.checked_by or 'system'
        )
        
        session.add(check)
        session.commit()
        session.refresh(check)
        
        # If quality check failed with high severity, create a marketplace notification
        if not input.passed and input.severity == 3:  # High severity
            batch_details = get_batch_details(input.batch_id)
            
            if batch_details and batch_details.get('orderId'):
                notification = MarketplaceNotification(
                    batch_id=input.batch_id,
                    marketplace_order_id=batch_details.get('orderId'),
                    notification_type='quality_issue',
                    message=f"Quality issue detected in batch {batch_details.get('batchNumber')}: {input.parameter_name} failed quality check. {input.notes or ''}"
                )
                
                session.add(notification)
                session.commit()
        
        session.close()
        
        return CreateQualityCheck(
            quality_check=check,
            success=True,
            message="Quality check recorded successfully"
        )

class CreateMarketplaceNotification(graphene.Mutation):
    class Arguments:
        input = MarketplaceNotificationInput(required=True)
    
    marketplace_notification = graphene.Field(lambda: MarketplaceNotificationType)
    success = graphene.Boolean()
    message = graphene.String()
    
    def mutate(self, info, input):
        session = get_session()
        
        # Create marketplace notification
        notification = MarketplaceNotification(
            batch_id=input.batch_id,
            marketplace_order_id=input.marketplace_order_id,
            notification_type=input.notification_type,
            message=input.message
        )
        
        session.add(notification)
        session.commit()
        session.refresh(notification)
        session.close()
        
        return CreateMarketplaceNotification(
            marketplace_notification=notification,
            success=True,
            message="Marketplace notification created successfully"
        )

class SendMarketplaceNotification(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
    
    marketplace_notification = graphene.Field(lambda: MarketplaceNotificationType)
    success = graphene.Boolean()
    message = graphene.String()
    
    def mutate(self, info, id):
        session = get_session()
        notification = session.query(MarketplaceNotification).filter(MarketplaceNotification.id == id).first()
        
        if not notification:
            return SendMarketplaceNotification(
                marketplace_notification=None,
                success=False,
                message=f"Notification with ID {id} not found"
            )
        
        if notification.sent:
            return SendMarketplaceNotification(
                marketplace_notification=notification,
                success=False,
                message=f"Notification already sent at {notification.sent_at}"
            )
        
        # Send notification to marketplace
        result = notify_marketplace(
            notification.marketplace_order_id,
            notification.notification_type,
            notification.message
        )
        
        # Update notification status
        notification.sent = result.get('success', False)
        notification.sent_at = datetime.datetime.utcnow()
        notification.error_message = None if result.get('success') else result.get('message')
        
        session.commit()
        session.refresh(notification)
        session.close()
        
        return SendMarketplaceNotification(
            marketplace_notification=notification,
            success=result.get('success', False),
            message=result.get('message', "Unknown error")
        )

class Mutation(graphene.ObjectType):
    create_production_feedback = CreateProductionFeedback.Field()
    create_quality_check = CreateQualityCheck.Field()
    create_marketplace_notification = CreateMarketplaceNotification.Field()
    send_marketplace_notification = SendMarketplaceNotification.Field()

# Queries
class Query(graphene.ObjectType):
    node = relay.Node.Field()
    
    # Production feedback queries
    production_feedback = graphene.Field(ProductionFeedbackType, id=graphene.Int())
    production_feedbacks_by_batch = graphene.List(ProductionFeedbackType, batch_id=graphene.Int())
    latest_feedback_by_batch = graphene.Field(ProductionFeedbackType, batch_id=graphene.Int())
    
    # Production history queries
    production_history = graphene.Field(ProductionHistoryType, id=graphene.Int())
    production_histories_by_product = graphene.List(
        ProductionHistoryType, 
        product_id=graphene.Int(),
        start_date=graphene.String(),
        end_date=graphene.String()
    )
    recent_production_histories = graphene.List(ProductionHistoryType, limit=graphene.Int())
    
    # Quality check queries
    quality_check = graphene.Field(QualityCheckType, id=graphene.Int())
    quality_checks_by_batch = graphene.List(QualityCheckType, batch_id=graphene.Int())
    failed_quality_checks = graphene.List(QualityCheckType, batch_id=graphene.Int())
    
    # Marketplace notification queries
    marketplace_notification = graphene.Field(MarketplaceNotificationType, id=graphene.Int())
    marketplace_notifications_by_order = graphene.List(
        MarketplaceNotificationType, 
        marketplace_order_id=graphene.String()
    )
    unsent_marketplace_notifications = graphene.List(MarketplaceNotificationType)
    
    def resolve_production_feedback(self, info, id):
        session = get_session()
        feedback = session.query(ProductionFeedback).filter(ProductionFeedback.id == id).first()
        session.close()
        return feedback
    
    def resolve_production_feedbacks_by_batch(self, info, batch_id):
        session = get_session()
        feedbacks = session.query(ProductionFeedback).filter(
            ProductionFeedback.batch_id == batch_id
        ).order_by(ProductionFeedback.timestamp).all()
        session.close()
        return feedbacks
    
    def resolve_latest_feedback_by_batch(self, info, batch_id):
        session = get_session()
        feedback = session.query(ProductionFeedback).filter(
            ProductionFeedback.batch_id == batch_id
        ).order_by(desc(ProductionFeedback.timestamp)).first()
        session.close()
        return feedback
    
    def resolve_production_history(self, info, id):
        session = get_session()
        history = session.query(ProductionHistory).filter(ProductionHistory.id == id).first()
        session.close()
        return history
    
    def resolve_production_histories_by_product(self, info, product_id, start_date=None, end_date=None):
        session = get_session()
        query = session.query(ProductionHistory).filter(ProductionHistory.product_id == product_id)
        
        if start_date:
            start = datetime.datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(ProductionHistory.end_time >= start)
        
        if end_date:
            end = datetime.datetime.strptime(end_date, '%Y-%m-%d')
            end = end.replace(hour=23, minute=59, second=59)
            query = query.filter(ProductionHistory.end_time <= end)
        
        histories = query.order_by(desc(ProductionHistory.end_time)).all()
        session.close()
        return histories
    
    def resolve_recent_production_histories(self, info, limit=10):
        session = get_session()
        histories = session.query(ProductionHistory).order_by(
            desc(ProductionHistory.created_at)
        ).limit(limit).all()
        session.close()
        return histories
    
    def resolve_quality_check(self, info, id):
        session = get_session()
        check = session.query(QualityCheck).filter(QualityCheck.id == id).first()
        session.close()
        return check
    
    def resolve_quality_checks_by_batch(self, info, batch_id):
        session = get_session()
        checks = session.query(QualityCheck).filter(
            QualityCheck.batch_id == batch_id
        ).order_by(QualityCheck.timestamp).all()
        session.close()
        return checks
    
    def resolve_failed_quality_checks(self, info, batch_id=None):
        session = get_session()
        query = session.query(QualityCheck).filter(QualityCheck.passed == False)
        
        if batch_id:
            query = query.filter(QualityCheck.batch_id == batch_id)
        
        checks = query.order_by(desc(QualityCheck.timestamp)).all()
        session.close()
        return checks
    
    def resolve_marketplace_notification(self, info, id):
        session = get_session()
        notification = session.query(MarketplaceNotification).filter(MarketplaceNotification.id == id).first()
        session.close()
        return notification
    
    def resolve_marketplace_notifications_by_order(self, info, marketplace_order_id):
        session = get_session()
        notifications = session.query(MarketplaceNotification).filter(
            MarketplaceNotification.marketplace_order_id == marketplace_order_id
        ).order_by(desc(MarketplaceNotification.created_at)).all()
        session.close()
        return notifications
    
    def resolve_unsent_marketplace_notifications(self, info):
        session = get_session()
        notifications = session.query(MarketplaceNotification).filter(
            MarketplaceNotification.sent == False
        ).order_by(MarketplaceNotification.created_at).all()
        session.close()
        return notifications

schema = graphene.Schema(query=Query, mutation=Mutation)
