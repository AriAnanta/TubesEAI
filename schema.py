import graphene
from graphene import relay
from graphene_sqlalchemy import SQLAlchemyObjectType, SQLAlchemyConnectionField
from models import Machine, MachineQueueItem, QueueItemMaterial, OperationLog, get_session
from sqlalchemy import desc, and_, func
import datetime
import requests
import json
import sys
import os

# Add parent directory to path to import common modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.config import GRAPHQL_ENDPOINTS

# Define GraphQL types
class MachineType(SQLAlchemyObjectType):
    class Meta:
        model = Machine
        interfaces = (relay.Node, )

class MachineQueueItemType(SQLAlchemyObjectType):
    class Meta:
        model = MachineQueueItem
        interfaces = (relay.Node, )

class QueueItemMaterialType(SQLAlchemyObjectType):
    class Meta:
        model = QueueItemMaterial
        interfaces = (relay.Node, )

class OperationLogType(SQLAlchemyObjectType):
    class Meta:
        model = OperationLog
        interfaces = (relay.Node, )

# Input types for mutations
class MachineInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    machine_type = graphene.String(required=True)
    status = graphene.String()
    last_maintenance = graphene.DateTime()
    next_maintenance = graphene.DateTime()

class AddToQueueInput(graphene.InputObjectType):
    machine_id = graphene.Int(required=True)
    production_step_id = graphene.Int(required=True)
    batch_id = graphene.Int(required=True)
    priority = graphene.Int()
    setup_time_minutes = graphene.Int()
    processing_time_minutes = graphene.Int(required=True)
    materials = graphene.List(graphene.String)  # Format: "material_id:quantity"

class UpdateQueueItemInput(graphene.InputObjectType):
    position = graphene.Int()
    priority = graphene.Int()
    status = graphene.String()
    estimated_start_time = graphene.DateTime()
    estimated_end_time = graphene.DateTime()
    actual_start_time = graphene.DateTime()
    actual_end_time = graphene.DateTime()
    setup_time_minutes = graphene.Int()
    processing_time_minutes = graphene.Int()
    materials_ready = graphene.Boolean()

class OperationLogInput(graphene.InputObjectType):
    machine_id = graphene.Int(required=True)
    queue_item_id = graphene.Int(required=True)
    operation_type = graphene.String(required=True)
    operator = graphene.String()
    notes = graphene.String()
    error_details = graphene.String()

# Helper functions for interacting with other services
def check_material_availability(material_id, quantity_needed):
    """Check if material is available in sufficient quantity"""
    try:
        query = """
        query($id: Int!) {
            material(id: $id) {
                id
                name
                quantity
            }
        }
        """
        variables = {"id": material_id}
        
        # Make request to Material Inventory Service
        response = requests.post(
            GRAPHQL_ENDPOINTS["material_inventory"],
            json={"query": query, "variables": variables}
        )
        
        data = response.json()
        if 'data' in data and 'material' in data['data'] and data['data']['material']:
            available_quantity = data['data']['material']['quantity']
            return available_quantity >= quantity_needed
        
        return False
    except Exception as e:
        print(f"Error checking material availability: {e}")
        return False

def get_production_step_details(step_id):
    """Get production step details from Production Management Service"""
    try:
        query = """
        query($id: Int!) {
            productionStep(id: $id) {
                id
                batchId
                stepNumber
                name
                status
            }
        }
        """
        variables = {"id": step_id}
        
        # Make request to Production Management Service
        response = requests.post(
            GRAPHQL_ENDPOINTS["production_management"],
            json={"query": query, "variables": variables}
        )
        
        data = response.json()
        if 'data' in data and 'productionStep' in data['data']:
            return data['data']['productionStep']
        return None
    except Exception as e:
        print(f"Error fetching production step: {e}")
        return None

def send_production_feedback(batch_id, step_id, status, completion_percentage=None):
    """Send production status updates to Production Feedback Service"""
    try:
        mutation = """
        mutation($input: ProductionFeedbackInput!) {
            createProductionFeedback(input: $input) {
                productionFeedback {
                    id
                }
                success
                message
            }
        }
        """
        variables = {
            "input": {
                "batchId": batch_id,
                "stepId": step_id,
                "status": status,
                "completionPercentage": completion_percentage
            }
        }
        
        # Make request to Production Feedback Service
        response = requests.post(
            GRAPHQL_ENDPOINTS["production_feedback"],
            json={"query": mutation, "variables": variables}
        )
        
        data = response.json()
        if 'data' in data and 'createProductionFeedback' in data['data']:
            return data['data']['createProductionFeedback']
        return None
    except Exception as e:
        print(f"Error sending production feedback: {e}")
        return None

# Mutations
class CreateMachine(graphene.Mutation):
    class Arguments:
        input = MachineInput(required=True)
    
    machine = graphene.Field(lambda: MachineType)
    success = graphene.Boolean()
    message = graphene.String()
    
    def mutate(self, info, input):
        session = get_session()
        
        machine = Machine(
            name=input.name,
            machine_type=input.machine_type,
            status=input.status or 'available',
            last_maintenance=input.last_maintenance,
            next_maintenance=input.next_maintenance
        )
        
        session.add(machine)
        session.commit()
        session.refresh(machine)
        session.close()
        
        return CreateMachine(
            machine=machine,
            success=True,
            message="Machine created successfully"
        )

class UpdateMachine(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        input = MachineInput(required=True)
    
    machine = graphene.Field(lambda: MachineType)
    success = graphene.Boolean()
    message = graphene.String()
    
    def mutate(self, info, id, input):
        session = get_session()
        machine = session.query(Machine).filter(Machine.id == id).first()
        
        if not machine:
            return UpdateMachine(
                machine=None,
                success=False,
                message=f"Machine with ID {id} not found"
            )
        
        machine.name = input.name
        machine.machine_type = input.machine_type
        machine.status = input.status or machine.status
        machine.last_maintenance = input.last_maintenance or machine.last_maintenance
        machine.next_maintenance = input.next_maintenance or machine.next_maintenance
        
        session.commit()
        session.refresh(machine)
        session.close()
        
        return UpdateMachine(
            machine=machine,
            success=True,
            message="Machine updated successfully"
        )

class AddToQueue(graphene.Mutation):
    class Arguments:
        input = AddToQueueInput(required=True)
    
    machine_queue_item = graphene.Field(lambda: MachineQueueItemType)
    success = graphene.Boolean()
    message = graphene.String()
    
    def mutate(self, info, input):
        session = get_session()
        
        # Check if machine exists
        machine = session.query(Machine).filter(Machine.id == input.machine_id).first()
        if not machine:
            return AddToQueue(
                machine_queue_item=None,
                success=False,
                message=f"Machine with ID {input.machine_id} not found"
            )
        
        # Get current highest position for this machine
        max_position_result = session.query(func.max(MachineQueueItem.position)).filter(
            MachineQueueItem.machine_id == input.machine_id,
            MachineQueueItem.status.in_(['queued', 'in_progress'])
        ).first()
        
        next_position = 1
        if max_position_result and max_position_result[0]:
            next_position = max_position_result[0] + 1
        
        # Calculate estimated times based on queue
        estimated_start_time = None
        
        # Get all items in the queue ahead of this one
        queue_items_ahead = session.query(MachineQueueItem).filter(
            MachineQueueItem.machine_id == input.machine_id,
            MachineQueueItem.status.in_(['queued', 'in_progress'])
        ).order_by(MachineQueueItem.position).all()
        
        if queue_items_ahead:
            # Calculate estimated start time based on items ahead in queue
            total_minutes_ahead = sum(item.setup_time_minutes + item.processing_time_minutes for item in queue_items_ahead)
            
            if machine.status == 'busy' and machine.current_queue_item_id:
                # If machine is busy, estimate from current queue item's estimated end time
                current_item = session.query(MachineQueueItem).filter(MachineQueueItem.id == machine.current_queue_item_id).first()
                if current_item and current_item.estimated_end_time:
                    estimated_start_time = current_item.estimated_end_time
                else:
                    estimated_start_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=total_minutes_ahead)
            else:
                estimated_start_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=total_minutes_ahead)
        else:
            # If no items ahead, check if machine is available
            if machine.status == 'available':
                estimated_start_time = datetime.datetime.utcnow()
            else:
                # Default to now + 1 hour if machine is not available and no queue
                estimated_start_time = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        
        # Calculate estimated end time
        total_time = (input.setup_time_minutes or 0) + input.processing_time_minutes
        estimated_end_time = estimated_start_time + datetime.timedelta(minutes=total_time) if estimated_start_time else None
        
        # Create queue item
        queue_item = MachineQueueItem(
            machine_id=input.machine_id,
            production_step_id=input.production_step_id,
            batch_id=input.batch_id,
            position=next_position,
            priority=input.priority or 1,
            status='queued',
            estimated_start_time=estimated_start_time,
            estimated_end_time=estimated_end_time,
            setup_time_minutes=input.setup_time_minutes or 0,
            processing_time_minutes=input.processing_time_minutes
        )
        
        session.add(queue_item)
        session.flush()  # Get queue item ID
        
        # Add materials if provided
        materials_ready = True
        if hasattr(input, 'materials') and input.materials:
            for material_str in input.materials:
                material_id, quantity = map(float, material_str.split(':'))
                material_id = int(material_id)
                
                # Check material availability
                is_available = check_material_availability(material_id, quantity)
                if not is_available:
                    materials_ready = False
                
                # Add to queue item materials
                queue_item_material = QueueItemMaterial(
                    queue_item_id=queue_item.id,
                    material_id=material_id,
                    quantity_required=quantity,
                    is_available=is_available
                )
                session.add(queue_item_material)
        
        queue_item.materials_ready = materials_ready
        
        # Add operation log
        log = OperationLog(
            machine_id=input.machine_id,
            queue_item_id=queue_item.id,
            operation_type='queued',
            operator='system',
            notes=f"Added to queue with position {next_position}"
        )
        session.add(log)
        
        session.commit()
        session.refresh(queue_item)
        session.close()
        
        return AddToQueue(
            machine_queue_item=queue_item,
            success=True,
            message="Item added to queue successfully"
        )

class UpdateQueueItem(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        input = UpdateQueueItemInput(required=True)
    
    machine_queue_item = graphene.Field(lambda: MachineQueueItemType)
    success = graphene.Boolean()
    message = graphene.String()
    
    def mutate(self, info, id, input):
        session = get_session()
        queue_item = session.query(MachineQueueItem).filter(MachineQueueItem.id == id).first()
        
        if not queue_item:
            return UpdateQueueItem(
                machine_queue_item=None,
                success=False,
                message=f"Queue item with ID {id} not found"
            )
        
        # Update queue item fields
        if input.position is not None:
            queue_item.position = input.position
        if input.priority is not None:
            queue_item.priority = input.priority
        if input.status:
            old_status = queue_item.status
            queue_item.status = input.status
            
            # Update machine status if needed
            if input.status == 'in_progress':
                machine = session.query(Machine).filter(Machine.id == queue_item.machine_id).first()
                if machine:
                    machine.status = 'busy'
                    machine.current_queue_item_id = queue_item.id
                
                queue_item.actual_start_time = datetime.datetime.utcnow()
                
                # Send feedback to Production Feedback Service
                send_production_feedback(queue_item.batch_id, queue_item.production_step_id, 'in_progress')
            
            elif input.status == 'completed':
                machine = session.query(Machine).filter(Machine.id == queue_item.machine_id).first()
                if machine and machine.current_queue_item_id == queue_item.id:
                    machine.status = 'available'
                    machine.current_queue_item_id = None
                
                queue_item.actual_end_time = datetime.datetime.utcnow()
                
                # Send feedback to Production Feedback Service
                send_production_feedback(queue_item.batch_id, queue_item.production_step_id, 'completed', 100)
                
                # Update Production Management Service about completed step
                try:
                    mutation = """
                    mutation($stepId: Int!) {
                        completeProductionStep(stepId: $stepId) {
                            success
                            message
                        }
                    }
                    """
                    variables = {"stepId": queue_item.production_step_id}
                    
                    requests.post(
                        GRAPHQL_ENDPOINTS["production_management"],
                        json={"query": mutation, "variables": variables}
                    )
                except Exception as e:
                    print(f"Error updating Production Management Service: {e}")
            
            # Add operation log for status change
            log = OperationLog(
                machine_id=queue_item.machine_id,
                queue_item_id=queue_item.id,
                operation_type=input.status,
                operator='system',
                notes=f"Status changed from {old_status} to {input.status}"
            )
            session.add(log)
        
        if input.estimated_start_time:
            queue_item.estimated_start_time = input.estimated_start_time
        if input.estimated_end_time:
            queue_item.estimated_end_time = input.estimated_end_time
        if input.actual_start_time:
            queue_item.actual_start_time = input.actual_start_time
        if input.actual_end_time:
            queue_item.actual_end_time = input.actual_end_time
        if input.setup_time_minutes is not None:
            queue_item.setup_time_minutes = input.setup_time_minutes
        if input.processing_time_minutes is not None:
            queue_item.processing_time_minutes = input.processing_time_minutes
        if input.materials_ready is not None:
            queue_item.materials_ready = input.materials_ready
        
        session.commit()
        session.refresh(queue_item)
        session.close()
        
        return UpdateQueueItem(
            machine_queue_item=queue_item,
            success=True,
            message="Queue item updated successfully"
        )

class ReorderQueue(graphene.Mutation):
    class Arguments:
        machine_id = graphene.Int(required=True)
    
    success = graphene.Boolean()
    message = graphene.String()
    
    def mutate(self, info, machine_id):
        session = get_session()
        
        # Get all queued items for this machine
        queue_items = session.query(MachineQueueItem).filter(
            MachineQueueItem.machine_id == machine_id,
            MachineQueueItem.status == 'queued'
        ).order_by(desc(MachineQueueItem.priority), MachineQueueItem.position).all()
        
        # Reorder positions based on priority
        for index, item in enumerate(queue_items, 1):
            item.position = index
        
        session.commit()
        session.close()
        
        return ReorderQueue(
            success=True,
            message=f"Queue for machine ID {machine_id} reordered successfully"
        )

class CreateOperationLog(graphene.Mutation):
    class Arguments:
        input = OperationLogInput(required=True)
    
    operation_log = graphene.Field(lambda: OperationLogType)
    success = graphene.Boolean()
    message = graphene.String()
    
    def mutate(self, info, input):
        session = get_session()
        
        log = OperationLog(
            machine_id=input.machine_id,
            queue_item_id=input.queue_item_id,
            operation_type=input.operation_type,
            operator=input.operator or 'system',
            notes=input.notes,
            error_details=input.error_details
        )
        
        session.add(log)
        session.commit()
        session.refresh(log)
        session.close()
        
        return CreateOperationLog(
            operation_log=log,
            success=True,
            message="Operation log created successfully"
        )

class Mutation(graphene.ObjectType):
    create_machine = CreateMachine.Field()
    update_machine = UpdateMachine.Field()
    add_to_queue = AddToQueue.Field()
    update_queue_item = UpdateQueueItem.Field()
    reorder_queue = ReorderQueue.Field()
    create_operation_log = CreateOperationLog.Field()

# Queries
class Query(graphene.ObjectType):
    node = relay.Node.Field()
    
    # Machine queries
    machine = graphene.Field(MachineType, id=graphene.Int())
    all_machines = graphene.List(MachineType)
    machines_by_type = graphene.List(MachineType, machine_type=graphene.String())
    machines_by_status = graphene.List(MachineType, status=graphene.String())
    
    # Queue item queries
    queue_item = graphene.Field(MachineQueueItemType, id=graphene.Int())
    queue_items_by_machine = graphene.List(MachineQueueItemType, machine_id=graphene.Int())
    queue_items_by_status = graphene.List(MachineQueueItemType, status=graphene.String())
    queue_items_by_batch = graphene.List(MachineQueueItemType, batch_id=graphene.Int())
    
    # Operation log queries
    operation_log = graphene.Field(OperationLogType, id=graphene.Int())
    operation_logs_by_machine = graphene.List(OperationLogType, machine_id=graphene.Int(), limit=graphene.Int())
    operation_logs_by_queue_item = graphene.List(OperationLogType, queue_item_id=graphene.Int())
    
    def resolve_machine(self, info, id):
        session = get_session()
        machine = session.query(Machine).filter(Machine.id == id).first()
        session.close()
        return machine
    
    def resolve_all_machines(self, info):
        session = get_session()
        machines = session.query(Machine).all()
        session.close()
        return machines
    
    def resolve_machines_by_type(self, info, machine_type):
        session = get_session()
        machines = session.query(Machine).filter(Machine.machine_type == machine_type).all()
        session.close()
        return machines
    
    def resolve_machines_by_status(self, info, status):
        session = get_session()
        machines = session.query(Machine).filter(Machine.status == status).all()
        session.close()
        return machines
    
    def resolve_queue_item(self, info, id):
        session = get_session()
        item = session.query(MachineQueueItem).filter(MachineQueueItem.id == id).first()
        session.close()
        return item
    
    def resolve_queue_items_by_machine(self, info, machine_id):
        session = get_session()
        items = session.query(MachineQueueItem).filter(
            MachineQueueItem.machine_id == machine_id
        ).order_by(MachineQueueItem.position).all()
        session.close()
        return items
    
    def resolve_queue_items_by_status(self, info, status):
        session = get_session()
        items = session.query(MachineQueueItem).filter(MachineQueueItem.status == status).all()
        session.close()
        return items
    
    def resolve_queue_items_by_batch(self, info, batch_id):
        session = get_session()
        items = session.query(MachineQueueItem).filter(MachineQueueItem.batch_id == batch_id).all()
        session.close()
        return items
    
    def resolve_operation_log(self, info, id):
        session = get_session()
        log = session.query(OperationLog).filter(OperationLog.id == id).first()
        session.close()
        return log
    
    def resolve_operation_logs_by_machine(self, info, machine_id, limit=100):
        session = get_session()
        logs = session.query(OperationLog).filter(
            OperationLog.machine_id == machine_id
        ).order_by(desc(OperationLog.timestamp)).limit(limit).all()
        session.close()
        return logs
    
    def resolve_operation_logs_by_queue_item(self, info, queue_item_id):
        session = get_session()
        logs = session.query(OperationLog).filter(
            OperationLog.queue_item_id == queue_item_id
        ).order_by(desc(OperationLog.timestamp)).all()
        session.close()
        return logs

schema = graphene.Schema(query=Query, mutation=Mutation)
